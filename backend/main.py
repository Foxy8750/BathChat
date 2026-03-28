import hashlib
import hmac
import json
import os
import secrets

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base, engine, get_db
from models import Match, Profile, User
from schemas import AIMatchData, MatchRead, ProfileRead, ProfileUpsert, TokenResponse, UserCreate, UserLogin, UserRead


app = FastAPI(title="SocialMatch AI API")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hex_digest = stored_hash.split("$", maxsplit=1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return hmac.compare_digest(digest.hex(), hex_digest)


async def get_current_user(
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await db.get(User, x_user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
    return user


async def get_ai_match_data(user1_profile: Profile, user2_profile: Profile) -> AIMatchData:
    """Placeholder Anthropic integration returning match score, reason, and icebreaker."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    prompt = {
        "user1": {
            "interests": user1_profile.interests,
            "societies": user1_profile.societies,
            "goals": user1_profile.goals,
            "vibe_tags": user1_profile.vibe_tags,
            "bio": user1_profile.bio,
        },
        "user2": {
            "interests": user2_profile.interests,
            "societies": user2_profile.societies,
            "goals": user2_profile.goals,
            "vibe_tags": user2_profile.vibe_tags,
            "bio": user2_profile.bio,
        },
    }

    if api_key:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 300,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Return ONLY valid JSON with keys: match_score (0-100), reason, icebreaker. "
                        f"Input profiles: {json.dumps(prompt)}"
                    ),
                }
            ],
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            text = data.get("content", [{}])[0].get("text", "{}")
            try:
                parsed = json.loads(text)
                return AIMatchData(
                    match_score=float(parsed.get("match_score", 50.0)),
                    reason=str(parsed.get("reason", "Shared university interests and compatible social goals.")),
                    icebreaker=str(parsed.get("icebreaker", "What is one Bath campus spot you would both recommend?")),
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

    # Fallback scoring keeps local development deterministic when no API key is set.
    shared_interests = len(set(user1_profile.interests) & set(user2_profile.interests))
    shared_societies = len(set(user1_profile.societies) & set(user2_profile.societies))
    shared_vibes = len(set(user1_profile.vibe_tags) & set(user2_profile.vibe_tags))
    raw_score = 35 + (shared_interests * 8) + (shared_societies * 10) + (shared_vibes * 6)
    score = max(0.0, min(100.0, float(raw_score)))
    reason = (
        f"You share {shared_interests} interests, {shared_societies} societies, "
        f"and {shared_vibes} vibe tags, suggesting strong compatibility."
    )
    icebreaker = "You both seem aligned. Want to swap your favorite student event this term?"
    return AIMatchData(match_score=score, reason=reason, icebreaker=icebreaker)


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> UserRead:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        name=payload.name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@app.post("/auth/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email.strip().lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Placeholder token format for quick integration in hackathon environments.
    return TokenResponse(access_token=f"user-{user.id}")


@app.get("/auth/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@app.post("/profiles/me", response_model=ProfileRead)
async def upsert_my_profile(
    payload: ProfileUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    profile = await db.get(Profile, current_user.id)
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.add(profile)

    profile.interests = payload.interests
    profile.societies = payload.societies
    profile.goals = payload.goals
    profile.vibe_tags = payload.vibe_tags
    profile.bio = payload.bio

    await db.commit()
    await db.refresh(profile)
    return ProfileRead.model_validate(profile)


@app.get("/profiles/me", response_model=ProfileRead)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    profile = await db.get(Profile, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileRead.model_validate(profile)


@app.post("/discovery/match/{candidate_id}", response_model=MatchRead)
async def discover_match(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MatchRead:
    if candidate_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot match with yourself")

    candidate = await db.get(User, candidate_id)
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    user_profile = await db.get(Profile, current_user.id)
    candidate_profile = await db.get(Profile, candidate_id)
    if not user_profile or not candidate_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both users must have profiles before matching",
        )

    existing = await db.execute(
        select(Match).where(
            or_(
                and_(Match.user1_id == current_user.id, Match.user2_id == candidate_id),
                and_(Match.user1_id == candidate_id, Match.user2_id == current_user.id),
            )
        )
    )
    old_match = existing.scalar_one_or_none()
    if old_match:
        return MatchRead.model_validate(old_match)

    ai_data = await get_ai_match_data(user_profile, candidate_profile)

    user1_id, user2_id = sorted([current_user.id, candidate_id])
    match = Match(
        user1_id=user1_id,
        user2_id=user2_id,
        match_score=ai_data.match_score,
        ai_reason=ai_data.reason,
        ai_icebreaker=ai_data.icebreaker,
        status="suggested",
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return MatchRead.model_validate(match)


@app.get("/discovery/matches", response_model=list[MatchRead])
async def list_my_matches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MatchRead]:
    result = await db.execute(
        select(Match).where(or_(Match.user1_id == current_user.id, Match.user2_id == current_user.id))
    )
    matches = result.scalars().all()
    return [MatchRead.model_validate(item) for item in matches]