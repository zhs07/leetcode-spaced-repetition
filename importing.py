"""Notion CSV parsing and import response schemas."""

import csv
import io
import re
from datetime import datetime

from pydantic import BaseModel, Field

from scheduler import REVIEW_INTERVALS
from schemas import AttemptCreate, ProblemCreate


class ImportedProblem(BaseModel):
    """Preview data; total_attempts includes the latest known attempt."""

    problem: ProblemCreate
    total_attempts: int = Field(ge=1)


class ImportRowError(BaseModel):
    row_number: int = Field(ge=2)
    message: str = Field(min_length=1)


class ImportPreview(BaseModel):
    problems: list[ImportedProblem]
    errors: list[ImportRowError]
    skipped_rows: int = Field(ge=0)


class ImportSaveResult(BaseModel):
    """Problem numbers saved or skipped, in input order."""

    imported_numbers: list[int]
    skipped_existing_numbers: list[int]


class ImportResult(ImportSaveResult):
    errors: list[ImportRowError]
    skipped_rows: int = Field(ge=0)


NOTION_DATA_COLUMNS = (
    "Problem",
    "Difficulty",
    "Topic",
    "Last Reviewed",
    "Mastery",
    "Pattern/Trick",
    "Reviews",
)

# These are the three mastery labels present in your current Notion export.
NOTION_MASTERY_LABELS = {
    "🔵 Mastered": "Mastered",
    "🟢 Solved Independently": "Solved Independently",
    "🟡 Solved With Struggle": "Solved with Struggle",
}


def parse_problem_title(title: str) -> tuple[str, int]:
    """Return (name, number) from a Notion problem title.

    Supported examples:
        "Two Sum #1" -> ("Two Sum", 1)
        "Max Area of Island # 695" -> ("Max Area of Island", 695)
        "House Robber I 198" -> ("House Robber I", 198)

    Raise ValueError when the title has no usable name or positive number.
    A missing number must be corrected, rather than guessed from the name.
    """
    # This pattern names the two pieces we want: "name" and "number".
    # It accepts an optional # and spaces before the trailing digits.
    match = re.fullmatch(
        r"(?P<name>.+?)\s+#?\s*(?P<number>\d+)",
        title.strip(),
    )

    if match is None:
        raise ValueError("No match found")

    name = match.group("name").strip()
    number = int(match.group("number"))

    if name == "":
        raise ValueError("Invalid problem name")
    if number <= 0:
        raise ValueError("Invalid problem number")

    return (name, number)


def parse_notion_row(row: dict[str, str]) -> ImportedProblem | None:
    """Convert one CSV dictionary into validated preview data without saving.

    The file reader will check required headers before calling this helper.
    Return None for an empty source record. Raise ValueError for invalid data;
    Pydantic's ValidationError is also a subclass of ValueError.

    Keep Reviews as a total count, including the latest known attempt.
    Ignore Review Status: the app calculates it from the date and mastery.
    """
    # The empty Notion record has a calculated interval of 0. Check source
    # fields only, so that calculated value does not make it look populated.
    if all(not row[column].strip() for column in NOTION_DATA_COLUMNS):
        return None

    name_num = parse_problem_title(row["Problem"])

    date_text = row["Last Reviewed"].strip()
    parsed_datetime = datetime.strptime(date_text, "%B %d, %Y")
    reviewed_on = parsed_datetime.date()

    mastery = NOTION_MASTERY_LABELS.get(row["Mastery"].strip())
    if mastery is None:
        raise ValueError("Unkown Label")

    attempt = AttemptCreate(reviewed_on=reviewed_on, mastery_level=mastery)

    if "Review Interval (Days)" in row:
        review_interval = int(row["Review Interval (Days)"])

        if REVIEW_INTERVALS[mastery] != review_interval:
            raise ValueError

    problem = ProblemCreate(
        number=name_num[1],
        name=name_num[0],
        difficulty=row["Difficulty"].strip(),
        topic=row["Topic"].strip(),
        notes=row["Pattern/Trick"],
        first_attempt=attempt,
    )

    return ImportedProblem(problem=problem, total_attempts=int(row["Reviews"]))


def preview_notion_csv(csv_text: str) -> ImportPreview:
    """Read CSV text and collect a preview without database writes.

    Row numbers count CSV records, including the header as row 1. A quoted
    note can contain multiple physical lines while remaining one record.
    Missing/duplicate headers reject the file. Invalid data rows are reported
    individually. Keep the first valid occurrence of each problem number.
    Existing problems in the database will be checked in a later step.
    """
    # StringIO lets the CSV reader read an in-memory string like an open file.
    # DictReader uses the header names as the keys of each row dictionary.
    # UTF-8 CSV exports sometimes begin with a byte-order mark.
    reader = csv.DictReader(io.StringIO(csv_text.removeprefix("\ufeff"), newline=""), strict=True)
    try:
        headers = reader.fieldnames or []
    except csv.Error as error:
        raise ValueError(f"Malformed CSV: {error}") from error

    missing_columns = set(NOTION_DATA_COLUMNS) - set(headers)
    if missing_columns:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing_columns))}")
    if len(headers) != len(set(headers)):
        raise ValueError("CSV contains duplicate column headers")

    problems: list[ImportedProblem] = []
    errors: list[ImportRowError] = []
    skipped_rows = 0
    seen_numbers: set[int] = set()

    try:
        rows = list(reader)
    except csv.Error as error:
        raise ValueError(f"Malformed CSV: {error}") from error

    for row_number, row in enumerate(rows, start=2):
        # DictReader uses a None key for extra cells, and None values for
        # missing cells. Report malformed records before calling your helper.
        if None in row or any(value is None for value in row.values()):
            errors.append(
                ImportRowError(
                    row_number=row_number,
                    message="Row has a different number of cells than the header",
                )
            )
            continue

        try:
            res = parse_notion_row(row)
            if res is None:
                skipped_rows += 1
                continue
        except ValueError as error:
            errors.append(
                ImportRowError(
                    row_number=row_number, message=str(error) or "Invalid row"
                )
            )
            continue

        problem_number = res.problem.number
        if problem_number in seen_numbers:
            errors.append(
                ImportRowError(
                    row_number=row_number,
                    message=f"Duplicate problem number: {problem_number}",
                )
            )
            continue

        seen_numbers.add(problem_number)
        problems.append(res)

    return ImportPreview(problems=problems, errors=errors, skipped_rows=skipped_rows)
