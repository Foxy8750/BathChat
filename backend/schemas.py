from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class UserCreate(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_bath_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.endswith("@bath.ac.uk"):
            raise ValueError("Only @bath.ac.uk emails are allowed")
        return normalized


class UserLogin(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    id: int
    email: str
    name: str
    elo_score: int
    badge_tier: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileUpsert(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    interests: list[str] = Field(default_factory=list)
    course: str | None = Field(default=None, max_length=120)
    accommodation: str | None = Field(default=None, max_length=120)
    ethnicity: str | None = Field(default=None, max_length=120)
    gender: str | None = Field(default=None, max_length=60)
    spoken_language: str | None = Field(default=None, max_length=120)
    societies: list[str] = Field(default_factory=list)
    goals: str | None = None
    bio: str | None = None


class ProfileBase(ProfileUpsert):
    pass


class ProfileRead(ProfileBase):
    user_id: int
    elo_score: int
    badge_tier: str

    model_config = {"from_attributes": True}


class AIMatchData(BaseModel):
    match_score: float
    reason: str
    icebreaker: str


class MatchRead(BaseModel):
    id: int
    user1_id: int
    user2_id: int
    match_score: float
    ai_reason: str
    ai_icebreaker: str
    status: str

    model_config = {"from_attributes": True}


class EloLogRead(BaseModel):
    id: int
    user_id: int
    points: int
    reason: str
    timestamp: datetime

    model_config = {"from_attributes": True}