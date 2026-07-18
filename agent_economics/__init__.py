"""Small, dependency-free primitives for an agent economic assurance case."""

from .adapters import load_normalized_json_bundle, normalized_json_bundle
from .assurance import AssuranceEngine, default_engine, evaluate, evaluate_bundle
from .checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from .evidence import make_evidence_bundle
from .io import (
    load_baseline,
    load_csv_bundle,
    load_outcomes,
    load_policy,
    load_rates,
    load_traces,
)
from .models import (
    AssuranceCase,
    Baseline,
    CheckMode,
    CheckOutput,
    CheckResult,
    CheckSpec,
    CheckStatus,
    Coverage,
    Decision,
    EconomicPolicy,
    EvaluationView,
    EvidenceBundle,
    ModelRate,
    Outcome,
    TraceEvent,
)

__all__ = [
    "AssuranceCase",
    "AssuranceEngine",
    "Baseline",
    "CheckMode",
    "CheckOutput",
    "CheckResult",
    "CheckSpec",
    "CheckStatus",
    "Coverage",
    "DEFAULT_REQUIRED_COVERAGE",
    "Decision",
    "EconomicPolicy",
    "EvaluationView",
    "EvidenceBundle",
    "ModelRate",
    "Outcome",
    "TraceEvent",
    "default_checks",
    "default_engine",
    "evaluate",
    "evaluate_bundle",
    "load_baseline",
    "load_csv_bundle",
    "load_normalized_json_bundle",
    "load_outcomes",
    "load_policy",
    "load_rates",
    "load_traces",
    "make_evidence_bundle",
    "normalized_json_bundle",
]
