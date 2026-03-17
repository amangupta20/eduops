from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict

# Strict base model to satisfy CodeRabbit and prevent hallucinated fields
class SessionModelBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class Session(SessionModelBase):
    id: str  # UUID, also used as the Docker label value
    scenario_id: str
    status: Literal["active", "completed", "abandoned"]
    workspace_path: str
    started_at: datetime
    completed_at: datetime | None = None
    review_text: str | None = None

class CheckResult(SessionModelBase):
    check_type: str
    check_name: str
    passed: bool
    message: str

class Review(SessionModelBase):
    what_went_well: list[str]
    what_could_improve: list[str]
    next_steps: list[str]