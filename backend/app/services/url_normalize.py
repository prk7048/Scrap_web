from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "si"}


@dataclass(frozen=True)
class NormalizedUrl:
    original: str
    normalized: str
    domain: str


def normalize_url(url: str) -> NormalizedUrl:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    host = (parsed.hostname or "").lower()
    port = parsed.port
    default_port = (scheme.lower() == "https" and port == 443) or (scheme.lower() == "http" and port == 80)
    netloc = host if port is None or default_port else f"{host}:{port}"
    domain = host.removeprefix("www.")
    path = parsed.path or ""

    if host == "youtu.be":
        video_id = path.strip("/")
        normalized = f"https://www.youtube.com/watch?v={video_id}"
        return NormalizedUrl(original=url, normalized=normalized, domain="youtube.com")

    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"} and path == "/watch":
        params = dict(parse_qsl(parsed.query, keep_blank_values=False))
        video_id = params.get("v")
        if video_id:
            return NormalizedUrl(
                original=url,
                normalized=f"https://www.youtube.com/watch?v={video_id}",
                domain="youtube.com",
            )

    filtered = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not key.startswith(TRACKING_PREFIXES) and key not in TRACKING_KEYS
    ]
    query = urlencode(filtered)
    path = path.rstrip("/") if path != "/" else ""
    normalized = urlunparse((scheme.lower(), netloc.removeprefix("www."), path, "", query, ""))
    return NormalizedUrl(original=url, normalized=normalized, domain=domain)
