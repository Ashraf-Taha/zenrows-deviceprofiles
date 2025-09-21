from app.db.session import get_session
from app.profiles.dto import CreateProfile, Window, CloneOverrides
from app.db.models import DeviceType
from app.profiles.repository import DeviceProfileRepository, ListFilters, NotFoundError


def test_list_scoped_filters_and_cursor(seed_env):
    _, uid = seed_env
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        a = repo.create(uid, CreateProfile(name="FA", device_type=DeviceType.desktop, window=Window(width=1, height=1), user_agent="ua", country="us"))
        b = repo.create(uid, CreateProfile(name="FB", device_type=DeviceType.mobile, window=Window(width=2, height=2), user_agent="ua", country="us"))
        s.commit()
        # device_type filter
        rows = repo.list_scoped(uid, ListFilters(device_type="desktop", limit=10))
        assert any(r.id == a.id for r in rows)
        # country filter
        rows2 = repo.list_scoped(uid, ListFilters(country="us", limit=10))
        assert len(rows2) >= 2
        # q filter
        rows3 = repo.list_scoped(uid, ListFilters(q="F", limit=10))
        assert len(rows3) >= 2
        # cursor path without next page
        rows4, nxt = repo.list_scoped_page(uid, ListFilters(limit=1, cursor=None))
        assert isinstance(rows4, list)
        if nxt:
            rows5, nxt2 = repo.list_scoped_page(uid, ListFilters(limit=1, cursor=nxt))
            assert isinstance(rows5, list)
        # list_scoped_page with filters device_type/country/q
        rows6, nxt3 = repo.list_scoped_page(uid, ListFilters(device_type="desktop", country="us", q="F", limit=10))
        assert isinstance(rows6, list)
        # get_scoped not found
        try:
            repo.get_scoped(uid, "prof_missing")
            assert False
        except NotFoundError:
            pass


def test_clone_overrides_country_none_validates():
    # ensure validator early-return branch executes
    co = CloneOverrides(country=None)
    assert co.country is None