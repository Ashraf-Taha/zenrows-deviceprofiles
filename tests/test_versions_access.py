import os
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_app
from app.auth.crypto import generate_api_key, hash_key


def test_given_missing_auth_when_get_versions_then_401(seed_env):
    app = create_app()
    client = TestClient(app)
    r = client.get("/v1/device-profiles/prof_x/versions")
    assert r.status_code == 401


def test_given_global_template_owned_by_other_when_get_versions_then_allowed(seed_env):
    raw1, uid1 = seed_env
    app = create_app()
    client = TestClient(app)

    body = {
        "name": "Global Tmpl",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
        "is_template": True,
        "visibility": "global",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw1})
    assert r.status_code == 200
    pid = r.json()["id"]

    raw2, prefix2 = generate_api_key()
    uid2 = f"usr_{uuid.uuid4().hex[:8]}"
    kid2 = f"key_{uuid.uuid4().hex[:8]}"
    eng = create_engine(os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        conn.execute(text("INSERT INTO users(id,email) VALUES (:i,:e)"), {"i": uid2, "e": f"{uid2}@x.z"})
        conn.execute(
            text("INSERT INTO api_keys(id,user_id,key_hash,key_prefix,name) VALUES (:id,:uid,:hash,:prefix,'t')"),
            {"id": kid2, "uid": uid2, "hash": hash_key(raw2), "prefix": prefix2},
        )

    r2 = client.get(f"/v1/device-profiles/{pid}/versions", headers={"X-API-Key": raw2})
    assert r2.status_code == 200
    data = r2.json()
    assert isinstance(data, list)
    assert len(data) >= 1