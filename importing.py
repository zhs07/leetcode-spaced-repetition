"""Standard and Notion CSV adapters sharing preview and response schemas."""

import csv
import io
import re
from datetime import date, datetime
from collections.abc import Callable

from pydantic import BaseModel, Field, ValidationError, model_validator

from schemas import AttemptCreate, ProblemCreate


class ImportedProblem(BaseModel):
    """Preview data; total_attempts includes the latest known attempt."""

    problem: ProblemCreate
    total_attempts: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_history(self) -> "ImportedProblem":
        if self.problem.first_attempt is None and self.total_attempts != 0:
            raise ValueError("Positive total_attempts requires reviewed_on and mastery_level")
        if self.problem.first_attempt is not None and self.total_attempts < 1:
            raise ValueError("A reviewed problem must have at least one attempt")
        return self


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

STANDARD_REQUIRED_COLUMNS = ("number", "name", "difficulty", "topic")
STANDARD_OPTIONAL_COLUMNS = ("notes", "reviewed_on", "mastery_level", "total_attempts")


def parse_standard_row(row: dict[str, str]) -> ImportedProblem | None:
    """Adapt explicit standard columns; never guess a review or problem number."""
    columns = (*STANDARD_REQUIRED_COLUMNS, *STANDARD_OPTIONAL_COLUMNS)
    if all(not row.get(column, "").strip() for column in columns):
        return None

    number_text = row["number"].strip()
    if not re.fullmatch(r"[0-9]+", number_text) or int(number_text) <= 0:
        raise ValueError("number must be a positive integer")
    for column in ("name", "topic"):
        if not row[column].strip():
            raise ValueError(f"{column} must not be blank")

    reviewed_text = row.get("reviewed_on", "").strip()
    mastery = row.get("mastery_level", "").strip()
    if bool(reviewed_text) != bool(mastery):
        raise ValueError("Provide both reviewed_on and mastery_level, or leave both blank")

    attempt = None
    if reviewed_text:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", reviewed_text):
            raise ValueError("reviewed_on must use YYYY-MM-DD")
        try:
            reviewed_on = date.fromisoformat(reviewed_text)
        except ValueError as error:
            raise ValueError("reviewed_on must be a valid YYYY-MM-DD date") from error
        attempt = AttemptCreate(reviewed_on=reviewed_on, mastery_level=mastery)

    count_text = row.get("total_attempts", "").strip()
    if count_text and not re.fullmatch(r"[0-9]+", count_text):
        raise ValueError("total_attempts must be a nonnegative integer")
    total_attempts = int(count_text) if count_text else int(attempt is not None)

    return ImportedProblem(
        problem=ProblemCreate(
            number=int(number_text), name=row["name"].strip(),
            difficulty=row["difficulty"].strip(), topic=row["topic"].strip(),
            notes=row.get("notes", ""), first_attempt=attempt,
        ),
        total_attempts=total_attempts,
    )


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
    Ignore Review Status and Review Interval (Days): the app calculates the
    schedule from the date and mastery, including for exports using older intervals.
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
    return _preview_csv(csv_text, NOTION_DATA_COLUMNS, parse_notion_row)


def preview_standard_csv(csv_text: str) -> ImportPreview:
    return _preview_csv(csv_text, STANDARD_REQUIRED_COLUMNS, parse_standard_row)


def _preview_csv(
    csv_text: str, required_columns: tuple[str, ...],
    parse_row: Callable[[dict[str, str]], ImportedProblem | None],
) -> ImportPreview:
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

    missing_columns = set(required_columns) - set(headers)
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
            res = parse_row(row)
            if res is None:
                skipped_rows += 1
                continue
        except ValueError as error:
            message = str(error) or "Invalid row"
            if isinstance(error, ValidationError):
                message = "; ".join(
                    f"{'.'.join(map(str, detail['loc']))}: {detail['msg']}".lstrip(": ")
                    for detail in error.errors()
                )
            errors.append(
                ImportRowError(
                    row_number=row_number, message=message
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
