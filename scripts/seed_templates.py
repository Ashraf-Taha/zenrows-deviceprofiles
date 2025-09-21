 # no uuid usage

from sqlalchemy import text, select

from app.db.session import get_session
from app.db.models import DeviceType, Visibility, DeviceProfile


def _ensure_profile(sess, profile_id, owner_id, name, device_type, width, height, user_agent, country, headers, is_template, visibility):
    exists = sess.execute(select(DeviceProfile.id).where(DeviceProfile.id == profile_id)).scalar()
    if exists:
        return
    dp = DeviceProfile(
        id=profile_id,
        owner_id=owner_id,
        name=name,
        device_type=device_type,
        width=width,
        height=height,
        user_agent=user_agent,
        country=country,
        custom_headers=headers or {},
        is_template=is_template,
        visibility=visibility,
    )
    sess.add(dp)


def main() -> None:
    owner_id = "usr_templates"
    with get_session() as s:
        s.execute(text("INSERT INTO users(id,email) VALUES (:i,:e) ON CONFLICT (id) DO NOTHING"), {"i": owner_id, "e": "templates@example.com"})
        templates = [
            {
                "id": "tmpl_chrome_win",
                "name": "Chrome on Windows",
                "device_type": DeviceType.desktop,
                "width": 1366,
                "height": 768,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                "country": "us",
            },
            {
                "id": "tmpl_iphone",
                "name": "iPhone Safari",
                "device_type": DeviceType.mobile,
                "width": 390,
                "height": 844,
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
                "country": "gb",
            },
            {
                "id": "tmpl_android",
                "name": "Android Chrome",
                "device_type": DeviceType.mobile,
                "width": 412,
                "height": 915,
                "user_agent": "Mozilla/5.0 (Linux; Android 13; Pixel) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36",
                "country": "de",
            },
        ]
        for t in templates:
            _ensure_profile(
                s,
                t["id"],
                owner_id,
                t["name"],
                t["device_type"],
                t["width"],
                t["height"],
                t["user_agent"],
                t["country"],
                {},
                True,
                Visibility.global_,
            )
        s.commit()


if __name__ == "__main__":
    main()
