import uuid

from sqlalchemy import text

from app.auth.crypto import generate_api_key, hash_key
from app.db.session import get_session


def main() -> None:
    raw, prefix = generate_api_key()
    uid = f"usr_{uuid.uuid4().hex[:10]}"
    kid = f"key_{uuid.uuid4().hex[:10]}"
    with get_session() as s:
        s.execute(text("INSERT INTO users(id,email) VALUES (:i,:e) ON CONFLICT (id) DO NOTHING"), {"i": uid, "e": f"{uid}@example.com"})
        s.execute(
            text(
                """
                INSERT INTO api_keys(id,user_id,key_hash,key_prefix,name)
                VALUES (:id,:uid,:hash,:prefix,:name)
                """
            ),
            {"id": kid, "uid": uid, "hash": hash_key(raw), "prefix": prefix, "name": "seed"},
        )
        s.commit()
    print(raw)


if __name__ == "__main__":
    main()
