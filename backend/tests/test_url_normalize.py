from app.services.url_normalize import normalize_url


def test_normalize_removes_tracking_params():
    result = normalize_url("https://example.com/post/?utm_source=x&id=123")
    assert result.normalized == "https://example.com/post?id=123"
    assert result.domain == "example.com"


def test_normalize_youtube_variants():
    first = normalize_url("https://youtu.be/abc123?si=tracking")
    second = normalize_url("https://www.youtube.com/watch?v=abc123&utm_source=x")
    assert first.normalized == "https://www.youtube.com/watch?v=abc123"
    assert second.normalized == "https://www.youtube.com/watch?v=abc123"


def test_normalize_strips_userinfo():
    result = normalize_url("https://user:pass@example.com/a")
    assert result.normalized == "https://example.com/a"
    assert result.domain == "example.com"
