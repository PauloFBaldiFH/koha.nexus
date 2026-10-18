"""Which direct servers to ask for one record, in what order (plan 4.2).

Eligible: the right record type, usable (not UNIMARC, login present), in
the librarian's subset when there is one, and with at least one address
that is not down, misconfigured or over its daily cap.

Order, as a tuple (not a weighted sum, so the preview can explain it):
  1. affinity to the record: a server in a country of the record's
     language or place first, then the regions in that language's order;
  2. national libraries and the preselected servers first in a region;
  3. health: success ratio over 7 days, then latency;
  4. the id, so the order is stable.
Then waves(): each wave gets at most PER_WAVE_PROVIDER sessions on one
provider (one Alma cluster, LoC), so a wave never bursts a shared gateway;
when only one provider's servers are left, its waves are that small.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nexus_enrich.marc import Record

from .targets import Target

WAVE = 6
PER_WAVE_PROVIDER = 2
REGIONS = ("brazil", "latin_america", "north_america", "europe", "asia_oceania")

# language (MARC 008/35-37) -> (countries first, regions in order)
LANGUAGES = {
    "por": (("BR", "PT"), ("brazil", "europe", "latin_america", "north_america", "asia_oceania")),
    "spa": (("ES", "MX", "AR", "CL", "CO", "PE"), ("latin_america", "europe", "north_america", "brazil",
                                                    "asia_oceania")),
    "eng": (("US", "GB", "CA", "AU", "NZ", "IE"), ("north_america", "europe", "asia_oceania", "latin_america",
                                                   "brazil")),
    "ger": (("DE", "AT", "CH"), ("europe", "north_america")),
    "fre": (("FR", "BE", "CH", "CA"), ("europe", "north_america")),
    "ita": (("IT", "CH"), ("europe", "north_america")),
    "dut": (("NL", "BE"), ("europe", "north_america")),
    "dan": (("DK",), ("europe", "north_america")),
    "cze": (("CZ",), ("europe", "north_america")),
    "heb": (("IL",), ("asia_oceania", "north_america", "europe")),
    "chi": (("HK", "SG", "TW", "CN"), ("asia_oceania", "north_america", "europe")),
    "jpn": (("JP",), ("asia_oceania", "north_america", "europe")),
}
# 008/15-17 place codes that settle the language question on their own.
PLACES = {"bl": "por", "po": "por", "sp": "spa", "mx": "spa", "ag": "spa", "xxu": "eng", "xxk": "eng",
          "enk": "eng", "gw": "ger", "fr": "fre", "it": "ita"}
DEFAULT = ((), ("north_america", "europe", "brazil", "latin_america", "asia_oceania"))
_NATIONAL = re.compile(r"\b(Nacional|National Library|Nationalbibliothek|Library of Congress|PORBASE)\b")


@dataclass(frozen=True)
class Context:
    """What the order depends on, read once per record."""
    language: str = ""
    place: str = ""

    @classmethod
    def of(cls, rec: Record | None) -> "Context":
        if rec is None:
            return cls()
        f008 = rec.control("008")
        lang = f008[35:38].strip().lower() if len(f008) == 40 else ""
        place = f008[15:18].strip().lower() if len(f008) == 40 else ""
        return cls(lang, place)

    def preference(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        lang = self.language if self.language in LANGUAGES else PLACES.get(self.place, "")
        if lang == "" and self.place[:2] in PLACES:
            lang = PLACES[self.place[:2]]
        countries, regions = LANGUAGES.get(lang, DEFAULT)
        return countries, regions + tuple(r for r in REGIONS if r not in regions)


def is_national(t: Target) -> bool:
    return bool(_NATIONAL.search(t.name)) and "University" not in t.name and "Universidad" not in t.name


def _health_key(t: Target, health) -> tuple:
    if health is None:
        return (0.0, 0)
    s = health.summary(t.address.key)
    seen = s["ok_7d"] + s["fail_7d"]
    ratio = s["ok_7d"] / seen if seen else 0.5
    return (-ratio, s["latency_ms"] or 99_999)


def _blocked(t: Target, health, limiter) -> str:
    """Why none of T's addresses can be used now, or ""."""
    reasons = []
    for a in t.addresses:
        state = health.state(a.key) if health is not None else "ok"
        if state in ("down", "misconfigured"):
            reasons.append(state)
            continue
        cap = limiter.capped(a) if limiter is not None else ""
        if cap:
            reasons.append(cap)
            continue
        return ""
    return reasons[0] if reasons else "no address"


def rank(targets, rec: Record | None = None, *, recordtype: str = "biblio", only=None, health=None,
         limiter=None):
    """(ordered targets, [(id, why skipped)])."""
    ctx = Context.of(rec)
    countries, regions = ctx.preference()
    only = {o.lower() for o in only} if only else None
    eligible, skipped = [], []
    for t in targets:
        if t.recordtype != recordtype:
            continue
        if only is not None and t.id not in only and t.category not in only:
            continue
        why = t.unusable or _blocked(t, health, limiter)
        if why:
            skipped.append((t.id, why))
            continue
        eligible.append(t)

    def key(t: Target):
        region = regions.index(t.category) if t.category in regions else len(regions)
        return (0 if t.country in countries else 1, region, 0 if (is_national(t) or t.preselect) else 1,
                *_health_key(t, health), t.id)

    eligible.sort(key=key)
    return eligible, skipped


def waves(ordered: list[Target], wave: int = WAVE, per_provider: int = PER_WAVE_PROVIDER) -> list[list[Target]]:
    """ORDERED cut into waves of at most WAVE, each with at most PER_PROVIDER
    of one provider (a host without a provider is its own), keeping the
    order as much as that allows."""
    rest = list(ordered)
    out: list[list[Target]] = []
    while rest:
        chunk, counts, left = [], {}, []
        for t in rest:
            p = t.address.provider or t.address.host_key
            if len(chunk) < wave and counts.get(p, 0) < per_provider:
                chunk.append(t)
                counts[p] = counts.get(p, 0) + 1
            else:
                left.append(t)
        out.append(chunk)                   # never empty: the first of REST always fits
        rest = left
    return out
