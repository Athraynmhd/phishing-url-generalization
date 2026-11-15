"""Offline URL canonicalisation, url_key and registered-domain grouping (PRD s8).

No network access: the Public Suffix List is a frozen snapshot shipped in resources/.
Only the ICANN section is used for primary grouping (private suffixes such as
blogspot.com are NOT suffixes here, so all *.blogspot.com share one group).
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

import idna

from .common import PKG_DIR, sha256_file, sha256_text

PARSER_VERSION = "urls-v1"
PSL_PATH = PKG_DIR / "resources" / "public_suffix_list.dat"
MAX_URL_LENGTH = 16384
OUTER_WS = " \t\n\r\x0b\x0c"
_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*)://")
_ASCII_HOST_RE = re.compile(r"^[a-z0-9_\-.]+$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
# 'word:' at the start that is not 'host:port' (digits then / ? # or end) and not 'scheme://'
_BAD_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:(?!\d+(?:[/?#]|$))")


@dataclass(frozen=True)
class ParsedURL:
    work: str              # raw URL with outer ASCII whitespace removed (feature string)
    scheme: str | None     # lower-case explicit scheme, None if absent / protocol-relative
    host: str              # ASCII (IDNA) host, lower case, no trailing dot, no IPv6 brackets
    is_ip: bool
    port: int | None       # explicit port number (default ports kept)
    has_userinfo: bool
    path: str
    query: str             # without '?'
    fragment: str          # without '#'
    url_key: str
    group_key: str         # registered domain / ip:<addr> / whole host

    @property
    def scheme_missing(self) -> bool:
        return self.scheme is None


@dataclass(frozen=True)
class Quarantine:
    reason: str


# ----------------------------------------------------------------- PSL (ICANN only)
@lru_cache(maxsize=1)
def _psl_rules() -> tuple[frozenset, frozenset, frozenset]:
    normal, wild, exc = set(), set(), set()
    for line in PSL_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("// ===BEGIN PRIVATE DOMAINS==="):
            break
        if not line or line.startswith("//"):
            continue
        body = line.lstrip("!").removeprefix("*.")
        rule = body if body.isascii() else idna.encode(body, uts46=True).decode("ascii")
        if line.startswith("!"):
            exc.add(rule)
        elif line.startswith("*."):
            wild.add(rule)
        else:
            normal.add(rule)
    return frozenset(normal), frozenset(wild), frozenset(exc)


def psl_hash() -> str:
    return sha256_file(PSL_PATH)


def registered_domain(host: str) -> str | None:
    """eTLD+1 for an ASCII host using explicit ICANN rules; None if no explicit rule matches
    or the host itself is a public suffix."""
    normal, wild, exc = _psl_rules()
    labels = host.split(".")
    n = len(labels)
    suffix_len = 0
    for i in range(n):  # i = index where candidate suffix starts; longest first
        cand = ".".join(labels[i:])
        if cand in exc:
            suffix_len = n - i - 1
            break
        if cand in normal:
            suffix_len = n - i
            break
        if i + 1 < n and ".".join(labels[i + 1:]) in wild:
            suffix_len = n - i
            break
    if suffix_len == 0 or suffix_len >= n:
        return None
    return ".".join(labels[n - suffix_len - 1:])


def group_key_for(host: str, is_ip: bool) -> str:
    if is_ip:
        return "ip:" + host
    return registered_domain(host) or host


def group_id_for(group_key: str) -> str:
    return sha256_text("group:" + group_key)[:20]


# ----------------------------------------------------------------- canonicalisation
def _split_hostport(hostport: str) -> tuple[str, str | None]:
    if hostport.startswith("["):
        end = hostport.find("]")
        if end < 0:
            return hostport, None
        rest = hostport[end + 1:]
        return hostport[: end + 1], (rest[1:] if rest.startswith(":") else (None if not rest else "\x00bad"))
    if ":" in hostport:
        h, p = hostport.rsplit(":", 1)
        return h, p
    return hostport, None


def canonicalize_url(raw: str, max_length: int = MAX_URL_LENGTH) -> ParsedURL | Quarantine:
    if not isinstance(raw, str):
        return Quarantine("not_string")
    work = raw.strip(OUTER_WS)
    if not work:
        return Quarantine("empty")
    if len(work) > max_length:
        return Quarantine("too_long")
    # CR/LF/NUL per PRD; other C0 controls too, because urlsplit silently deletes tabs and
    # leading controls, which would make url_key differ from the stored string.
    if _CONTROL_RE.search(work):
        return Quarantine("embedded_control")

    m = _SCHEME_RE.match(work)
    if m:
        scheme = m.group(1).lower()
        if scheme not in ("http", "https"):
            return Quarantine("unsupported_scheme")
        prefix_len, parse_str = len(m.group(0)), work      # 'scheme://'
    elif _BAD_SCHEME_RE.match(work):           # e.g. 'mailto:x', 'http:/x', 'javascript:...'
        return Quarantine("unsupported_scheme")
    elif work.startswith("//"):
        scheme, prefix_len, parse_str = None, 2, work
    else:
        scheme, prefix_len, parse_str = None, 2, "//" + work   # virtual prefix, work unchanged

    try:
        sp = urlsplit(parse_str)
    except ValueError:
        return Quarantine("parse_error")
    netloc = sp.netloc
    has_userinfo = "@" in netloc
    hostport = netloc.rsplit("@", 1)[1] if has_userinfo else netloc
    host_raw, port_str = _split_hostport(hostport)

    port: int | None = None
    if port_str is not None and port_str != "":
        if not port_str.isdigit() or not port_str.isascii() or int(port_str) > 65535:
            return Quarantine("invalid_port")
        port = int(port_str)

    host = host_raw.strip("[]").rstrip(".").lower()
    if not host:
        return Quarantine("no_host")
    is_ip = False
    try:
        ipaddress.ip_address(host)
        is_ip = True
        host = str(ipaddress.ip_address(host))
    except ValueError:
        if not host.isascii():
            try:
                host = idna.encode(host, uts46=True, transitional=False).decode("ascii")
            except idna.IDNAError:
                return Quarantine("idna_error")
        if not _ASCII_HOST_RE.match(host) or ".." in host or host.startswith("."):
            return Quarantine("invalid_host")
    if host_raw.startswith("[") and not is_ip:
        return Quarantine("invalid_host")

    # url_key: lower scheme+host, keep userinfo/port/path/query/fragment exactly as written
    remainder = parse_str[prefix_len + len(netloc):]
    userinfo = netloc.rsplit("@", 1)[0] + "@" if has_userinfo else ""
    host_disp = f"[{host}]" if is_ip and ":" in host else host
    port_part = f":{port_str}" if port_str not in (None, "") else ""
    url_key = f"{scheme or '<none>'}://{userinfo}{host_disp}{port_part}{remainder}"

    return ParsedURL(
        work=work, scheme=scheme, host=host, is_ip=is_ip, port=port, has_userinfo=has_userinfo,
        path=sp.path, query=sp.query, fragment=sp.fragment, url_key=url_key,
        group_key=group_key_for(host, is_ip),
    )
