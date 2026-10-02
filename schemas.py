from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from scheduler import REVIEW_INTERVALS

from typing import Literal

class AttemptCreate(BaseModel):
    reviewed_on: date
    mastery_level: str

    @field_validator("mastery_level")
    @classmethod
    def validate_mastery_level(cls, value: str) -> str:
        if value not in REVIEW_INTERVALS:
            raise ValueError(f"Invalid mastery level: {value}")
        return value

class ReviewCreate(AttemptCreate):
    problem_number: int = Field(gt=0)


class ImportPreviewRequest(BaseModel):
    csv_text: str = Field(min_length=1)


class ProblemCreate(BaseModel):
    number : int = Field(gt=0)
    name : str = Field(min_length=1)
    difficulty : Literal["Easy", "Medium", "Hard"]
    topic : str = Field(min_length=1)
    notes : str = ""
    first_attempt: AttemptCreate | None = None
    
    @field_validator("name", "topic")
    @classmethod
    def validate_nonblank_text(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) == 0:
            raise ValueError("Must not be blank")
        return cleaned
    
class ProblemSummary(BaseModel):
    number: int 
    name: str
    difficulty: str
    topic: str
    mastery_level: str | None
    next_review: date | None
    attempts: int
    notes: str
    archived: bool


class StatementElement(BaseModel):
    tag: str
    children: list[StatementElement | str] = Field(default_factory=list)
    src: str | None = None
    alt: str | None = None


class PracticePick(BaseModel):
    # Used internally for saving the attempt; the dialog hides this number.
    problem_number: int
    statement: list[StatementElement | str] | None
    statement_error: str | None = None
    leetcode_url: str | None = None


class StatementSaveRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)

    @field_validator("text")
    @classmethod
    def validate_statement_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Paste a non-empty problem statement")
        return value
