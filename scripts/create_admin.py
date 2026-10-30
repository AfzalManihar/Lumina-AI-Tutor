"""Create an administrator or promote an existing user.   python scripts/create_admin.py EMAIL [--password PW]

Run from the repo root with the backend virtualenv active. The password is read from --password or prompted
(never echoed, never logged). Registration through the public API always creates students only."""
import argparse
import asyncio
import getpass

import _common  # noqa: F401
from app.core.config import get_settings
from app.core.security import hash_password, utcnow
from app.db.mongo import create_client, ensure_indexes
from app.services.auth import validate_password_strength


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    ap.add_argument("--password")
    a = ap.parse_args()
    s = get_settings()
    client = create_client(s)
    db = client[s.db_name]
    await ensure_indexes(db)
    email = a.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if user:
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"role": "admin", "updated_at": utcnow()}})
        print(f"Promoted existing user {email} to admin.")
    else:
        pw = a.password or getpass.getpass("New admin password: ")
        validate_password_strength(pw)
        await db.users.insert_one({"email": email, "name": "Administrator", "password_hash": hash_password(pw),
                                   "role": "admin", "created_at": utcnow(), "updated_at": utcnow(),
                                   "settings": {"memory_enabled": s.memory_enabled, "learning_topic": ""}})
        print(f"Created admin {email}.")
    await client.close()


asyncio.run(main())
