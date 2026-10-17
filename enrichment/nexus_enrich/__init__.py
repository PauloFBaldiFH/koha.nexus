"""koha.nexus enrichment engine: match a local MARC21 record against
candidate records and add, never replace, the fields it lacks.

    from nexus_enrich import enrich, Candidate, Policy
    result = enrich(local_record, [Candidate(rec, "bn", "123", weight=1.0)])
    result.status, result.additions, result.record

Pure Python (standard library only); reading static.db needs zstandard.
"""

from .classify import M0, M1, R, W, Thresholds
from .merge import Candidate, Policy, Result, enrich

__version__ = "0.1.0"
__all__ = ["M0", "M1", "W", "R", "Thresholds", "Candidate", "Policy", "Result", "enrich", "__version__"]
