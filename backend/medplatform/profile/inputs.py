from typing import Any, Literal

from pydantic import Field

from ..web.inputs import ID, Input, Version


class ResponseCreate(Input):
    supersedes_response_id: ID | None = None


class AnswersPut(Input):
    expected_revision: Version
    answers: dict[
        Literal["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"], dict[str, Any]
    ] = Field(min_length=1)


class Submit(Input):
    expected_revision: Version
    confirmed: Literal[True]
    same_episode: bool | None = None


class ProfileCreate(Input):
    response_id: ID
