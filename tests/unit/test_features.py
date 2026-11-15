"""U02 exact feature values (hand-computed) and subset == projection of ALL."""
import itertools
import math

import numpy as np
import pytest

from phishresearch.features import FEATURE_IDS, extract_features

URL = "http://login.secure.example.com:8080/a_b/c-d?x=1&y=%41#top"


def feat(url=URL):
    return extract_features([url]).iloc[0].to_dict()


def test_hand_computed_values():
    f = feat()
    assert f["F01"] == len(URL) == 58
    assert f["F02"] == len("login.secure.example.com") == 24
    assert f["F03"] == len("/a_b/c-d") == 8
    assert f["F04"] == len("x=1&y=%41") == 9
    assert f["F05"] == 3
    assert (f["F06"], f["F07"], f["F08"], f["F09"]) == (3, 1, 1, 4)
    assert (f["F10"], f["F11"], f["F12"], f["F13"], f["F14"], f["F15"]) == (0, 1, 2, 1, 1, 2)
    assert f["F16"] == 7                              # 8080 1 41
    assert f["F18"] == pytest.approx(7 / 58)
    assert (f["F22"], f["F23"]) == (4, 2)             # login.secure | example.com
    assert (f["F26"], f["F27"], f["F28"], f["F29"], f["F30"], f["F31"]) == (1, 8080, 0, 1, 0, 0)
    assert (f["F33"], f["F34"], f["F35"]) == (1, 2, 2)
    assert (f["F36"], f["F37"]) == (2, 2)             # login, secure


def test_entropy_simple_strings():
    assert feat("aaaa.test")["F20"] == pytest.approx(-(4/9*math.log2(4/9) + 1/9*math.log2(1/9) + 2/9*math.log2(2/9) + 1/9*math.log2(1/9) + 1/9*math.log2(1/9)))
    assert feat("ab.test")["F20"] > 0


def test_keyword_token_boundaries():
    # 'logins' and 'relogin' are different tokens; 'LOGIN' matches; repeats counted
    f = feat("http://example.com/LOGIN/logins/relogin/login-verify")
    assert f["F36"] == 3 and f["F37"] == 0


def test_query_segmentation_and_ip_host():
    f = feat("http://192.0.2.1/?&a=1&&b=")
    assert f["F34"] == 2 and f["F22"] == 0 and f["F23"] == 0 and f["F25"] == 1


def test_no_scheme_and_https_flags():
    assert feat("example.com")["F31"] == 1 and feat("example.com")["F30"] == 0
    assert feat("HTTPS://example.com")["F30"] == 1


def test_punycode_and_nonascii():
    f = feat("http://bücher.example/ü")
    assert f["F32"] == 1 and f["F19"] == 2


def test_subset_equals_projection():
    urls = [URL, "example.com/x", "https://a.b.c.example.co.uk/p?q=1", "http://[2001:db8::2]/"]
    full = extract_features(urls)
    rng = np.random.default_rng(0)
    for k in (1, 8, 16, 24):
        sel = sorted(rng.choice(FEATURE_IDS, k, replace=False))
        np.testing.assert_array_equal(extract_features(urls, sel).to_numpy(), full[sel].to_numpy())


def test_rejects_unknown_ids():
    with pytest.raises(ValueError):
        extract_features([URL], ["F01", "F99"])
