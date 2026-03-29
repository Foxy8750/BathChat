from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import ExpLog, User

BASE_EXP = 500
TIER_STEP = 200

EXP_BADGE_TIERS: list[tuple[int, str]] = [
    (BASE_EXP + (4 * TIER_STEP), "diamond"),
    (BASE_EXP + (3 * TIER_STEP), "platinum"),
    (BASE_EXP + (2 * TIER_STEP), "gold"),
    (BASE_EXP + TIER_STEP, "silver"),
    (BASE_EXP, "bronze"),
]

def get_badge_tier_from_xp(xp_points: int) -> str:
    for threshold, tier in EXP_BADGE_TIERS:
        if xp_points >= threshold:
            return tier
    return "bronze"

async def award_xp(
    db: AsyncSession,
    user: User,
    points: int,
    reason: str,
) -> None:
    if points <= 0:
        return

    user.exp_points = (user.exp_points or 0) + points
    user.badge_tier = get_badge_tier_from_xp(user.exp_points)
    db.add(
        ExpLog(
            user_id=user.id,
            points=points,
            reason=reason,
        )
    )
    await db.commit()
    await db.refresh(user)

    