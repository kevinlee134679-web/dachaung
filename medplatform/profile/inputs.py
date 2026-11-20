from typing import Literal

from pydantic import field_validator, model_validator

from ..web.inputs import ID, Input, Version


class ResponseCreate(Input):
    questionnaire_version: str
    supersedes_response_id: ID | None = None


class Answer(Input):
    state: Literal["answered", "unknown", "not_applicable", "not_answered"]
    value: dict | None

    @model_validator(mode="after")
    def correct_null(self):
        if (self.state == "answered") != (self.value is not None):
            raise ValueError("state/value mismatch")
        return self


class AnswersPut(Input):
    expected_revision: Version
    answers: dict[str, Answer]

    @field_validator("answers")
    @classmethod
    def eight(cls, value):
        if set(value) != {f"Q{i}" for i in range(1, 9)}:
            raise ValueError("exactly eight themes required")
        return value


class Submit(Input):
    expected_revision: Version
    confirmed: Literal[True]


class ProfileCreate(Input):
    response_id: ID
