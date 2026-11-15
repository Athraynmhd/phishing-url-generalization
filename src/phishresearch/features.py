"""Lexical feature dictionary v1 (PRD s11): 37 deterministic numeric features.

Each feature is a small function of a ParsedURL, so a subset only runs the functions it
needs (dependency pruning: entropy / keyword tokenisation are skipped unless selected).
Parsing itself is shared by every feature and is always paid.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Callable, Iterable, Sequence

import numpy as np
import pandas as pd

from .common import canonical_json, sha256_text
from .urls import ParsedURL, Quarantine, canonicalize_url, registered_domain

FEATURE_VERSION = "lexical37-v1"
KEYWORDS = ("login", "signin", "verify", "account", "secure", "update", "password", "banking", "confirm", "wallet")
_ALNUM_RUN = re.compile(r"[A-Za-z0-9]+")
_TRIPLET = re.compile(r"%[0-9A-Fa-f]{2}")
_TOKEN = re.compile(r"[A-Za-z]+")


def _digits(s: str) -> int:
    return sum(1 for c in s if "0" <= c <= "9")


def _letters(s: str) -> int:
    return sum(1 for c in s if ("a" <= c <= "z") or ("A" <= c <= "Z"))


def _entropy(s: str) -> float:
    n = len(s)
    if n == 0:
        return 0.0
    return -sum((c / n) * math.log2(c / n) for c in Counter(s).values())


def _max_run(s: str) -> int:
    return max((len(m) for m in _ALNUM_RUN.findall(s)), default=0)


def _host_labels(p: ParsedURL) -> int:
    return 0 if p.is_ip else sum(1 for lab in p.host.split(".") if lab)


def _subdomain_labels(p: ParsedURL) -> int:
    if p.is_ip:
        return 0
    rd = registered_domain(p.host)
    if rd is None:
        return 0
    return max(0, _host_labels(p) - len(rd.split(".")))


def _kw(s: str, kws: frozenset) -> int:
    return sum(1 for t in _TOKEN.findall(s) if t.lower() in kws)


def _ratio(a: float, b: float) -> float:
    return a / b if b else 0.0


def _build(keywords: Sequence[str]) -> dict[str, tuple[str, Callable[[ParsedURL], float]]]:
    kws = frozenset(k.lower() for k in keywords)
    return {
        "F01": ("url_length", lambda p: len(p.work)),
        "F02": ("host_length", lambda p: len(p.host)),
        "F03": ("path_length", lambda p: len(p.path)),
        "F04": ("query_length", lambda p: len(p.query)),
        "F05": ("fragment_length", lambda p: len(p.fragment)),
        "F06": ("dot_count", lambda p: p.work.count(".")),
        "F07": ("hyphen_count", lambda p: p.work.count("-")),
        "F08": ("underscore_count", lambda p: p.work.count("_")),
        "F09": ("slash_count", lambda p: p.work.count("/")),
        "F10": ("at_count", lambda p: p.work.count("@")),
        "F11": ("question_count", lambda p: p.work.count("?")),
        "F12": ("equals_count", lambda p: p.work.count("=")),
        "F13": ("ampersand_count", lambda p: p.work.count("&")),
        "F14": ("percent_count", lambda p: p.work.count("%")),
        "F15": ("colon_count", lambda p: p.work.count(":")),
        "F16": ("digit_count", lambda p: _digits(p.work)),
        "F17": ("letter_count", lambda p: _letters(p.work)),
        "F18": ("digit_ratio", lambda p: _ratio(_digits(p.work), len(p.work))),
        "F19": ("nonascii_count", lambda p: sum(1 for c in p.work if ord(c) > 127)),
        "F20": ("char_entropy", lambda p: _entropy(p.work)),
        "F21": ("max_alnum_run", lambda p: _max_run(p.work)),
        "F22": ("host_label_count", _host_labels),
        "F23": ("subdomain_label_count", _subdomain_labels),
        "F24": ("host_digit_ratio", lambda p: _ratio(_digits(p.host), len(p.host))),
        "F25": ("host_is_ip", lambda p: int(p.is_ip)),
        "F26": ("explicit_port", lambda p: int(p.port is not None)),
        "F27": ("port_number", lambda p: p.port or 0),
        "F28": ("has_userinfo", lambda p: int(p.has_userinfo)),
        "F29": ("has_query", lambda p: int(len(p.query) > 0)),
        "F30": ("is_https", lambda p: int(p.scheme == "https")),
        "F31": ("scheme_missing", lambda p: int(p.scheme is None)),
        "F32": ("host_has_punycode", lambda p: int(any(lab.startswith("xn--") for lab in p.host.split(".")))),
        "F33": ("encoded_triplet_count", lambda p: len(_TRIPLET.findall(p.work))),
        "F34": ("query_pair_count", lambda p: sum(1 for s in p.query.split("&") if s)),
        "F35": ("path_segment_count", lambda p: sum(1 for s in p.path.split("/") if s)),
        "F36": ("url_keyword_count", lambda p: _kw(p.work, kws)),
        "F37": ("host_keyword_count", lambda p: _kw(p.host, kws)),
    }


FEATURES = _build(KEYWORDS)
FEATURE_IDS: tuple[str, ...] = tuple(FEATURES)
FEATURE_NAMES = {fid: name for fid, (name, _) in FEATURES.items()}
FLOAT_FEATURES = {"F18", "F20", "F24"}


def feature_schema_hash(keywords: Sequence[str] = KEYWORDS) -> str:
    return sha256_text(canonical_json({
        "version": FEATURE_VERSION, "ids": list(FEATURE_IDS),
        "names": [FEATURE_NAMES[f] for f in FEATURE_IDS], "keywords": list(keywords),
    }))


def validate_ids(selected: Iterable[str]) -> list[str]:
    sel = list(selected)
    unknown = [f for f in sel if f not in FEATURES]
    if unknown:
        raise ValueError(f"unknown feature ids: {unknown}")
    if len(set(sel)) != len(sel):
        raise ValueError("duplicate feature ids")
    return sorted(sel)          # canonical column order = feature id order


def extract_parsed(parsed: Sequence[ParsedURL], selected_ids: Iterable[str] = FEATURE_IDS,
                   keywords: Sequence[str] = KEYWORDS) -> pd.DataFrame:
    ids = validate_ids(selected_ids)
    table = FEATURES if tuple(keywords) == KEYWORDS else _build(keywords)
    fns = [table[f][1] for f in ids]
    data = np.array([[fn(p) for fn in fns] for p in parsed], dtype=np.float64).reshape(len(parsed), len(ids))
    if not np.isfinite(data).all():
        raise ValueError("non-finite feature value")
    return pd.DataFrame(data, columns=ids)


def extract_features(urls: Sequence[str], selected_ids: Iterable[str] = FEATURE_IDS,
                     keywords: Sequence[str] = KEYWORDS) -> pd.DataFrame:
    """End-to-end extraction from raw URL strings (parse + selected features)."""
    parsed = []
    for u in urls:
        p = canonicalize_url(u)
        if isinstance(p, Quarantine):
            raise ValueError(f"URL rejected by parser: {p.reason}")
        parsed.append(p)
    return extract_parsed(parsed, selected_ids, keywords)
