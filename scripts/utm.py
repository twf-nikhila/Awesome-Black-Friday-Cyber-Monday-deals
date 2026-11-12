"""Tag outbound deal links with UTM params so makers can see traffic from this list.

Links that already carry their own utm_* params are left alone, so we never
overwrite a maker's tracking. Links we tagged earlier only get their medium
swapped (README links use utm_medium=github, the website uses utm_medium=website).
"""
import re
from urllib.parse import parse_qsl, urlsplit

SOURCE = "awesome-black-friday-deals"
CAMPAIGN = "bfcm2026"
SKIP_HOSTS = ("github.com", "img.shields.io", "twf-nikhila.github.io")


def add_utm(url, medium):
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if parts.scheme not in ("http", "https") or any(host == h or host.endswith("." + h) for h in SKIP_HOSTS):
        return url
    params = dict((k.lower(), v) for k, v in parse_qsl(parts.query, keep_blank_values=True))
    if params.get("utm_source") == SOURCE:
        return re.sub(r"([?&]utm_medium=)[^&#]*", rf"\g<1>{medium}", url)
    if any(k.startswith("utm_") for k in params):
        return url
    base, hash_, fragment = url.partition("#")
    sep = "&" if parts.query else ("" if base.endswith("?") else "?")
    return f"{base}{sep}utm_source={SOURCE}&utm_medium={medium}&utm_campaign={CAMPAIGN}{hash_}{fragment}"
