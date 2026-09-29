import sqlite3
from models import Problem, Review
from datetime import date

def get_connection(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)

    try:
        connection.execute("PRAGMA foreign_keys = ON")
    except:
        connection.close()
        raise

    return connection

def initialize_database(database_path: str) -> None:
    connection = get_connection(database_path)

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS problems (
                number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                topic TEXT NOT NULL,
                notes TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                problem_number INTEGER NOT NULL,
                reviewed_on TEXT NOT NULL,
                mastery_level TEXT NOT NULL,
                FOREIGN KEY (problem_number) REFERENCES problems(number)
            )
        """)
        connection.commit()
    finally:
        connection.close()


def save_problem(database_path: str, problem: Problem) -> None:
    connection =get_connection(database_path)

    try:
        connection.execute(
            """
            INSERT INTO problems (number, name, difficulty, topic, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                problem.number,
                problem.name,
                problem.difficulty,
                problem.topic,
                problem.notes,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def get_all_problems(database_path: str) -> list[Problem]:
    connection = get_connection(database_path)

    try:
        rows = connection.execute("""
            SELECT number, name, difficulty, topic, notes
            FROM problems
            ORDER BY number
            """).fetchall()
    finally:
        connection.close()
    problems = []

    for row in rows:
        problem = Problem(number=row[0], name=row[1], difficulty=row[2], topic=row[3], notes=row[4])
        problems.append(problem)

    return problems


def save_review(database_path: str, review: Review) -> None:
    connection = get_connection(database_path)
    
    try:
        connection.execute(
            """
            INSERT INTO reviews (problem_number, reviewed_on, mastery_level)
            VALUES (?, ?, ?)
            """,
            (
                review.problem_number,
                review.reviewed_on.isoformat(),
                review.mastery_level,
    
            ),
        )
        connection.commit()
    finally:
        connection.close()

def get_all_reviews(database_path: str, ) -> list[Review]:
    connection = get_connection(database_path)
    
    try:
        rows = connection.execute("""
            SELECT problem_number, reviewed_on, mastery_level
            FROM reviews
            ORDER BY reviewed_on ASC, id DESC
            """).fetchall()
    finally:
        connection.close()
        
    reviews = []

    for row in rows:
        review = Review(problem_number=row[0], reviewed_on=date.fromisoformat(row[1]), mastery_level=row[2])
        reviews.append(review)

    return reviews


def save_problem_with_first_attempt(
    database_path: str,
    problem: Problem,
    first_attempt: Review | None = None,
) -> None:
    if first_attempt is not None and first_attempt.problem_number != problem.number:
        raise ValueError

    connection = get_connection(database_path)
    
    try:
        connection.execute(
            """
            INSERT INTO problems (number, name, difficulty, topic, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                problem.number,
                problem.name,
                problem.difficulty,
                problem.topic,
                problem.notes,
            )   
        )
        if first_attempt is not None:
            connection.execute(
                    """
                    INSERT INTO reviews (problem_number, reviewed_on, mastery_level)
                    VALUES (?, ?, ?)
                    """,
                    (
                        first_attempt.problem_number,
                        first_attempt.reviewed_on.isoformat(),
                        first_attempt.mastery_level,
            
                    ),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()