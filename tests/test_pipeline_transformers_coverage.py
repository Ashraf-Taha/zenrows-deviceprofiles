import pytest

from app.profiles.pipeline import ListRequest, ListRequestTransformer, VersionValidator, VersionRequest
from app.profiles.pipeline import VersionsPageValidator, VersionsPageRequest
import base64


def test_list_request_transformer_invalid_cursor():
    tr = ListRequestTransformer()
    # bad base64 triggers ValueError("invalid_cursor")
    with pytest.raises(ValueError):
        tr.transform(ListRequest(user_id="u", cursor="notb64"))


def test_list_request_transformer_b64_without_pipe():
    tr = ListRequestTransformer()
    token = base64.b64encode(b"no-sep").decode("utf-8")
    with pytest.raises(ValueError):
        tr.transform(ListRequest(user_id="u", cursor=token))


def test_version_validator_invalid():
    with pytest.raises(ValueError):
        VersionValidator().validate(VersionRequest(user_id="u", profile_id="p", version=0))


def test_version_validator_missing_id():
    with pytest.raises(ValueError):
        VersionValidator().validate(VersionRequest(user_id="u", profile_id="", version=1))


def test_versions_page_validator_missing_id():
    with pytest.raises(ValueError):
        VersionsPageValidator().validate(VersionsPageRequest(user_id="u", profile_id=""))