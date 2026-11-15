"""URL canonicalization, tracking-parameter stripping, and SSRF guards."""

from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Common tracking / analytics query parameters to strip during normalization.
TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "utm_name",
        "fbclid",
        "gclid",
        "gclsrc",
        "dclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "igshid",
        "ref",
        "ref_src",
        "ref_url",
        "source",
        "ncid",
        "cmpid",
        "sr_share",
        "sref",
        "spm",
        "sc_channel",
        "sc_campaign",
        "sc_geo",
        "sc_outcome",
        "si",
        "mkt_tok",
        "_hsenc",
        "_hsmi",
        "hsa_cam",
        "hsa_grp",
        "hsa_mt",
        "hsa_src",
        "hsa_ad",
        "hsa_acc",
        "hsa_net",
        "hsa_kw",
        "hsa_tgt",
        "hsa_ver",
    }
)

_TRACKING_PREFIXES = ("utm_", "hsa_", "pk_", "mtm_", "oly_")

HN_ITEM_RE = re.compile(
    r"^https?://(www\.)?news\.ycombinator\.com/item\?id=\d+",
    re.IGNORECASE,
)


class UnsafeURLError(ValueError):
    """Raised when a URL is rejected for SSRF or policy reasons."""


def is_hn_discussion_url(url: str) -> bool:
    return bool(HN_ITEM_RE.match(url.strip()))


def strip_tracking_params(url: str) -> str:
    """Remove common tracking query parameters while preserving other query data."""
    parsed = urlparse(url.strip())
    if not parsed.query:
        return url.strip()

    kept: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lower = key.lower()
        if lower in TRACKING_PARAMS:
            continue
        if any(lower.startswith(prefix) for prefix in _TRACKING_PREFIXES):
            continue
        kept.append((key, value))

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(kept, doseq=True),
            "",  # drop fragment
        )
    )


def canonicalize_url(url: str) -> str:
    """
    Produce a stable canonical URL for deduplication.

    - Lowercase scheme/host
    - Strip tracking params and fragments
    - Remove default ports
    - Collapse empty path to "/"
    - Remove trailing slash except for root
    """
    cleaned = strip_tracking_params(url.strip())
    parsed = urlparse(cleaned)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"URL missing scheme or host: {url!r}")

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeURLError(f"Unsupported URL scheme: {scheme}")

    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def article_id_for_url(canonical_url: str) -> str:
    """Stable article identifier derived from the canonical URL."""
    digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
    return digest[:32]


def _hostname_is_blocked(hostname: str) -> bool:
    host = hostname.lower().strip("[]")
    if host in {"localhost", "localhost.localdomain"}:
        return True
    if host.endswith(".localhost") or host.endswith(".local"):
        return True
    return False


def _ip_is_unsafe(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (ip.version == 4 and ip in ipaddress.ip_network("169.254.0.0/16"))
        or (ip.version == 6 and ip in ipaddress.ip_network("fc00::/7"))
        or (ip.version == 4 and str(ip).startswith("100.64."))  # CGNAT
    )


def validate_public_http_url(url: str, *, resolve_dns: bool = True) -> str:
    """
    Validate that a URL is a public http(s) destination suitable for fetching.

    Rejects local/private/metadata destinations. Optionally resolves DNS and
    checks the resulting addresses (used before requests and on redirects).
    """
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeURLError(f"Unsupported URL scheme: {scheme or '(missing)'}")
    if not parsed.hostname:
        raise UnsafeURLError("URL missing hostname")
    if parsed.username or parsed.password:
        raise UnsafeURLError("URLs with embedded credentials are not allowed")
    if _hostname_is_blocked(parsed.hostname):
        raise UnsafeURLError(f"Blocked hostname: {parsed.hostname}")

    # Literal IP in the URL
    try:
        literal_ip = ipaddress.ip_address(parsed.hostname.strip("[]"))
    except ValueError:
        literal_ip = None
    if literal_ip is not None and _ip_is_unsafe(literal_ip):
        raise UnsafeURLError(f"Blocked IP address: {literal_ip}")

    if resolve_dns and literal_ip is None:
        try:
            infos = socket.getaddrinfo(parsed.hostname, None)
        except socket.gaierror as exc:
            raise UnsafeURLError(f"DNS resolution failed for {parsed.hostname}: {exc}") from exc
        if not infos:
            raise UnsafeURLError(f"No DNS records for {parsed.hostname}")
        for info in infos:
            addr = info[4][0]
            try:
                ip = ipaddress.ip_address(addr)
            except ValueError:
                continue
            if _ip_is_unsafe(ip):
                raise UnsafeURLError(f"Hostname {parsed.hostname} resolves to unsafe address {ip}")

    return url.strip()
