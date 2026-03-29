import hashlib
import hmac
import json
import os
import secrets

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import Base, engine, get_db
from backend.models import Chat, Match, Message, Profile, User
from backend.schemas import (
    AIMatchData,
    ChatMessageCreate,
    ChatMessageRead,
    ConnectionRead,
    GameIdea,
    GameIdeasResponse,
    MatchRead,
    ProfileRead,
    ProfileUpsert,
    TopEloHolderRead,
    TopEloLeaderboardResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserRead,
)

GEMINI_API_KEY = "AIzaSyDNvViMd10UcfDA01Mo0vF9ISXBZpsoIeQ"
GEMINI_MODEL = "gemini-1.5-flash"


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


# SentenceTransformer path intentionally disabled per request.
# _embedding_model = None
# _sentence_transformers_ready = True
# def get_embedding_model():
#     ...


def normalize_exact_value(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def exact_overlap_count(items_a: list[str] | None, items_b: list[str] | None) -> int:
    set_a = {normalize_exact_value(v) for v in (items_a or []) if isinstance(v, str) and normalize_exact_value(v)}
    set_b = {normalize_exact_value(v) for v in (items_b or []) if isinstance(v, str) and normalize_exact_value(v)}
    return len(set_a & set_b)


async def get_user_elo_rank(db: AsyncSession, user: User) -> int:
    result = await db.execute(select(func.count()).where(User.elo_score > user.elo_score))
    higher_count = int(result.scalar_one() or 0)
    return higher_count + 1


def extract_json_payload(raw_text: str) -> dict:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


async def call_gemini_json(prompt: str, fallback: dict) -> dict:
    if not GEMINI_API_KEY:
        return fallback

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        f"?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            text_part = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            if not text_part:
                return fallback
            parsed = extract_json_payload(text_part)
            return parsed if isinstance(parsed, dict) else fallback
    except Exception:
        return fallback


async def get_ai_match_data(user1_profile: Profile, user2_profile: Profile) -> AIMatchData:
    """Gemini-powered match scoring."""

    prompt = {
        "user1": {
            "name": user1_profile.name,
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
            "name": user2_profile.name,
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

    fallback = {
        "match_score": 50.0,
        "reason": "Shared university interests and compatible social goals.",
        "icebreaker": "What is one Bath campus spot you would both recommend?",
    }

    gemini_prompt = (
        "Return ONLY valid JSON object with keys: match_score (0-100 number), reason (string), "
        "icebreaker (string). Use profile compatibility based on interests, course, societies, goals and bio. "
        f"Input profiles: {json.dumps(prompt)}"
    )
    parsed = await call_gemini_json(gemini_prompt, fallback)

    try:
        return AIMatchData(
            match_score=float(parsed.get("match_score", fallback["match_score"])),
            reason=str(parsed.get("reason", fallback["reason"])),
            icebreaker=str(parsed.get("icebreaker", fallback["icebreaker"])),
        )
    except (TypeError, ValueError):
        pass

    # Deterministic fallback if Gemini output is malformed or unavailable.
    shared_interests = exact_overlap_count(user1_profile.interests, user2_profile.interests)
    shared_societies = exact_overlap_count(user1_profile.societies, user2_profile.societies)

    course_1 = normalize_exact_value(user1_profile.course)
    course_2 = normalize_exact_value(user2_profile.course)
    same_course_exact = bool(course_1 and course_2 and course_1 == course_2)

    score = (
        15.0
        + (shared_interests * 12.0)
        + (shared_societies * 10.0)
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

    if reason_parts:
        reason = f"You have {', '.join(reason_parts)}."
    else:
        reason = "No exact overlap found yet, but there is still a chance to connect."

    icebreaker = "You both seem aligned. Want to swap your favorite student event this term?"
    return AIMatchData(match_score=score, reason=reason, icebreaker=icebreaker)


@app.get("/games/ideas/{candidate_id}", response_model=GameIdeasResponse)
async def generate_game_ideas(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GameIdeasResponse:
    candidate = await db.get(User, candidate_id)
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    user_profile = await db.get(Profile, current_user.id)
    candidate_profile = await db.get(Profile, candidate_id)
    if not user_profile or not candidate_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both users must have profiles before generating games",
        )

    profile_context = {
        "user1": {
            "name": user_profile.name,
            "interests": user_profile.interests,
            "course": user_profile.course,
            "societies": user_profile.societies,
            "goals": user_profile.goals,
            "bio": user_profile.bio,
        },
        "user2": {
            "name": candidate_profile.name,
            "interests": candidate_profile.interests,
            "course": candidate_profile.course,
            "societies": candidate_profile.societies,
            "goals": candidate_profile.goals,
            "bio": candidate_profile.bio,
        },
    }

    fallback_games = {
        "games": [
            {
                "game_type": "20 Questions",
                "ai_role": "AI picks an object related to both users' interests and judges guesses.",
                "technical_execution": "Store game_state in games table; each message is checked for win condition.",
            },
            {
                "game_type": "Would You Rather",
                "ai_role": "AI generates funny, polarizing options tailored to both users.",
                "technical_execution": "Save both choices in DB and compute a compatibility delta.",
            },
            {
                "game_type": "Emoji Story",
                "ai_role": "AI gives a prompt and later translates/rates the emoji-only story.",
                "technical_execution": "Persist turns and final AI translation + humour score.",
            },
        ]
    }

    games_prompt = (
        "Return ONLY valid JSON object: {\"games\":[{\"game_type\":...,\"ai_role\":...,\"technical_execution\":...}]} "
        "with exactly 3 games similar in style to: 20 Questions, Would You Rather, Emoji Story. "
        "Tailor ideas to these two users' shared profile attributes. "
        f"Profiles: {json.dumps(profile_context)}"
    )
    parsed = await call_gemini_json(games_prompt, fallback_games)

    raw_games = parsed.get("games", []) if isinstance(parsed, dict) else []
    games: list[GameIdea] = []
    for item in raw_games[:3]:
        if not isinstance(item, dict):
            continue
        games.append(
            GameIdea(
                game_type=str(item.get("game_type", "")),
                ai_role=str(item.get("ai_role", "")),
                technical_execution=str(item.get("technical_execution", "")),
            )
        )

    if len(games) < 3:
        games = [GameIdea(**x) for x in fallback_games["games"]]

    return GameIdeasResponse(games=games)


async def get_connection_match(db: AsyncSession, user_id: int, other_user_id: int) -> Match | None:
    result = await db.execute(
        select(Match).where(
            or_(
                and_(Match.user1_id == user_id, Match.user2_id == other_user_id),
                and_(Match.user1_id == other_user_id, Match.user2_id == user_id),
            )
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_chat(db: AsyncSession, match_id: int) -> Chat:
    result = await db.execute(select(Chat).where(Chat.match_id == match_id))
    chat = result.scalar_one_or_none()
    if chat:
        return chat

    chat = Chat(match_id=match_id)
    db.add(chat)
    await db.flush()
    return chat


async def trim_chat_history_to_last_10(db: AsyncSession, chat_id: int) -> None:
    result = await db.execute(
        select(Message.id)
        .where(Message.chat_id == chat_id)
        .order_by(Message.sent_at.desc(), Message.id.desc())
        .offset(10)
    )
    stale_ids = [row[0] for row in result.all()]
    if stale_ids:
        await db.execute(delete(Message).where(Message.id.in_(stale_ids)))


@app.post("/connections/{candidate_id}", response_model=MatchRead)
async def connect_with_user(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MatchRead:
    if candidate_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot connect with yourself")

    candidate = await db.get(User, candidate_id)
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    user_profile = await db.get(Profile, current_user.id)
    candidate_profile = await db.get(Profile, candidate_id)
    if not user_profile or not candidate_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both users must have profiles before connecting",
        )

    existing = await get_connection_match(db, current_user.id, candidate_id)
    if existing:
        existing.status = "connected"
        match = existing
    else:
        ai_data = await get_ai_match_data(user_profile, candidate_profile)
        user1_id, user2_id = sorted([current_user.id, candidate_id])
        match = Match(
            user1_id=user1_id,
            user2_id=user2_id,
            match_score=ai_data.match_score,
            ai_reason=ai_data.reason,
            ai_icebreaker=ai_data.icebreaker,
            status="connected",
        )
        db.add(match)

    await db.flush()
    await get_or_create_chat(db, match.id)
    await db.commit()
    await db.refresh(match)
    return MatchRead.model_validate(match)


@app.get("/connections", response_model=list[ConnectionRead])
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConnectionRead]:
    result = await db.execute(
        select(Match).where(
            and_(
                or_(Match.user1_id == current_user.id, Match.user2_id == current_user.id),
                Match.status == "connected",
            )
        )
    )
    matches = result.scalars().all()

    items: list[ConnectionRead] = []
    for match in matches:
        other_id = match.user2_id if match.user1_id == current_user.id else match.user1_id
        other_profile = await db.get(Profile, other_id)
        items.append(
            ConnectionRead(
                match_id=match.id,
                user_id=other_id,
                name=other_profile.name if other_profile and other_profile.name else f"User {other_id}",
                status=match.status,
            )
        )
    return items


@app.post("/connections/{connection_user_id}/chat", response_model=ChatMessageRead)
async def send_message_to_connection(
    connection_user_id: int,
    payload: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageRead:
    if connection_user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot chat with yourself")

    connection = await get_connection_match(db, current_user.id, connection_user_id)
    if not connection or connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not connected with this user")

    chat = await get_or_create_chat(db, connection.id)
    message = Message(
        chat_id=chat.id,
        sender_id=current_user.id,
        content=payload.content.strip(),
        message_type=payload.message_type,
    )
    db.add(message)
    await db.flush()

    await trim_chat_history_to_last_10(db, chat.id)
    await db.commit()
    await db.refresh(message)
    return ChatMessageRead.model_validate(message)


@app.get("/connections/{connection_user_id}/chat", response_model=list[ChatMessageRead])
async def get_recent_chat_history(
    connection_user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessageRead]:
    if connection_user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot chat with yourself")

    connection = await get_connection_match(db, current_user.id, connection_user_id)
    if not connection or connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not connected with this user")

    chat = await get_or_create_chat(db, connection.id)
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat.id)
        .order_by(Message.sent_at.desc(), Message.id.desc())
        .limit(10)
    )
    latest = result.scalars().all()
    return [ChatMessageRead.model_validate(item) for item in reversed(latest)]


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
    elo_rank = await get_user_elo_rank(db, current_user)
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
        elo_rank=elo_rank,
    )


@app.get("/profiles/me", response_model=ProfileRead)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    profile = await db.get(Profile, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    elo_rank = await get_user_elo_rank(db, current_user)
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
        elo_rank=elo_rank,
    )


@app.get("/leaderboard/top-elo", response_model=TopEloLeaderboardResponse)
async def get_top_elo_holders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TopEloLeaderboardResponse:
    _ = current_user
    result = await db.execute(select(User).order_by(User.elo_score.desc(), User.id.asc()).limit(5))
    users = result.scalars().all()

    holders: list[TopEloHolderRead] = []
    for user in users:
        rank = await get_user_elo_rank(db, user)
        profile = await db.get(Profile, user.id)
        holders.append(
            TopEloHolderRead(
                user_id=user.id,
                name=profile.name if profile and profile.name else f"User {user.id}",
                elo_score=user.elo_score,
                badge_tier=user.badge_tier,
                elo_rank=rank,
            )
        )

    return TopEloLeaderboardResponse(top_holders=holders)


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


def local_discovery_score(user_profile: Profile, candidate_profile: Profile) -> AIMatchData:
    shared_interests = exact_overlap_count(user_profile.interests, candidate_profile.interests)
    shared_societies = exact_overlap_count(user_profile.societies, candidate_profile.societies)
    same_course = bool(
        normalize_exact_value(user_profile.course)
        and normalize_exact_value(user_profile.course) == normalize_exact_value(candidate_profile.course)
    )

    score = 20 + (shared_interests * 12) + (shared_societies * 10) + (8 if same_course else 0)
    score = float(max(0, min(100, score)))

    parts: list[str] = []
    if shared_interests:
        parts.append(f"{shared_interests} common interest{'s' if shared_interests != 1 else ''}")
    if shared_societies:
        parts.append(f"{shared_societies} common societ{'ies' if shared_societies != 1 else 'y'}")
    if same_course:
        parts.append("same course")

    reason = f"You share {', '.join(parts)}." if parts else "Potential match based on profile similarity."
    icebreaker = "Say hi and ask what they are most excited about this term at Bath."
    return AIMatchData(match_score=score, reason=reason, icebreaker=icebreaker)


@app.get("/discovery/matches", response_model=list[MatchRead])
async def list_my_matches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MatchRead]:
    user_profile = await db.get(Profile, current_user.id)
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user must have a profile before discovery",
        )

    existing_result = await db.execute(
        select(Match).where(or_(Match.user1_id == current_user.id, Match.user2_id == current_user.id))
    )
    existing_matches = existing_result.scalars().all()
    existing_map: dict[tuple[int, int], Match] = {
        (min(m.user1_id, m.user2_id), max(m.user1_id, m.user2_id)): m for m in existing_matches
    }

    candidates_result = await db.execute(select(Profile).where(Profile.user_id != current_user.id))
    candidates = candidates_result.scalars().all()

    has_new_records = False
    has_updated_records = False
    for candidate_profile in candidates:
        pair_key = (min(current_user.id, candidate_profile.user_id), max(current_user.id, candidate_profile.user_id))
        existing_match = existing_map.get(pair_key)
        if existing_match is not None:
            if existing_match.status == "suggested":
                ai_data = local_discovery_score(user_profile, candidate_profile)
                existing_match.match_score = ai_data.match_score
                existing_match.ai_reason = ai_data.reason
                existing_match.ai_icebreaker = ai_data.icebreaker
                has_updated_records = True
            continue

        ai_data = local_discovery_score(user_profile, candidate_profile)
        match = Match(
            user1_id=pair_key[0],
            user2_id=pair_key[1],
            match_score=ai_data.match_score,
            ai_reason=ai_data.reason,
            ai_icebreaker=ai_data.icebreaker,
            status="suggested",
        )
        db.add(match)
        has_new_records = True

    if has_new_records or has_updated_records:
        await db.commit()

    top_result = await db.execute(
        select(Match)
        .where(
            and_(
                or_(Match.user1_id == current_user.id, Match.user2_id == current_user.id),
                Match.status == "suggested",
            )
        )
        .order_by(Match.match_score.desc(), Match.id.desc())
        .limit(3)
    )
    top_matches = top_result.scalars().all()
    return [MatchRead.model_validate(item) for item in top_matches]