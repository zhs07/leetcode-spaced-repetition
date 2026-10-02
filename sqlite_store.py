"""Adapter preserving the existing local app while routes use a common interface."""

import sqlite3

import storage
from storage_errors import DuplicateProblem, ProblemNotFound, StorageError


class SQLiteStore:
    def __init__(self, database_path: str):
        self.database_path = database_path

    def _call(self, operation, *args):
        try:
            return operation(self.database_path, *args)
        except sqlite3.IntegrityError as error:
            if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY:
                raise DuplicateProblem("Problem already exists") from error
            if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY:
                raise ProblemNotFound("Problem not found") from error
            raise StorageError("Database operation failed") from error
        except sqlite3.DatabaseError as error:
            raise StorageError("Database operation failed") from error

    def get_all_problems(self):
        return self._call(storage.get_all_problems)

    def get_all_reviews(self):
        return self._call(storage.get_all_reviews)

    def save_review(self, review):
        return self._call(storage.save_review, review)

    def save_problem_with_first_attempt(self, problem, first_attempt=None):
        return self._call(storage.save_problem_with_first_attempt, problem, first_attempt)

    def save_imported_problems(self, imports):
        return self._call(storage.save_imported_problems, imports)

    def delete_problem(self, number):
        return self._call(storage.delete_problem, number)

    def archive_problem(self, number):
        return self._call(storage.archive_problem, number)

    def restore_problem(self, number, today):
        return self._call(storage.restore_problem, number, today)

    def get_problem_statement(self, number):
        return self._call(storage.get_problem_statement, number)

    def save_problem_statement(self, number, html, slug=None):
        return self._call(storage.save_problem_statement, number, html, slug)
