from app.auth.pipeline import AuthRequest, ApiKeyHeaderValidator, PrefixTransformer, AuthenticateExecutor
from app.auth.service import AuthError
from app.auth.crypto import prefix_from_raw
import pytest


def test_given_missing_key_when_validate_then_error():
    v = ApiKeyHeaderValidator()
    with pytest.raises(AuthError):
        v.validate(AuthRequest(api_key=""))


def test_given_key_when_transform_then_prefix_set():
    t = PrefixTransformer()
    req = t.transform(AuthRequest(api_key="abc"))
    assert req.prefix == prefix_from_raw("abc")


def test_given_no_prefix_when_execute_then_error():
    class DummyRepo:
        def find_by_prefix(self, prefix: str):
            return []

    ex = AuthenticateExecutor(DummyRepo())
    with pytest.raises(AuthError):
        ex.execute(AuthRequest(api_key="abc", prefix=None))
