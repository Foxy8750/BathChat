import hashlib
import hmac
import math
import os
import secrets
from typing import Iterable

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from google import genai
from google.genai import types

from backend.database import Base, engine, get_db
from backend.models import Match, Profile, User
from backend.schemas import AIMatchData, MatchRead, ProfileRead, ProfileUpsert, TokenResponse, UserCreate, UserLogin, UserRead

load_dotenv()

client = genai.Client(api_key=os.getenv("API_KEY"))
app = FastAPI(title="BathChat API")


def get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]

    # Safe defaults for local dev plus Firebase Hosting previews/live.
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=r"^https://([a-z0-9-]+)\.(web\.app|firebaseapp\.com)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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



def normalize_exact_value(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def exact_overlap_count(items_a: list[str] | None, items_b: list[str] | None) -> int:
    set_a = {
        normalize_exact_value(v)
        for v in (items_a or [])
        if isinstance(v, str) and normalize_exact_value(v)
    }
    set_b = {
        normalize_exact_value(v)
        for v in (items_b or [])
        if isinstance(v, str) and normalize_exact_value(v)
    }
    return len(set_a & set_b)


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add profile fields to profiles table (not to users - they have elo_score and badge_tier in User model)
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS name VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS course VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS accommodation VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ethnicity VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS gender VARCHAR(60)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS spoken_language VARCHAR(120)"))
        # Ensure users table has elo_score and badge_tier (defined in User model)
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS elo_score INTEGER NOT NULL DEFAULT 500"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS badge_tier VARCHAR(40) NOT NULL DEFAULT 'bronze'"))
        await conn.execute(
            text(
                """
                UPDATE profiles p
                SET name = u.name
                FROM users u
                WHERE p.user_id = u.id
                  AND (p.name IS NULL OR p.name = '')
                """
            )
        )

@app.post("/auth/login")
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    print(f"DEBUG: Login attempt for email: '{payload.email}'") # Check for hidden spaces

    result = await db.execute(select(User).where(User.email == payload.email.strip().lower()))
    user = result.scalar_one_or_none()

    if not user:
        print("DEBUG: User NOT found in database.") # Error 1: Email is wrong
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user.hashed_password):
        print(f"DEBUG: Password mismatch for user {user.email}") # Error 2: Hashing is wrong
        print(f"DEBUG: Received password: {payload.password}")
        print(f"DEBUG: Stored hash: {user.hashed_password}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenResponse(access_token=f"user-{user.id}")


@app.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> UserRead:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()

    profile = Profile(user_id=user.id, name=payload.name)
    db.add(profile)

    await db.commit()
    await db.refresh(user)
    return UserRead(
        id=user.id,
        email=user.email,
        name=payload.name,
        elo_score=user.elo_score,
        badge_tier=user.badge_tier,
    )


@app.get("/auth/me", response_model=UserRead)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    profile = await db.get(Profile, current_user.id)
    display_name = profile.name if profile and profile.name else ""
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        name=display_name,
        elo_score=current_user.elo_score,
        badge_tier=current_user.badge_tier,
    )


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

    profile.name = payload.name
    profile.interests = payload.interests
    profile.course = payload.course
    profile.accommodation = payload.accommodation
    profile.ethnicity = payload.ethnicity
    profile.gender = payload.gender
    profile.spoken_language = payload.spoken_language
    profile.societies = payload.societies
    profile.goals = payload.goals
    profile.bio = payload.bio

    await db.commit()
    await db.refresh(profile)
    return ProfileRead(
        user_id=profile.user_id,
        name=profile.name,
        interests=profile.interests,
        course=profile.course,
        accommodation=profile.accommodation,
        ethnicity=profile.ethnicity,
        gender=profile.gender,
        spoken_language=profile.spoken_language,
        societies=profile.societies,
        goals=profile.goals,
        bio=profile.bio,
        elo_score=current_user.elo_score,
        badge_tier=current_user.badge_tier,
    )


@app.get("/profiles/me", response_model=ProfileRead)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    profile = await db.get(Profile, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileRead(
        user_id=profile.user_id,
        name=profile.name,
        interests=profile.interests,
        course=profile.course,
        accommodation=profile.accommodation,
        ethnicity=profile.ethnicity,
        gender=profile.gender,
        spoken_language=profile.spoken_language,
        societies=profile.societies,
        goals=profile.goals,
        bio=profile.bio,
        elo_score=current_user.elo_score,
        badge_tier=current_user.badge_tier,
    )


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
    ai_data = await get_ai_match_data(user_profile, candidate_profile)

    user1_id, user2_id = sorted([current_user.id, candidate_id])
    if old_match:
        # Recompute and update existing match so profile edits are reflected immediately.
        old_match.match_score = ai_data.match_score
        old_match.ai_reason = ai_data.reason
        old_match.ai_icebreaker = ai_data.icebreaker
        match = old_match
    else:
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

def clean_list(values: Iterable[str] | None) -> list[str]:
    return [v.strip() for v in (values or []) if v and v.strip()]


def ai_profile_payload(profile: Profile) -> dict:
    return {
        "interests": clean_list(profile.interests),
        "course": profile.course,
        "accommodation": profile.accommodation,
        "spoken_language": profile.spoken_language,
        "societies": clean_list(profile.societies),
        "goals": profile.goals,
        "bio": profile.bio,
    }


def profile_text_for_embedding(profile: Profile) -> str:
    bits: list[str] = []

    interests = clean_list(profile.interests)
    societies = clean_list(profile.societies)

    if profile.course:
        bits.append(f"Course: {profile.course}")
    if interests:
        bits.append(f"Interests: {', '.join(interests)}")
    if societies:
        bits.append(f"Societies: {', '.join(societies)}")
    if profile.spoken_language:
        bits.append(f"Language: {profile.spoken_language}")
    if profile.accommodation:
        bits.append(f"Accommodation: {profile.accommodation}")
    if profile.goals:
        bits.append(f"Goals: {profile.goals}")
    if profile.bio:
        bits.append(f"Bio: {profile.bio}")

    return "\n".join(bits)

def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    denom = norm(a) * norm(b)
    if denom == 0:
        return 0.0
    return dot(a, b) / denom

async def embedding_similarity(text1: str, text2: str) -> float:
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=[text1, text2],
    )
    emb1 = response.embeddings[0].values
    emb2 = response.embeddings[1].values
    return max(0.0, min(1.0, (cosine_similarity(emb1, emb2) + 1.0) / 2.0))

async def compute_match_score(user1_profile: Profile, user2_profile: Profile) -> float:
    shared_interests = exact_overlap_count(user1_profile.interests, user2_profile.interests)
    shared_societies = exact_overlap_count(user1_profile.societies, user2_profile.societies)

    course_1 = normalize_exact_value(user1_profile.course)
    course_2 = normalize_exact_value(user2_profile.course)
    same_course_exact = bool(course_1 and course_2 and course_1 == course_2)

    semantic_similarity = await embedding_similarity(
        profile_text_for_embedding(user1_profile),
        profile_text_for_embedding(user2_profile),
    )

    score = (
        10.0
        + semantic_similarity * 55.0
        + shared_interests * 10.0
        + shared_societies * 8.0
        + (12.0 if same_course_exact else 0.0)
    )
    return max(0.0, min(100.0, score))


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


async def generate_match_copy(
    user1_profile: Profile,
    user2_profile: Profile,
    score: float,
) -> tuple[str, str]:
    prompt = f"""
You are generating match feedback for a student social-connection app.

These two students have already been matched by the app above a similarity threshold.
So assume there is at least some genuine common ground.

Use only the profile details provided.
Do not mention protected or sensitive traits.
Do not make up facts.
Do not sound romantic, cheesy, or overly intense.

Your job:
1. Write a short reason explaining why they were matched.
2. Write one short, natural icebreaker one student could send the other.

The reason should:
- be 1 sentence
- mention shared themes if present, such as interests, course, societies, goals, language, or accommodation context
- sound warm but not exaggerated

The icebreaker should:
- be 1 sentence
- sound like something a real university student would send
- be specific enough to feel personal
- not be awkward, flirty, or invasive

Suggested similarity score from the matching system: {score:.1f}

Student 1:
{ai_profile_payload(user1_profile)}

Student 2:
{ai_profile_payload(user2_profile)}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "icebreaker": {"type": "string"},
                },
                "required": ["reason", "icebreaker"],
            },
            temperature=0.7,
        ),
    )

    data = response.parsed
    return data["reason"], data["icebreaker"]

async def get_ai_match_data(user1_profile: Profile, user2_profile: Profile) -> AIMatchData:
    score = await compute_match_score(user1_profile, user2_profile)
    reason, icebreaker = await generate_match_copy(user1_profile, user2_profile, score)

    return AIMatchData(
        match_score=score,
        reason=reason,
        icebreaker=icebreaker,
    )