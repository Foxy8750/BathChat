import argparse
import asyncio
import hashlib
import json
import random
import secrets
from dataclasses import dataclass

import asyncpg
from sqlalchemy.engine.url import make_url

from backend.database import DATABASE_URL


@dataclass
class DemoSeedData:
    first_name: str
    last_name: str
    interests: list[str]
    societies: list[str]
    course: str
    accommodation: str
    ethnicity: str
    gender: str
    spoken_language: str
    goals: str
    bio: str


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${digest.hex()}"


def badge_for_exp(exp_points: int) -> str:
    if exp_points >= 1200:
        return "platinum"
    if exp_points >= 1000:
        return "gold"
    if exp_points >= 800:
        return "silver"
    if exp_points >= 500:
        return "bronze"
    return "iron"


def random_seed_data() -> DemoSeedData:
    first_names = [
        "Alex", "Jamie", "Sam", "Taylor", "Jordan", "Morgan", "Casey", "Avery", "Riley", "Drew",
        "Kai", "Noah", "Luca", "Mia", "Emma", "Olivia", "Sophia", "Ava", "Ivy", "Zoe",
    ]
    last_names = [
        "Smith", "Jones", "Brown", "Taylor", "Williams", "Davis", "Wilson", "Clark", "Lewis", "Walker",
        "Hall", "Young", "King", "Wright", "Scott", "Green", "Baker", "Adams", "Hill", "Parker",
    ]
    interest_pool = [
        "coffee", "gaming", "hiking", "football", "basketball", "chess", "music", "cinema", "coding",
        "design", "photography", "cooking", "reading", "gym", "yoga", "running", "travel", "fishing",
        "art", "anime", "mathematics", "ai", "machine learning", "startups", "board games", "tennis",
    ]
    society_pool = [
        "AI Society", "Entrepreneurship Society", "Debate Society", "Film Society", "Music Society",
        "Chess Club", "Hiking Club", "Cooking Club", "Photography Society", "International Students Society",
        "Sports Union", "Dance Society", "Gaming Society", "Book Club", "Startup Society",
    ]
    courses = [
        "Computer Science", "Mathematics", "Economics", "Mechanical Engineering", "Business", "Physics",
        "Psychology", "Architecture", "Biology", "Data Science",
    ]
    accommodations = ["Westwood", "Brendon Court", "Polden", "Marlborough", "Private Rental", "City Centre"]
    ethnicities = ["Asian", "White", "Black", "Mixed", "Middle Eastern", "Latino", "Other"]
    genders = ["Male", "Female", "Non-binary", "Prefer not to say"]
    languages = ["English", "Mandarin", "Spanish", "Hindi", "Arabic", "French", "German", "Korean"]
    goals_pool = [
        "Find study buddies", "Meet new friends", "Build startup ideas", "Stay active and social",
        "Practice speaking confidence", "Explore Bath together", "Prepare for placements", "Join hackathons",
    ]
    bio_pool = [
        "Always up for coffee and coding.", "Love spontaneous adventures and good food.",
        "Trying to balance study and fun this term.", "Looking for people to build cool projects with.",
        "Gym in the morning, Netflix at night.", "Big fan of board games and deep conversations.",
        "Enjoy football, music, and discovering hidden cafes.", "Into AI, product ideas, and meeting new people.",
    ]

    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    interests = random.sample(interest_pool, k=random.randint(3, 6))
    societies = random.sample(society_pool, k=random.randint(1, 3))

    return DemoSeedData(
        first_name=first_name,
        last_name=last_name,
        interests=interests,
        societies=societies,
        course=random.choice(courses),
        accommodation=random.choice(accommodations),
        ethnicity=random.choice(ethnicities),
        gender=random.choice(genders),
        spoken_language=random.choice(languages),
        goals=random.choice(goals_pool),
        bio=random.choice(bio_pool),
    )


async def seed_demo_users(count: int) -> None:
    created = 0
    password_hash = hash_password("DemoPass123!")

    db_url = make_url(DATABASE_URL)
    conn = await asyncpg.connect(
        host=db_url.host,
        port=db_url.port,
        user=db_url.username,
        password=db_url.password,
        database=db_url.database,
        ssl="require",
        timeout=20,
    )

    try:
        async with conn.transaction():
            for _ in range(count):
                seed = random_seed_data()
                full_name = f"{seed.first_name} {seed.last_name}"
                suffix = secrets.token_hex(4)
                email = f"demo.{seed.first_name.lower()}.{seed.last_name.lower()}.{suffix}@bath.ac.uk"

                existing = await conn.fetchval("SELECT id FROM users WHERE email=$1", email)
                if existing is not None:
                    continue

                exp_points = random.randint(350, 1300)
                badge_tier = badge_for_exp(exp_points)

                user_id = await conn.fetchval(
                    """
                    INSERT INTO users (email, name, hashed_password, exp_points, badge_tier)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    email,
                    full_name,
                    password_hash,
                    exp_points,
                    badge_tier,
                )

                await conn.execute(
                    """
                    INSERT INTO profiles (
                        user_id, name, interests, course, accommodation, ethnicity,
                        gender, spoken_language, societies, goals, bio
                    )
                    VALUES ($1, $2, $3::json, $4, $5, $6, $7, $8, $9::json, $10, $11)
                    """,
                    user_id,
                    full_name,
                    json.dumps(seed.interests),
                    seed.course,
                    seed.accommodation,
                    seed.ethnicity,
                    seed.gender,
                    seed.spoken_language,
                    json.dumps(seed.societies),
                    seed.goals,
                    seed.bio,
                )
                created += 1
    finally:
        await conn.close()

    print(f"Seed complete: created {created} demo users/profiles.")
    print("Demo login password for seeded users: DemoPass123!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo users and profiles for matching demos")
    parser.add_argument("--count", type=int, default=50, help="Number of demo users to create")
    args = parser.parse_args()

    asyncio.run(seed_demo_users(args.count))


if __name__ == "__main__":
    main()
