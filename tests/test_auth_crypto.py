from app.auth.crypto import hash_key, verify_key, generate_api_key


def test_given_hashed_key_when_verify_with_same_raw_then_true():
    raw, _ = generate_api_key()
    h = hash_key(raw)
    assert verify_key(h, raw) is True


def test_given_hashed_key_when_verify_with_different_raw_then_false():
    raw, _ = generate_api_key()
    h = hash_key(raw)
    other, _ = generate_api_key()
    assert verify_key(h, other) is False
