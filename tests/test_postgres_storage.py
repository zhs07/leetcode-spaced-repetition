"""Real PostgreSQL tests; create and stop an isolated temporary cluster.

No database URL is read from the environment. PG_BIN optionally locates the
PostgreSQL binaries; otherwise use PATH or Homebrew's PostgreSQL 17 install.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import shutil
from threading import Barrier
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from importing import ImportedProblem
from guest_limits import ProblemLimitExceeded
from migrate import MIGRATIONS, SchemaMismatch, check_schema, migrate
from models import Problem, Review
from postgres_storage import PostgresStore, open_pool
from schemas import AttemptCreate, ProblemCreate
from storage_errors import DuplicateProblem, ProblemNotFound, StorageError
from summaries import build_problem_summary
from tracker import get_due_problems


@pytest.fixture
def stores(database):
    pool = open_pool(make_conninfo(database, user="tracker_test_runtime"), sslmode="disable")
    try:
        yield PostgresStore(pool, uuid4()), PostgresStore(pool, uuid4())
    finally:
        pool.close()


def problem(number=1, notes="private"):
    return Problem(number, "Example", "Easy", "Arrays", notes)


def review(number=1, mastery="Mastered"):
    return Review(number, date(2026, 10, 1), mastery)


def imported(number=1):
    return ImportedProblem(problem=ProblemCreate(
        number=number, name="Imported", difficulty="Easy", topic="Arrays", notes="CSV note",
        first_attempt=AttemptCreate(reviewed_on=date(2026, 9, 1), mastery_level="Mastered"),
    ), total_attempts=5)


def test_two_users_same_number_keep_independent_history_and_statements(stores):
    alice, bob = stores
    alice.save_problem_with_first_attempt(problem(notes="Alice's note"), review())
    bob.save_problem_with_first_attempt(problem(notes="Bob's note"), review(mastery="Partial Recall"))
    alice.save_problem_statement(1, "Alice's paste", "two-sum")
    bob.save_problem_statement(1, "Bob's paste")
    alice.save_problem_statement(1, "Alice's revised paste")
    assert alice.get_all_problems()[0].notes == "Alice's note"
    assert bob.get_all_problems()[0].notes == "Bob's note"
    assert alice.get_all_reviews() == [review()]
    assert bob.get_all_reviews() == [review(mastery="Partial Recall")]
    assert alice.get_problem_statement(1) == ("Alice's revised paste", "two-sum")
    assert bob.get_problem_statement(1) == ("Bob's paste", None)
    with pytest.raises(DuplicateProblem):
        alice.save_problem(problem())
    assert alice.delete_problem(1)
    assert alice.get_all_reviews() == []
    assert alice.get_problem_statement(1) is None
    assert len(bob.get_all_problems()) == len(bob.get_all_reviews()) == 1
    assert bob.get_problem_statement(1) == ("Bob's paste", None)


def test_missing_owner_cannot_read_or_mutate_another_users_problem(stores):
    alice, bob = stores
    bob.save_problem_with_first_attempt(problem(), review())
    bob.save_problem_statement(1, "Bob only")
    assert alice.get_all_problems() == alice.get_all_reviews() == []
    assert alice.get_problem_statement(1) is None
    assert not alice.delete_problem(1)
    assert not alice.archive_problem(1)
    assert not alice.restore_problem(1, date(2026, 10, 2))
    with pytest.raises(ProblemNotFound):
        alice.save_review(review())
    with pytest.raises(ProblemNotFound):
        alice.save_problem_statement(1, "Attempted overwrite")
    assert bob.get_all_problems() == [problem()]
    assert bob.get_all_reviews() == [review()]
    assert bob.get_problem_statement(1) == ("Bob only", None)


def test_archive_restore_and_record_attempt_preserve_schedule(stores):
    alice, bob = stores
    for store in stores:
        store.save_problem_with_first_attempt(problem(), review())
    today = date(2026, 10, 2)
    assert alice.archive_problem(1)
    assert alice.archive_problem(1)
    assert get_due_problems(alice.get_all_problems(), alice.get_all_reviews(), today) == []
    assert not bob.get_all_problems()[0].archived
    assert alice.restore_problem(1, today)
    assert alice.restore_problem(1, date(2026, 10, 3))
    assert alice.get_all_problems()[0].review_due_on == today
    assert len(get_due_problems(alice.get_all_problems(), alice.get_all_reviews(), today)) == 1
    alice.save_review(Review(1, today, "Solved Independently"))
    assert alice.restore_problem(1, date(2026, 10, 4))
    summary = build_problem_summary(alice.get_all_problems()[0], alice.get_all_reviews())
    assert summary.next_review == date(2026, 10, 16)
    assert summary.attempts == 2
    assert bob.get_all_reviews() == [review()]


def test_same_day_latest_review_order_matches_legacy(stores):
    alice, _ = stores
    alice.save_problem_with_first_attempt(problem(), review(mastery="Partial Recall"))
    alice.save_review(review(mastery="Mastered"))
    summary = build_problem_summary(alice.get_all_problems()[0], alice.get_all_reviews())
    assert summary.mastery_level == "Mastered"


def test_import_is_repeat_safe_owner_scoped_and_keeps_counts(stores):
    alice, bob = stores
    bob.save_problem_with_first_attempt(problem(), review())
    batch = [imported(2), imported(1), imported(2)]
    result = alice.save_imported_problems(batch)
    assert result.imported_numbers == [2, 1]
    assert result.skipped_existing_numbers == [2]
    assert alice.save_imported_problems(batch).skipped_existing_numbers == [2, 1, 2]
    assert len(alice.get_all_reviews()) == 2
    assert [p.historical_attempts for p in alice.get_all_problems()] == [4, 4]
    assert build_problem_summary(alice.get_all_problems()[0], alice.get_all_reviews()).attempts == 5
    assert bob.get_all_problems() == [problem()]
    assert bob.get_all_reviews() == [review()]


def fail_review_for(database, number):
    with psycopg.connect(database) as connection:
        connection.execute(sql.SQL("""
            ALTER TABLE tracker.reviews ADD CONSTRAINT test_failure
            CHECK (problem_number <> {})
        """).format(sql.Literal(number)))


def test_failed_import_rolls_back_whole_batch(stores, database):
    alice, _ = stores
    fail_review_for(database, 2)
    with pytest.raises(StorageError):
        alice.save_imported_problems([imported(1), imported(2)])
    assert alice.get_all_problems() == alice.get_all_reviews() == []


def test_failed_first_attempt_rolls_back_parent(stores, database):
    alice, _ = stores
    fail_review_for(database, 1)
    with pytest.raises(StorageError):
        alice.save_problem_with_first_attempt(problem(), review())
    assert alice.get_all_problems() == []


def test_failed_review_preserves_restore_override(stores, database):
    alice, _ = stores
    alice.save_problem(problem())
    alice.archive_problem(1)
    today = date(2026, 10, 2)
    alice.restore_problem(1, today)
    fail_review_for(database, 1)
    with pytest.raises(StorageError):
        alice.save_review(review())
    assert alice.get_all_problems()[0].review_due_on == today
    assert alice.get_all_reviews() == []


def test_concurrent_imports_create_one_review_per_problem(stores):
    alice, _ = stores
    barrier = Barrier(2)

    def run(numbers):
        barrier.wait(timeout=10)
        return alice.save_imported_problems([imported(n) for n in numbers])

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run, [1, 2]), executor.submit(run, [2, 1])]
        results = [future.result(timeout=15) for future in futures]
    assert sum(len(result.imported_numbers) for result in results) == 2
    assert len(alice.get_all_problems()) == len(alice.get_all_reviews()) == 2


def test_concurrent_reviews_both_persist(stores):
    alice, _ = stores
    alice.save_problem(problem())
    barrier = Barrier(2)

    def run():
        barrier.wait(timeout=10)
        alice.save_review(review())

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run) for _ in range(2)]
        for future in futures:
            future.result(timeout=15)
    assert len(alice.get_all_reviews()) == 2


@pytest.mark.parametrize("owner", [None, "", "not-a-uuid", str(uuid4()), UUID(int=0)])
def test_store_requires_explicit_uuid(owner):
    with pytest.raises(ValueError):
        PostgresStore(None, owner)


def test_migration_is_repeat_safe_and_checks_content(database, tmp_path):
    with psycopg.connect(database) as connection:
        migrate(connection)
        migrate(connection)
        check_schema(connection)
        assert connection.execute("SELECT count(*) FROM tracker.schema_migrations").fetchone()[0] == 1
    for path in MIGRATIONS.glob("*.sql"):
        (tmp_path / path.name).write_text(path.read_text() + "\n-- edited after application\n")
    with psycopg.connect(database) as connection:
        with pytest.raises(SchemaMismatch):
            migrate(connection, tmp_path)


def test_failed_migration_rolls_back_schema_and_version(database, tmp_path):
    for path in MIGRATIONS.glob("*.sql"):
        shutil.copyfile(path, tmp_path / path.name)
    (tmp_path / "002_failure.sql").write_text(
        "CREATE TABLE tracker.should_rollback (id integer); SELECT 1 / 0;"
    )
    with psycopg.connect(database) as connection:
        with pytest.raises(psycopg.errors.DivisionByZero):
            migrate(connection, tmp_path)
        assert connection.execute("SELECT to_regclass('tracker.should_rollback')").fetchone() == (None,)
        assert connection.execute("SELECT count(*) FROM tracker.schema_migrations").fetchone() == (1,)


def test_runtime_cannot_change_schema_and_ungranted_role_cannot_read(database, stores):
    with psycopg.connect(make_conninfo(database, user="tracker_test_runtime")) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connection.transaction():
                connection.execute("CREATE TABLE tracker.forbidden (id integer)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connection.transaction():
                connection.execute("DELETE FROM tracker.schema_migrations")
    with psycopg.connect(make_conninfo(database, user="tracker_test_stranger")) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT * FROM tracker.problems")


def test_guest_cap_counts_archived_and_delete_frees_capacity(stores):
    alice, bob = stores
    guest = PostgresStore(alice.pool, alice.user_id, problem_limit=2)
    guest.save_problem_with_first_attempt(problem(1), review(1))
    guest.save_problem_with_first_attempt(problem(2), review(2))
    guest.save_problem_statement(1, "Keep this statement")
    guest.archive_problem(1)
    before = guest.get_all_problems(), guest.get_all_reviews()
    with pytest.raises(ProblemLimitExceeded):
        guest.save_problem_with_first_attempt(problem(3), review(3))
    assert (guest.get_all_problems(), guest.get_all_reviews()) == before
    assert guest.get_problem_statement(1) == ("Keep this statement", None)
    with pytest.raises(DuplicateProblem):
        guest.save_problem(problem(1))
    guest.save_review(review(2))  # Existing practice remains available at capacity.
    bob.save_problem(problem(3))  # Another owner has independent capacity.
    assert guest.delete_problem(1)
    guest.save_problem_with_first_attempt(problem(3), review(3))
    assert [p.number for p in guest.get_all_problems()] == [2, 3]
    assert bob.get_all_problems() == [problem(3)]


def test_guest_import_capacity_is_distinct_repeat_safe_and_all_or_nothing(stores):
    alice, _ = stores
    guest = PostgresStore(alice.pool, alice.user_id, problem_limit=2)
    guest.save_problem_with_first_attempt(problem(1), review(1))
    before = guest.get_all_problems(), guest.get_all_reviews()
    with pytest.raises(ProblemLimitExceeded):
        guest.save_imported_problems([imported(1), imported(2), imported(3)])
    assert (guest.get_all_problems(), guest.get_all_reviews()) == before
    result = guest.save_imported_problems([imported(1), imported(2), imported(2)])
    assert result.imported_numbers == [2]
    assert result.skipped_existing_numbers == [1, 2]
    assert guest.save_imported_problems([imported(1), imported(2)]).imported_numbers == []
    assert len(guest.get_all_reviews()) == 2


def test_older_guest_above_cap_preserves_records_and_reimports(stores):
    alice, _ = stores
    alice.save_imported_problems([imported(1), imported(2), imported(3)])
    guest = PostgresStore(alice.pool, alice.user_id, problem_limit=2)
    before = guest.get_all_problems(), guest.get_all_reviews()
    assert guest.save_imported_problems([imported(1), imported(2)]).imported_numbers == []
    with pytest.raises(ProblemLimitExceeded):
        guest.save_problem(problem(4))
    assert (guest.get_all_problems(), guest.get_all_reviews()) == before


def test_failed_guest_save_releases_capacity_and_transaction_lock(stores, database):
    alice, _ = stores
    guest = PostgresStore(alice.pool, alice.user_id, problem_limit=1)
    fail_review_for(database, 1)
    with pytest.raises(StorageError):
        guest.save_problem_with_first_attempt(problem(1), review(1))
    assert guest.get_all_problems() == guest.get_all_reviews() == []
    guest.save_problem_with_first_attempt(problem(2), review(2))
    assert guest.get_all_problems() == [problem(2)]


@pytest.mark.parametrize("methods", [("single", "single"), ("import", "import"), ("single", "import")])
def test_concurrent_guest_additions_across_pools_cannot_exceed_cap(stores, database, methods):
    alice, _ = stores
    alice.save_problem_with_first_attempt(problem(1), review(1))
    second_pool = open_pool(make_conninfo(database, user="tracker_test_runtime"), sslmode="disable")
    guests = [PostgresStore(pool, alice.user_id, problem_limit=2) for pool in (alice.pool, second_pool)]
    barrier = Barrier(2)

    def add(store, method, number):
        barrier.wait(timeout=10)
        try:
            if method == "single":
                store.save_problem_with_first_attempt(problem(number), review(number))
            else:
                store.save_imported_problems([imported(number), imported(number)])
            return "saved"
        except ProblemLimitExceeded:
            return "limited"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(add, store, method, number)
                       for store, method, number in zip(guests, methods, [2, 3])]
            assert sorted(f.result(timeout=15) for f in futures) == ["limited", "saved"]
        assert len(alice.get_all_problems()) == len(alice.get_all_reviews()) == 2
    finally:
        second_pool.close()


def test_missing_schema_rejected_without_creating_tables(database):
    with psycopg.connect(database) as connection:
        connection.execute("DROP SCHEMA tracker CASCADE")
    with pytest.raises(SchemaMismatch):
        open_pool(database, sslmode="disable")
    with psycopg.connect(database) as connection:
        assert connection.execute("SELECT to_regnamespace('tracker')").fetchone() == (None,)
