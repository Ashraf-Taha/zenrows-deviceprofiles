import pytest
from app.profiles.pipeline import VersionsValidator, VersionsRequest, VersionValidator, VersionRequest


def test_given_missing_id_when_versions_validator_then_raises():
    with pytest.raises(ValueError):
        VersionsValidator().validate(VersionsRequest(user_id="u", profile_id=""))


def test_given_invalid_version_when_version_validator_then_raises():
    with pytest.raises(ValueError):
        VersionValidator().validate(VersionRequest(user_id="u", profile_id="p", version=0))

from app.profiles.pipeline import VersionsValidator, VersionsRequest


def test_given_missing_id_when_versions_validator_then_raises():
    v = VersionsValidator()
    with pytest.raises(ValueError):
        v.validate(VersionsRequest(user_id="u", profile_id=""))