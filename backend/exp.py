from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import User

def get_badge_tier_from_xp(xp_points: int) -> str:
    if xp_points >= 800:
        return "gold"
    if xp_points >= 500:
        return "silver"
    return "bronze"

async def award_xp(
    db: AsyncSession,
    user: User,
    points: int,
) -> None:
    user.elo_score = (user.elo_score or 0) + points
    user.badge_tier = get_badge_tier_from_xp(user.elo_score)
    await db.commit()
    await db.refresh(user)

    