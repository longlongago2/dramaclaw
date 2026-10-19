"""Structured motion prompt and timing returned by the shot directors."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class VideoPromptPlan(BaseModel):
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    duration_seconds: float = Field(
        gt=0, le=300, allow_inf_nan=False,
        description="Recommended clip length in seconds, based on action and speech pacing",
    )
