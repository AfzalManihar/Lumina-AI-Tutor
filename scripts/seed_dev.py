"""DEVELOPMENT-ONLY demo data: one student with a sample document, a lesson, a quiz and progress events.
Refuses to run when APP_ENV=production. Does not call any external provider (uses lexical hash embeddings and
fixed content), so every value shown in the UI for this user is clearly demo data.

   python scripts/seed_dev.py [--email demo@lumina.local] [--password PW]
"""
import argparse
import asyncio
import secrets

import _common  # noqa: F401
from app.core.config import get_settings
from app.core.security import hash_password, utcnow
from app.db.mongo import create_client, ensure_indexes
from app.rag.embeddings import HashEmbedder
from app.rag.store import MongoVectorStore
from app.services.documents import DocumentService

SAMPLE = ("Photosynthesis converts light energy into chemical energy stored in glucose. "
          "Chloroplasts contain chlorophyll, the green pigment that absorbs light. "
          "The Calvin cycle takes place in the stroma of the chloroplast.")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", default="demo@lumina.local")
    ap.add_argument("--password")
    a = ap.parse_args()
    s = get_settings()
    if s.app_env == "production":
        raise SystemExit("Refusing to seed demo data when APP_ENV=production.")
    client = create_client(s)
    db = client[s.db_name]
    await ensure_indexes(db)
    pw = a.password or secrets.token_urlsafe(10) + "9a"
    if await db.users.find_one({"email": a.email}):
        raise SystemExit(f"{a.email} already exists; delete it first or choose another --email.")
    res = await db.users.insert_one({"email": a.email, "name": "Demo Student", "password_hash": hash_password(pw),
                                     "role": "student", "created_at": utcnow(), "updated_at": utcnow(),
                                     "settings": {"memory_enabled": True, "learning_topic": "Biology"}})
    uid = str(res.inserted_id)
    docs = DocumentService(db, s, HashEmbedder(), MongoVectorStore(db))
    await docs.upload(uid, "demo-biology.txt", "text/plain", SAMPLE.encode())
    await db.quizzes.insert_one({"user_id": uid, "topic": "Photosynthesis", "difficulty": "beginner", "grounded": False,
                                 "sources": {}, "created_at": utcnow(), "attempts": [
                                     {"score": 2, "total": 3, "percent": 66.7, "answers": [0, 1, 2], "created_at": utcnow()}],
                                 "questions": [{"prompt": f"Demo question {i}?", "options": ["A", "B", "C", "D"],
                                                "correct_index": i, "explanation": "Demo.", "cite_ids": []} for i in range(3)]})
    await db.learning_events.insert_one({"user_id": uid, "type": "quiz_attempt", "topic": "Photosynthesis",
                                         "difficulty": "beginner", "score": 2, "total": 3, "percent": 66.7,
                                         "created_at": utcnow()})
    print(f"Seeded demo student.\n  email:    {a.email}\n  password: {pw}\n(DEMO DATA - development only)")
    await client.close()


asyncio.run(main())
