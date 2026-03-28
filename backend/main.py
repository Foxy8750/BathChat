import hashlib
import hmac
import json
import os
import secrets
from difflib import SequenceMatcher

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base, engine, get_db
from models import Match, Profile, User
from schemas import AIMatchData, MatchRead, ProfileRead, ProfileUpsert, TokenResponse, UserCreate, UserLogin, UserRead


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


_embedding_model = None
_sentence_transformers_ready = True


def get_embedding_model():
    global _embedding_model, _sentence_transformers_ready
    if not _sentence_transformers_ready:
        return None
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError:
            _sentence_transformers_ready = False
            return None
        # Compact model with good semantic performance for short profile terms.
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def normalize_exact_value(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def exact_overlap_count(items_a: list[str] | None, items_b: list[str] | None) -> int:
    set_a = {normalize_exact_value(v) for v in (items_a or []) if isinstance(v, str) and normalize_exact_value(v)}
    set_b = {normalize_exact_value(v) for v in (items_b or []) if isinstance(v, str) and normalize_exact_value(v)}
    return len(set_a & set_b)


def semantic_text_similarity(text_a: str | None, text_b: str | None) -> float:
    if not text_a or not text_b:
        return 0.0
    model = get_embedding_model()
    if model is None:
        return SequenceMatcher(None, text_a.strip().lower(), text_b.strip().lower()).ratio()
    from sentence_transformers import util as st_util
    vectors = model.encode([text_a.strip(), text_b.strip()], convert_to_tensor=True)
    similarity = float(st_util.cos_sim(vectors[0], vectors[1]).item())
    return max(0.0, min(1.0, similarity))


def semantic_list_similarity(items_a: list[str] | None, items_b: list[str] | None) -> float:
    values_a = [v.strip() for v in (items_a or []) if isinstance(v, str) and v.strip()]
    values_b = [v.strip() for v in (items_b or []) if isinstance(v, str) and v.strip()]
    if not values_a or not values_b:
        return 0.0

    model = get_embedding_model()
    if model is None:
        best_a = [max(SequenceMatcher(None, a.lower(), b.lower()).ratio() for b in values_b) for a in values_a]
        best_b = [max(SequenceMatcher(None, b.lower(), a.lower()).ratio() for a in values_a) for b in values_b]
        score = ((sum(best_a) / len(best_a)) + (sum(best_b) / len(best_b))) / 2.0
        return max(0.0, min(1.0, score))
    from sentence_transformers import util as st_util
    emb_a = model.encode(values_a, convert_to_tensor=True)
    emb_b = model.encode(values_b, convert_to_tensor=True)

    # Pair each item with its best semantic counterpart and average both directions.
    best_a_to_b: list[float] = []
    for vec_a in emb_a:
        best_a_to_b.append(max(float(st_util.cos_sim(vec_a, vec_b).item()) for vec_b in emb_b))

    best_b_to_a: list[float] = []
    for vec_b in emb_b:
        best_b_to_a.append(max(float(st_util.cos_sim(vec_b, vec_a).item()) for vec_a in emb_a))

    forward = sum(best_a_to_b) / len(best_a_to_b) if best_a_to_b else 0.0
    backward = sum(best_b_to_a) / len(best_b_to_a) if best_b_to_a else 0.0
    score = (forward + backward) / 2.0
    return max(0.0, min(1.0, score))


async def get_ai_match_data(user1_profile: Profile, user2_profile: Profile) -> AIMatchData:
    """Placeholder Anthropic integration returning match score, reason, and icebreaker."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    prompt = {
        "user1": {
            "interests": user1_profile.interests,
            "course": user1_profile.course,
            "accommodation": user1_profile.accommodation,
            "ethnicity": user1_profile.ethnicity,
            "gender": user1_profile.gender,
            "spoken_language": user1_profile.spoken_language,
            "societies": user1_profile.societies,
            "goals": user1_profile.goals,
            "bio": user1_profile.bio,
        },
        "user2": {
            "interests": user2_profile.interests,
            "course": user2_profile.course,
            "accommodation": user2_profile.accommodation,
            "ethnicity": user2_profile.ethnicity,
            "gender": user2_profile.gender,
            "spoken_language": user2_profile.spoken_language,
            "societies": user2_profile.societies,
            "goals": user2_profile.goals,
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

    # Fallback scoring uses SentenceTransformer semantic similarity.
    shared_interests = exact_overlap_count(user1_profile.interests, user2_profile.interests)
    shared_societies = exact_overlap_count(user1_profile.societies, user2_profile.societies)

    course_1 = normalize_exact_value(user1_profile.course)
    course_2 = normalize_exact_value(user2_profile.course)
    same_course_exact = bool(course_1 and course_2 and course_1 == course_2)

    interests_similarity = semantic_list_similarity(user1_profile.interests, user2_profile.interests)
    societies_similarity = semantic_list_similarity(user1_profile.societies, user2_profile.societies)
    course_similarity = semantic_text_similarity(user1_profile.course, user2_profile.course)

    score = (
        15.0
        + (interests_similarity * 45.0)
        + (societies_similarity * 25.0)
        + (course_similarity * 15.0)
        + (shared_interests * 8.0)
        + (shared_societies * 7.0)
        + (10.0 if same_course_exact else 0.0)
    )
    score = max(0.0, min(100.0, score))

    reason_parts: list[str] = []
    if shared_interests > 0:
        reason_parts.append(f"{shared_interests} common interest{'s' if shared_interests != 1 else ''}")
    if shared_societies > 0:
        reason_parts.append(f"{shared_societies} common societ{'ies' if shared_societies != 1 else 'y'}")
    if same_course_exact:
        reason_parts.append("same course")

    semantic_note = (
        f"semantic similarity - interests: {int(interests_similarity * 100)}%, "
        f"societies: {int(societies_similarity * 100)}%, course: {int(course_similarity * 100)}%"
    )

    if reason_parts:
        reason = f"You have {', '.join(reason_parts)}; {semantic_note}."
    else:
        reason = f"No exact overlap found, but {semantic_note}."

    icebreaker = "You both seem aligned. Want to swap your favorite student event this term?"
    return AIMatchData(match_score=score, reason=reason, icebreaker=icebreaker)


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add profile fields to profiles table (not to users - they have elo_score and badge_tier in User model)
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS course VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS accommodation VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ethnicity VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS gender VARCHAR(60)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS spoken_language VARCHAR(120)"))
        # Ensure users table has elo_score and badge_tier (defined in User model)
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS elo_score INTEGER NOT NULL DEFAULT 500"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS badge_tier VARCHAR(40) NOT NULL DEFAULT 'bronze'"))

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
        name=payload.name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)





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