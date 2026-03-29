import hashlib
import hmac
import json
import math
import os
import secrets
from typing import Iterable

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import httpx
from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import Base, engine, get_db
from backend.exp import award_xp
from backend.models import Chat, FriendRequest, Match, Message, Profile, User
from backend.schemas import (
    AIMatchData,
    ChatMessageCreate,
    ChatMessageRead,
    ConnectionRead,
    MatchRead,
    ProfileRead,
    ProfileUpsert,
    TokenResponse,
    TopExpHolderRead,
    TopExpLeaderboardResponse,
    UserCreate,
    UserLogin,
    UserRead,
)

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_APP_URL = os.getenv("OPENROUTER_APP_URL", "http://localhost")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "BathChat")

app = FastAPI(title="BathChat API")

DISCOVERY_SHORTLIST_SIZE = 10
DISCOVERY_RETURN_SIZE = 3
EXP_REWARD_FRIEND_REQUEST_SENT = 5
EXP_REWARD_CONNECTED = 10
EXP_REWARD_CHAT_SENT = 2


def get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]

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
    set_a = {normalize_exact_value(v) for v in (items_a or []) if isinstance(v, str) and normalize_exact_value(v)}
    set_b = {normalize_exact_value(v) for v in (items_b or []) if isinstance(v, str) and normalize_exact_value(v)}
    return len(set_a & set_b)


async def get_user_exp_rank(db: AsyncSession, user: User) -> int:
    result = await db.execute(select(func.count()).where(User.exp_points > user.exp_points))
    higher_count = int(result.scalar_one() or 0)
    return higher_count + 1


def clean_list(values: Iterable[str] | None) -> list[str]:
    return [v.strip() for v in (values or []) if v and v.strip()]


def ai_profile_payload(profile: Profile) -> dict:
    return {
        "name": profile.name,
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


async def embedding_similarity(text1: str, text2: str) -> float:
    _ = text1, text2
    return 0.0


async def compute_match_score(user1_profile: Profile, user2_profile: Profile) -> float:
    local = local_discovery_score(user1_profile, user2_profile)
    return local.match_score


def extract_json_payload(raw_text: str) -> dict | None:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
        return None


async def call_openrouter_json(prompt: str, temperature: float = 0.2) -> dict | None:
    if not OPENROUTER_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_APP_URL,
        "X-OpenRouter-Title": OPENROUTER_APP_TITLE,
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(OPENROUTER_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if not content:
                return None
            return extract_json_payload(content)
    except Exception:
        return None


async def get_ai_match_data(user1_profile: Profile, user2_profile: Profile) -> AIMatchData:
    fallback = local_discovery_score(user1_profile, user2_profile)

    prompt = (
        "Return ONLY valid JSON object with keys: match_score (0-100 number), reason (string), "
        "icebreaker (string).\n"
        "Use profile compatibility based on interests, course, societies, goals, language and bio.\n"
        "Keep reason to one sentence, warm and non-romantic. Keep icebreaker to one sentence.\n"
        f"Student 1: {json.dumps(ai_profile_payload(user1_profile), ensure_ascii=True)}\n"
        f"Student 2: {json.dumps(ai_profile_payload(user2_profile), ensure_ascii=True)}\n"
        f"Baseline local score: {fallback.match_score:.1f}"
    )

    parsed = await call_openrouter_json(prompt)
    if not parsed:
        return fallback

    try:
        score = float(parsed.get("match_score", fallback.match_score))
        score = max(0.0, min(100.0, score))
    except Exception:
        score = fallback.match_score

    reason = str(parsed.get("reason", "")).strip() or fallback.reason
    icebreaker = str(parsed.get("icebreaker", "")).strip() or fallback.icebreaker
    return AIMatchData(match_score=score, reason=reason, icebreaker=icebreaker)


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

    await award_xp(db, current_user, EXP_REWARD_CONNECTED, "Connected with another user")
    await award_xp(db, candidate, EXP_REWARD_CONNECTED, "Connected with another user")

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

    await award_xp(db, current_user, EXP_REWARD_CHAT_SENT, "Sent a chat message")

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

        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS name VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS course VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS accommodation VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ethnicity VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS gender VARCHAR(60)"))
        await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS spoken_language VARCHAR(120)"))

        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS exp_points INTEGER NOT NULL DEFAULT 500"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS badge_tier VARCHAR(40) NOT NULL DEFAULT 'bronze'"))
        await conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'users' AND column_name = 'elo_score'
                    ) THEN
                        UPDATE users
                        SET exp_points = elo_score
                        WHERE exp_points = 500 AND elo_score <> 500;
                    END IF;
                END
                $$;
                """
            )
        )
        await conn.execute(
            text(
                """
                UPDATE users
                SET badge_tier = CASE
                    WHEN exp_points >= 1300 THEN 'diamond'
                    WHEN exp_points >= 1100 THEN 'platinum'
                    WHEN exp_points >= 900 THEN 'gold'
                    WHEN exp_points >= 700 THEN 'silver'
                    ELSE 'bronze'
                END;
                """
            )
        )

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
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email.strip().lower()))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

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
        exp_points=user.exp_points,
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
        exp_points=current_user.exp_points,
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

    exp_rank = await get_user_exp_rank(db, current_user)
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
        exp_points=current_user.exp_points,
        badge_tier=current_user.badge_tier,
        exp_rank=exp_rank,
    )


@app.get("/profiles/me", response_model=ProfileRead)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    profile = await db.get(Profile, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    exp_rank = await get_user_exp_rank(db, current_user)
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
        exp_points=current_user.exp_points,
        badge_tier=current_user.badge_tier,
        exp_rank=exp_rank,
    )


@app.get("/leaderboard/top-exp", response_model=TopExpLeaderboardResponse)
async def get_top_exp_holders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TopExpLeaderboardResponse:
    _ = current_user
    result = await db.execute(select(User).order_by(User.exp_points.desc(), User.id.asc()).limit(5))
    users = result.scalars().all()

    holders: list[TopExpHolderRead] = []
    for user in users:
        rank = await get_user_exp_rank(db, user)
        profile = await db.get(Profile, user.id)
        holders.append(
            TopExpHolderRead(
                user_id=user.id,
                name=profile.name if profile and profile.name else f"User {user.id}",
                exp_points=user.exp_points,
                badge_tier=user.badge_tier,
                exp_rank=rank,
            )
        )

    return TopExpLeaderboardResponse(top_holders=holders)


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
    user_profile = await db.get(Profile, current_user.id)
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user must have a profile before discovery",
        )

    existing_result = await db.execute(
        select(Match).where(
            or_(Match.user1_id == current_user.id, Match.user2_id == current_user.id)
        )
    )
    existing_matches = existing_result.scalars().all()

    connected_user_ids: set[int] = set()
    for item in existing_matches:
        if item.status != "connected":
            continue
        other_id = item.user2_id if item.user1_id == current_user.id else item.user1_id
        connected_user_ids.add(other_id)

    candidate_result = await db.execute(select(Profile).where(Profile.user_id != current_user.id))
    candidates = candidate_result.scalars().all()

    # Run AI matching for all eligible candidates (no local ranking).
    ai_ranked_matches: list[MatchRead] = []
    for candidate_profile in candidates:
        candidate_id = candidate_profile.user_id
        if candidate_id in connected_user_ids:
            continue
        ai_ranked_matches.append(
            await discover_match(
                candidate_id=candidate_id,
                current_user=current_user,
                db=db,
            )
        )

    ai_ranked_matches.sort(key=lambda m: (m.match_score, m.id), reverse=True)
    return ai_ranked_matches[:DISCOVERY_RETURN_SIZE]


@app.post("/messages/send")
async def send_message_for_xp(
    recipient_id: int,
    content: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    recipient = await db.get(User, recipient_id)
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")

    if len(content.strip()) >= 10:
        await award_xp(db, current_user, EXP_REWARD_CHAT_SENT, "Sent a chat message")

    return {
        "detail": "Message sent",
        "exp_points": current_user.exp_points,
        "badge_tier": current_user.badge_tier,
    }


@app.post("/friends/request/{receiver_id}")
async def send_friend_request(
    receiver_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if receiver_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot friend yourself")

    receiver = await db.get(User, receiver_id)
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")

    existing = await db.execute(
        select(FriendRequest).where(
            or_(
                and_(
                    FriendRequest.sender_id == current_user.id,
                    FriendRequest.receiver_id == receiver_id,
                ),
                and_(
                    FriendRequest.sender_id == receiver_id,
                    FriendRequest.receiver_id == current_user.id,
                ),
            )
        )
    )
    old_request = existing.scalar_one_or_none()
    if old_request:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Friend request already exists")

    request = FriendRequest(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        status="pending",
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)

    await award_xp(db, current_user, EXP_REWARD_FRIEND_REQUEST_SENT, "Sent a friend request")

    return {"detail": "Friend request sent", "request_id": request.id}


@app.post("/friends/request/{request_id}/accept")
async def accept_friend_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(FriendRequest).where(FriendRequest.id == request_id))
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Friend request not found")
    if request.receiver_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if request.status == "accepted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already accepted")

    sender = await db.get(User, request.sender_id)
    receiver = await db.get(User, request.receiver_id)
    if not sender or not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    request.status = "accepted"

    match = await get_connection_match(db, sender.id, receiver.id)
    if not match:
        sender_profile = await db.get(Profile, sender.id)
        receiver_profile = await db.get(Profile, receiver.id)

        if not sender_profile or not receiver_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both users must have profiles before connecting",
            )

        ai_data = await get_ai_match_data(sender_profile, receiver_profile)
        user1_id, user2_id = sorted([sender.id, receiver.id])
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
    else:
        match.status = "connected"

    await get_or_create_chat(db, match.id)
    await db.commit()

    await award_xp(db, sender, EXP_REWARD_CONNECTED, "Friend request accepted and connected")
    await award_xp(db, receiver, EXP_REWARD_CONNECTED, "Accepted friend request and connected")

    return {"detail": "Friend request accepted"}
