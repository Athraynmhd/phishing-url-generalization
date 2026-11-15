"""U01 parsing - expected values written by hand on reserved / documentation domains."""
import pytest

from phishresearch.urls import ParsedURL, Quarantine, canonicalize_url, registered_domain


def ok(u) -> ParsedURL:
    p = canonicalize_url(u)
    assert isinstance(p, ParsedURL), p
    return p


def test_scheme_absent_and_protocol_relative():
    p = ok("login.example.test/a")
    assert p.scheme is None and p.host == "login.example.test" and p.path == "/a"
    assert p.work == "login.example.test/a"                    # virtual // never leaks into work
    assert p.url_key == "<none>://login.example.test/a"
    q = ok("//cdn.example.test/x")
    assert q.scheme is None and q.scheme_missing


def test_uppercase_host_lowered_path_case_kept():
    p = ok("HTTPS://WWW.Example.COM/Path/File.HTML?Q=A#Frag")
    assert p.scheme == "https" and p.host == "www.example.com"
    assert p.url_key == "https://www.example.com/Path/File.HTML?Q=A#Frag"
    assert (p.path, p.query, p.fragment) == ("/Path/File.HTML", "Q=A", "Frag")


def test_idna_unicode_and_punycode_same_key():
    assert ok("http://bücher.example/").host == "xn--bcher-kva.example"
    assert ok("http://bücher.example/").url_key == ok("http://xn--bcher-kva.example/").url_key


def test_ipv4_ipv6():
    p = ok("http://192.0.2.10/login")
    assert p.is_ip and p.group_key == "ip:192.0.2.10"
    q = ok("http://[2001:DB8::1]:8443/")
    assert q.is_ip and q.host == "2001:db8::1" and q.port == 8443
    assert q.url_key == "http://[2001:db8::1]:8443/"


def test_userinfo_and_explicit_default_port_kept():
    p = ok("http://user:pw@example.com:80/")
    assert p.has_userinfo and p.port == 80 and p.host == "example.com"
    assert p.url_key == "http://user:pw@example.com:80/"
    assert ok("http://example.com/").url_key != p.url_key


def test_percent_encoding_not_decoded():
    p = ok("http://example.com/a%2Fb?x=%41")
    assert p.path == "/a%2Fb" and p.query == "x=%41"


def test_empty_query_kept_in_key():
    assert ok("http://example.com/a?").url_key == "http://example.com/a?"
    assert ok("http://example.com/a").url_key == "http://example.com/a"


@pytest.mark.parametrize("raw,reason", [
    ("", "empty"), ("   ", "empty"),
    ("http://example.com/a\nb", "embedded_control"),
    ("http://example.com/\x00", "embedded_control"),
    ("ftp://example.com/", "unsupported_scheme"),
    ("javascript:alert(1)", "unsupported_scheme"),
    ("http://example.com:99999/", "invalid_port"),
    ("http://example.com:8o/", "invalid_port"),
    ("http:///nohost", "no_host"),
    ("http://exa mple.com/", "invalid_host"),
    ("http://" + "a" * 20000 + ".com", "too_long"),
])
def test_malformed_quarantined(raw, reason):
    q = canonicalize_url(raw)
    assert isinstance(q, Quarantine) and q.reason == reason


def test_outer_whitespace_only_trimmed():
    assert ok("  http://example.com/a  ").work == "http://example.com/a"


def test_registered_domain_icann_only():
    assert registered_domain("a.b.example.co.uk") == "example.co.uk"
    assert registered_domain("x.blogspot.com") == "blogspot.com"     # private suffix ignored
    assert registered_domain("co.uk") is None                         # host is a suffix
    assert registered_domain("foo.bar.ck") == "foo.bar.ck"            # wildcard *.ck
    assert registered_domain("www.city.kawasaki.jp") == "city.kawasaki.jp"   # exception rule
    assert registered_domain("host.example.test") is None             # no ICANN rule
    assert ok("http://host.example.test/").group_key == "host.example.test"
