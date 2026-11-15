"""Synthetic two-source fixture on reserved *.example.test domains (tests / `smoke` only).
Outputs are NOT scientific results."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .adapters import _frame

WORDS = ["news", "shop", "blog", "docs", "mail", "photo", "travel", "music", "wiki", "forum"]
KW = ["login", "verify", "account", "secure", "update", "wallet"]


def _url(rng, phishing: bool, domain: str, style: int) -> str:
    if phishing:
        host = ".".join(rng.choice(KW, rng.integers(1, 3))) + "." + domain if style else f"{rng.integers(1, 255)}.{rng.integers(0, 255)}.{rng.integers(0, 255)}.{rng.integers(1, 255)}"
        path = "/" + "-".join(rng.choice(KW + WORDS, rng.integers(2, 5))) + (".php" if style else "")
        q = f"?id={rng.integers(10**5, 10**8)}&session={rng.integers(10**6, 10**9):x}" if rng.random() < 0.6 else ""
        return f"{'http' if rng.random() < 0.7 else 'https'}://{host}{path}{q}"
    # .test has no PSL rule, so the group is the whole host: keep benign hosts == domain
    host = domain
    path = "/" + "/".join(rng.choice(WORDS, rng.integers(0, 3)))
    return f"https://{host}{path}"


def make_source(dataset_id: str, n_domains: int, per_domain: int, seed: int, shift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    urls, labels = [], []
    for d in range(n_domains):
        phishing = d % 2 == 1
        domain = f"{dataset_id.lower()}{d}.example.test"
        style = 1 if rng.random() > shift else 0
        for _ in range(int(rng.integers(1, per_domain + 1))):
            urls.append(_url(rng, phishing, domain, style))
            labels.append(int(phishing))
    # a few rows that must be quarantined / deduplicated
    urls += ["mailto:x@example.test", urls[0], "http://bad\nnewline.example.test/"]
    labels += [0, labels[0], 1]
    return _frame(dataset_id, f"synthetic_{dataset_id}.json", urls, labels, None)


def make_sources(seed: int = 7) -> list[pd.DataFrame]:
    a = make_source("A", 160, 6, seed)
    b = make_source("B", 160, 6, seed + 1, shift=0.3)
    # one shared domain across sources -> must be purged from both
    shared = _frame("B", "synthetic_B_shared.json", ["https://a0.example.test/shared"], [0], None)
    return [a, pd.concat([b, shared], ignore_index=True)]
