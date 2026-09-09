"""Small, dependency-free primitives for an agent economic assurance case.

Two entry points issue a decision and they are not interchangeable.
`decide` is the gate: it evaluates and audits as one act, and a SCALE the
audit has grounds against comes back INCOMPLETE. `evaluate_bundle` is the
engine alone, which is what the property tests and the sweeps want, and it
will return that SCALE.

For a while only the CLI reached the gate. `decide` was not exported, so a
library consumer doing the obvious thing got the engine, and on
`examples/claude-code-tree/bundle.json` the engine says SCALE where the gate
says INCOMPLETE on unattested instruments. That is the fail-open this
package exists to argue against, shipped in its own public surface. Both are
exported now, tests/test_entry_points.py pins the difference on every
shipped bundle, and the rule is: gating anything, call `decide`.
"""

__version__ = "0.9.0"

from .audit import AuditReport, audit, decide
from .adapters import (
    load_normalized_json_bundle,
    normalized_json_bundle,
    normalized_json_document,
    render_normalized_json,
)
from .assurance import (
    ASSURANCE_ENGINE_IMPLEMENTATION,
    DECISION_CONTRACT_SCHEMA,
    ROUTING_SEMANTICS,
    AssuranceEngine,
    decision_contract_digest,
    decision_contract_manifest,
    default_engine,
    evaluate,
    evaluate_bundle,
)
from .checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from .claude_code import (
    ClaudeCodeSession,
    claude_code_bundle,
    claude_code_bundle_from_session,
    conversion_contract_template,
    conversion_receipt,
    inspect_claude_code_jsonl,
    inspect_to_contract_template,
    load_conversion_contract,
)
from .claude_code_tree import (
    claude_code_tree_bundle,
    claude_code_tree_bundle_from_session,
    inspect_claude_code_session_tree,
)
from .delegation import (
    DELEGATION_CLOSURE,
    ClosureReport,
    assess_bundle_closure,
    delegation_closure_gate,
)
from .evidence import make_evidence_bundle
from .frontier import (
    ArmSummary,
    ExperimentPlan,
    FrontierCase,
    FrontierDecision,
    PairedComparison,
    clopper_pearson_upper,
    evaluate_frontier,
    load_experiment,
    load_plan,
    run_frontier,
)
from .frontier_report import (
    render_frontier_json,
    render_frontier_markdown,
    render_frontier_svg,
)
from .io import (
    load_baseline,
    load_csv_bundle,
    load_outcomes,
    load_policy,
    load_rates,
    load_traces,
)
from .kimi_client import KimiRequestError
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
    TaskIdentity,
    TraceEvent,
    implementation_fingerprint,
)
from .mutation import Mutation, MutationReport, mutate
from .otel_genai import (
    OtelGenAISession,
    conversion_contract_template as otel_genai_conversion_contract_template,
    conversion_receipt as otel_genai_conversion_receipt,
    inspect_otel_genai_json,
    otel_genai_bundle,
    otel_genai_bundle_from_session,
)
from .provenance import (
    EVIDENCE_PROVENANCE,
    Attestation,
    ProvenancePolicy,
    ProvenanceReport,
    assess_provenance,
    evidence_provenance_gate,
    parse_attestations,
)

__all__ = [
    "ASSURANCE_ENGINE_IMPLEMENTATION",
    "DECISION_CONTRACT_SCHEMA",
    "DEFAULT_REQUIRED_COVERAGE",
    "DELEGATION_CLOSURE",
    "EVIDENCE_PROVENANCE",
    "ROUTING_SEMANTICS",
    "ArmSummary",
    "AssuranceCase",
    "AssuranceEngine",
    "Attestation",
    "Baseline",
    "CheckMode",
    "CheckOutput",
    "CheckResult",
    "CheckSpec",
    "CheckStatus",
    "ClaudeCodeSession",
    "ClosureReport",
    "Coverage",
    "Decision",
    "EconomicPolicy",
    "EvaluationView",
    "EvidenceBundle",
    "ExperimentPlan",
    "FrontierCase",
    "FrontierDecision",
    "KimiRequestError",
    "ModelRate",
    "Mutation",
    "MutationReport",
    "OtelGenAISession",
    "Outcome",
    "PairedComparison",
    "ProvenancePolicy",
    "ProvenanceReport",
    "TaskIdentity",
    "TraceEvent",
    "__version__",
    "assess_bundle_closure",
    "assess_provenance",
    "claude_code_bundle",
    "claude_code_bundle_from_session",
    "claude_code_tree_bundle",
    "claude_code_tree_bundle_from_session",
    "clopper_pearson_upper",
    "conversion_contract_template",
    "conversion_receipt",
    "decision_contract_digest",
    "decision_contract_manifest",
    "default_checks",
    "default_engine",
    "delegation_closure_gate",
    "evaluate",
    "evaluate_bundle",
    "decide",
    "audit",
    "AuditReport",
    "evaluate_frontier",
    "evidence_provenance_gate",
    "implementation_fingerprint",
    "inspect_claude_code_jsonl",
    "inspect_claude_code_session_tree",
    "inspect_otel_genai_json",
    "inspect_to_contract_template",
    "load_baseline",
    "load_conversion_contract",
    "load_csv_bundle",
    "load_experiment",
    "load_normalized_json_bundle",
    "load_outcomes",
    "load_plan",
    "load_policy",
    "load_rates",
    "load_traces",
    "make_evidence_bundle",
    "mutate",
    "normalized_json_bundle",
    "normalized_json_document",
    "otel_genai_bundle",
    "otel_genai_bundle_from_session",
    "otel_genai_conversion_contract_template",
    "otel_genai_conversion_receipt",
    "parse_attestations",
    "render_frontier_json",
    "render_frontier_markdown",
    "render_frontier_svg",
    "render_normalized_json",
    "run_frontier",
]
