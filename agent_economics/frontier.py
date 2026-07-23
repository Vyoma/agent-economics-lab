"""Paired, uncertainty-aware comparison of tested agent configurations.

The frontier is deliberately offline. It consumes frozen normalized evidence
bundles, aligns identical task input digests and rubric versions, and refuses
complete-case deletion. The
quality gate uses an exact upper confidence bound on harmful regressions versus
the reference arm. Cost savings use a deterministic paired bootstrap.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from enum import Enum
from numbers import Integral, Real
from pathlib import Path
from typing import Any, Mapping, Sequence

from .adapters import normalized_json_bundle
from .assurance import evaluate_bundle
from .evidence import validate_evidence_bundle
from .models import (
    AssuranceCase,
    Decision,
    EvidenceBundle,
    TaskEconomics,
    TaskIdentity,
)


CANONICAL_SIGNIFICANT_DIGITS = 12


def canonical_float(value: float) -> float:
    """Remove runtime-level noise from a finite derived statistic.

    Decision endpoints and portable artifacts use twelve significant digits. This
    is substantially finer than displayed report precision while keeping supported
    Python runtimes byte-stable around platform-level floating-point differences.
    """
    if not math.isfinite(value):
        return value
    result = float(format(value, f".{CANONICAL_SIGNIFICANT_DIGITS}g"))
    return 0.0 if result == 0 else result


class FrontierDecision(str, Enum):
    INCOMPLETE = "INCOMPLETE"
    HOLD = "HOLD"
    ADOPT = "ADOPT"


@dataclass(frozen=True)
class ExperimentPlan:
    experiment_id: str
    reference_arm: str
    arms: tuple[tuple[str, str], ...]
    max_breakage_rate: float
    min_cost_reduction_rate: float
    confidence_level: float
    bootstrap_samples: int
    seed: int
    min_paired_tasks: int
    task_manifest_path: str
    task_manifest_digest: str
    plan_digest: str

    @property
    def arm_paths(self) -> dict[str, str]:
        return dict(self.arms)

    @property
    def candidate_arms(self) -> tuple[str, ...]:
        return tuple(arm_id for arm_id, _ in self.arms if arm_id != self.reference_arm)


@dataclass(frozen=True)
class ArmSummary:
    arm_id: str
    assurance_decision: str
    paired_tasks: int
    acceptable_rate: float
    mean_effective_cost_usd: float
    cost_per_acceptable_outcome_usd: float
    expected_net_value_per_attempt_usd: float
    evidence_digest: str
    dominated: bool


@dataclass(frozen=True)
class PairedComparison:
    candidate_arm: str
    paired_tasks: int
    harmful_regressions: int
    beneficial_changes: int
    breakage_rate: float
    breakage_rate_upper: float
    acceptable_rate_delta: float
    mean_cost_reduction_rate: float
    cost_reduction_rate_lower: float
    adjusted_alpha: float
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FrontierCase:
    decision: FrontierDecision
    selected_arm: str | None
    plan: ExperimentPlan
    arms: tuple[ArmSummary, ...]
    comparisons: tuple[PairedComparison, ...]
    problems: tuple[str, ...]
    method: str = (
        "Exact one-sided Clopper-Pearson breakage bound plus deterministic "
        "paired percentile bootstrap for cost reduction; a Bonferroni-adjusted "
        "nominal familywise confidence target across planned quality and cost tests. "
        "Derived decision endpoints are canonicalized to twelve significant digits."
    )


def _canonical_digest(raw: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r} is not permitted")


def _validate_plan(raw: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "experiment_id",
        "reference_arm",
        "arms",
        "max_breakage_rate",
        "min_cost_reduction_rate",
        "confidence_level",
        "bootstrap_samples",
        "seed",
        "min_paired_tasks",
        "task_manifest",
        "task_manifest_digest",
    }
    missing = sorted(required - set(raw))
    if missing:
        raise ValueError(f"Experiment plan is missing fields: {missing}")
    if raw["schema_version"] != 1:
        raise ValueError("Only frontier plan schema_version 1 is supported")
    arms = raw["arms"]
    if not isinstance(arms, dict) or len(arms) < 2:
        raise ValueError("Experiment plan requires a reference and at least one candidate")
    if any(
        not isinstance(arm_id, str)
        or not arm_id.strip()
        or not isinstance(path, str)
        or not path.strip()
        for arm_id, path in arms.items()
    ):
        raise ValueError("arm IDs and paths must be non-empty strings")
    if raw["reference_arm"] not in arms:
        raise ValueError("reference_arm must name one of the planned arms")
    if not isinstance(raw["task_manifest"], str) or not raw["task_manifest"].strip():
        raise ValueError("task_manifest must be a non-empty relative path")
    task_manifest_digest = raw["task_manifest_digest"]
    if (
        not isinstance(task_manifest_digest, str)
        or len(task_manifest_digest) != 64
        or any(character not in "0123456789abcdef" for character in task_manifest_digest)
    ):
        raise ValueError("task_manifest_digest must be a lowercase SHA-256 digest")
    confidence = _finite_number(raw["confidence_level"], "confidence_level")
    max_breakage = _finite_number(raw["max_breakage_rate"], "max_breakage_rate")
    min_reduction = _finite_number(
        raw["min_cost_reduction_rate"], "min_cost_reduction_rate"
    )
    if not 0 < confidence < 1:
        raise ValueError("confidence_level must be between zero and one")
    if not 0 <= max_breakage < 1:
        raise ValueError("max_breakage_rate must be in [0, 1)")
    if not 0 <= min_reduction < 1:
        raise ValueError("min_cost_reduction_rate must be in [0, 1)")
    if not _is_integer(raw["bootstrap_samples"]) or raw["bootstrap_samples"] < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    if not _is_integer(raw["seed"]):
        raise ValueError("seed must be an integer")
    if not _is_integer(raw["min_paired_tasks"]) or raw["min_paired_tasks"] < 2:
        raise ValueError("min_paired_tasks must be at least 2")
    adjusted_alpha = (1 - confidence) / (2 * (len(arms) - 1))
    if raw["bootstrap_samples"] * adjusted_alpha < 20:
        raise ValueError(
            "bootstrap_samples must provide at least 20 expected draws in the "
            "adjusted lower tail"
        )


def _is_integer(value: Any) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _finite_number(value: Any, label: str) -> float:
    if not isinstance(value, Real) or isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def _validate_plan_instance(plan: ExperimentPlan) -> tuple[str, ...]:
    problems: list[str] = []
    if not isinstance(plan.experiment_id, str) or not plan.experiment_id.strip():
        problems.append("experiment_id must be a non-empty string")
    if not isinstance(plan.reference_arm, str) or not plan.reference_arm.strip():
        problems.append("reference_arm must be a non-empty string")

    arm_ids: list[str] = []
    try:
        arm_rows = tuple(plan.arms)
    except TypeError:
        arm_rows = ()
        problems.append("arms must be a sequence of (arm_id, path) pairs")
    for index, row in enumerate(arm_rows):
        if not isinstance(row, (tuple, list)) or len(row) != 2:
            problems.append(f"arm entry {index} must contain an arm ID and path")
            continue
        arm_id, path = row
        if not isinstance(arm_id, str) or not arm_id.strip():
            problems.append(f"arm entry {index} has an invalid arm ID")
        else:
            arm_ids.append(arm_id)
        if not isinstance(path, str) or not path.strip():
            problems.append(f"arm entry {index} has an invalid path")
    if len(arm_rows) < 2:
        problems.append("experiment requires a reference and at least one candidate")
    duplicate_ids = sorted(
        arm_id for arm_id in set(arm_ids) if arm_ids.count(arm_id) > 1
    )
    if duplicate_ids:
        problems.append(f"duplicate planned arm IDs: {duplicate_ids}")
    if plan.reference_arm not in arm_ids:
        problems.append("reference_arm must name one of the planned arms")

    numeric_rules = (
        ("confidence_level", plan.confidence_level, 0.0, 1.0, False),
        ("max_breakage_rate", plan.max_breakage_rate, 0.0, 1.0, True),
        (
            "min_cost_reduction_rate",
            plan.min_cost_reduction_rate,
            0.0,
            1.0,
            True,
        ),
    )
    for label, value, lower, upper, include_lower in numeric_rules:
        try:
            number = _finite_number(value, label)
        except ValueError as error:
            problems.append(str(error))
            continue
        lower_ok = number >= lower if include_lower else number > lower
        if not lower_ok or number >= upper:
            bracket = "[" if include_lower else "("
            problems.append(f"{label} must be in {bracket}{lower}, {upper})")
    if not _is_integer(plan.bootstrap_samples) or plan.bootstrap_samples < 100:
        problems.append("bootstrap_samples must be an integer of at least 100")
    if not _is_integer(plan.seed):
        problems.append("seed must be an integer")
    if not _is_integer(plan.min_paired_tasks) or plan.min_paired_tasks < 2:
        problems.append("min_paired_tasks must be an integer of at least 2")
    valid_candidate_count = len(set(arm_ids)) - int(plan.reference_arm in arm_ids)
    try:
        confidence = _finite_number(plan.confidence_level, "confidence_level")
    except ValueError:
        confidence = math.nan
    if (
        _is_integer(plan.bootstrap_samples)
        and plan.bootstrap_samples >= 100
        and valid_candidate_count > 0
        and math.isfinite(confidence)
    ):
        adjusted_alpha = (1 - confidence) / (2 * valid_candidate_count)
        if adjusted_alpha <= 0 or plan.bootstrap_samples * adjusted_alpha < 20:
            problems.append(
                "bootstrap_samples must provide at least 20 expected draws in the "
                "adjusted lower tail"
            )
    if not isinstance(plan.plan_digest, str) or not plan.plan_digest:
        problems.append("plan_digest must be a non-empty string")
    if (
        not isinstance(plan.task_manifest_path, str)
        or not plan.task_manifest_path.strip()
    ):
        problems.append("task_manifest_path must be a non-empty string")
    if (
        not isinstance(plan.task_manifest_digest, str)
        or len(plan.task_manifest_digest) != 64
        or any(
            character not in "0123456789abcdef"
            for character in plan.task_manifest_digest
        )
    ):
        problems.append("task_manifest_digest must be a lowercase SHA-256 digest")
    return tuple(problems)


def load_plan(path: str | Path) -> ExperimentPlan:
    plan_path = Path(path)
    with plan_path.open(encoding="utf-8") as handle:
        raw = json.load(handle, parse_constant=_reject_json_constant)
    if not isinstance(raw, Mapping):
        raise ValueError("Experiment plan must be a JSON object")
    _validate_plan(raw)
    arms = tuple(sorted((str(key), str(value)) for key, value in raw["arms"].items()))
    return ExperimentPlan(
        experiment_id=str(raw["experiment_id"]),
        reference_arm=str(raw["reference_arm"]),
        arms=arms,
        max_breakage_rate=float(raw["max_breakage_rate"]),
        min_cost_reduction_rate=float(raw["min_cost_reduction_rate"]),
        confidence_level=float(raw["confidence_level"]),
        bootstrap_samples=int(raw["bootstrap_samples"]),
        seed=int(raw["seed"]),
        min_paired_tasks=int(raw["min_paired_tasks"]),
        task_manifest_path=str(raw["task_manifest"]),
        task_manifest_digest=str(raw["task_manifest_digest"]),
        plan_digest=_canonical_digest(raw),
    )


def _validate_frontier_bundle(raw: Mapping[str, Any], arm_id: str) -> tuple[str, ...]:
    problems: list[str] = []
    if raw.get("schema_version") != 1:
        problems.append(f"{arm_id}: bundle schema_version must be 1")
    for index, event in enumerate(raw.get("events", ())):
        if not isinstance(event, Mapping):
            problems.append(f"{arm_id}: event {index} must be an object")
            continue
        if "task_id" not in event or "event_id" not in event:
            problems.append(f"{arm_id}: event {index} is missing task_id or event_id")
            continue
        direct = event.get("direct_cost_usd")
        if direct is None:
            event_type = event.get("event_type")
            model = event.get("model", "")
            rates = raw.get("rates", {})
            if event_type != "model" or model not in rates:
                problems.append(
                    f"{arm_id}: event {event['event_id']} has unknown cost; "
                    "provide direct_cost_usd (use 0.0 for explicitly included cost) "
                    "or a model rate"
                )
            elif "input_tokens" not in event or "output_tokens" not in event:
                problems.append(
                    f"{arm_id}: model event {event['event_id']} uses rate-card pricing "
                    "but omits input_tokens or output_tokens; provide both fields or "
                    "an explicit direct_cost_usd"
                )
    required_outcome_fields = {
        "task_id",
        "acceptable",
        "business_value_usd",
        "human_minutes",
        "remediation_cost_usd",
        "incident_loss_usd",
    }
    for index, outcome in enumerate(raw.get("outcomes", ())):
        if not isinstance(outcome, Mapping):
            problems.append(f"{arm_id}: outcome {index} must be an object")
            continue
        missing = sorted(required_outcome_fields - set(outcome))
        if missing:
            problems.append(
                f"{arm_id}: outcome {index} is missing full-cost fields: {missing}"
            )
    return tuple(problems)


def _task_manifest_digest(bundle: EvidenceBundle) -> str:
    payload = [
        asdict(bundle.task_manifest[task_id])
        for task_id in sorted(bundle.task_manifest)
    ]
    return _canonical_digest({"tasks": payload})


def load_experiment(
    plan_path: str | Path,
) -> tuple[ExperimentPlan, dict[str, EvidenceBundle], tuple[str, ...]]:
    plan_file = Path(plan_path)
    plan = load_plan(plan_file)
    bundles: dict[str, EvidenceBundle] = {}
    problems: list[str] = []
    task_rows: list[dict[str, str]] = []
    task_manifest_path = (plan_file.parent / plan.task_manifest_path).resolve()
    try:
        task_manifest_path.relative_to(plan_file.parent.resolve())
    except ValueError:
        problems.append("task manifest path escapes the plan directory")
    else:
        if not task_manifest_path.is_file():
            problems.append(
                f"task manifest is not a regular file: {plan.task_manifest_path}"
            )
        else:
            try:
                with task_manifest_path.open(encoding="utf-8") as handle:
                    task_raw = json.load(handle, parse_constant=_reject_json_constant)
                if not isinstance(task_raw, Mapping) or task_raw.get("schema_version") != 1:
                    raise ValueError("task manifest schema_version must be 1")
                raw_rows = task_raw.get("tasks")
                if not isinstance(raw_rows, list) or not raw_rows:
                    raise ValueError("task manifest requires a non-empty tasks list")
                identities: dict[str, TaskIdentity] = {}
                for row in raw_rows:
                    if not isinstance(row, Mapping):
                        raise ValueError("each task manifest entry must be an object")
                    identity = TaskIdentity(**row)
                    if identity.task_id in identities:
                        raise ValueError(
                            f"duplicate task manifest ID: {identity.task_id!r}"
                        )
                    identities[identity.task_id] = identity
                task_rows = [
                    asdict(identities[task_id]) for task_id in sorted(identities)
                ]
                observed_digest = _canonical_digest({"tasks": task_rows})
                if observed_digest != plan.task_manifest_digest:
                    problems.append(
                        f"task manifest digest {observed_digest} does not match "
                        f"frozen plan digest {plan.task_manifest_digest}"
                    )
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
                problems.append(f"invalid task manifest: {error}")
    for arm_id, relative_path in plan.arms:
        bundle_path = (plan_file.parent / relative_path).resolve()
        try:
            bundle_path.relative_to(plan_file.parent.resolve())
        except ValueError:
            problems.append(f"{arm_id}: bundle path escapes the plan directory")
            continue
        if not bundle_path.is_file():
            problems.append(f"{arm_id}: bundle is not a regular file: {relative_path}")
            continue
        try:
            with bundle_path.open(encoding="utf-8") as handle:
                raw = json.load(handle, parse_constant=_reject_json_constant)
            if not isinstance(raw, Mapping):
                raise ValueError("bundle must be a JSON object")
            problems.extend(_validate_frontier_bundle(raw, arm_id))
            normalized_raw = dict(raw)
            normalized_raw["task_manifest"] = task_rows
            bundles[arm_id] = normalized_json_bundle(normalized_raw)
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
            problems.append(f"{arm_id}: invalid bundle: {error}")
    return plan, bundles, tuple(problems)


def _binomial_cdf(observed: int, trials: int, probability: float) -> float:
    if probability <= 0:
        return 1.0
    if probability >= 1:
        return 1.0 if observed >= trials else 0.0
    log_probability = math.log(probability)
    log_complement = math.log1p(-probability)
    log_terms = [
        math.lgamma(trials + 1)
        - math.lgamma(value + 1)
        - math.lgamma(trials - value + 1)
        + value * log_probability
        + (trials - value) * log_complement
        for value in range(observed + 1)
    ]
    maximum = max(log_terms)
    log_sum = maximum + math.log(
        math.fsum(math.exp(term - maximum) for term in log_terms)
    )
    return min(1.0, math.exp(log_sum))


def clopper_pearson_upper(observed: int, trials: int, alpha: float) -> float:
    """Exact one-sided binomial upper confidence bound."""
    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0 <= observed <= trials:
        raise ValueError("observed must be between zero and trials")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")
    if observed == trials:
        return 1.0
    low = observed / trials
    high = 1.0
    for _ in range(80):
        midpoint = (low + high) / 2
        if _binomial_cdf(observed, trials, midpoint) > alpha:
            low = midpoint
        else:
            high = midpoint
    return high


def _lower_quantile(values: Sequence[float], alpha: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(alpha * len(ordered)) - 1)
    return ordered[index]


def _paired_cost_bootstrap(
    reference_costs: Sequence[float],
    candidate_costs: Sequence[float],
    *,
    samples: int,
    alpha: float,
    seed: int,
) -> tuple[float, float]:
    reference_total = math.fsum(reference_costs)
    point = (
        (reference_total - math.fsum(candidate_costs)) / reference_total
        if reference_total > 0
        else -math.inf
    )
    generator = random.Random(seed)
    count = len(reference_costs)
    estimates: list[float] = []
    for _ in range(samples):
        indices = [generator.randrange(count) for _ in range(count)]
        sampled_reference = math.fsum(reference_costs[index] for index in indices)
        sampled_candidate = math.fsum(candidate_costs[index] for index in indices)
        estimates.append(
            (sampled_reference - sampled_candidate) / sampled_reference
            if sampled_reference > 0
            else -math.inf
        )
    return point, _lower_quantile(estimates, alpha)


def _task_map(case: AssuranceCase) -> dict[str, TaskEconomics]:
    return {task.task_id: task for task in case.tasks}


def _arm_summary(arm_id: str, case: AssuranceCase, dominated: bool) -> ArmSummary:
    return ArmSummary(
        arm_id=arm_id,
        assurance_decision=case.decision.value,
        paired_tasks=len(case.tasks),
        acceptable_rate=canonical_float(case.acceptable_rate),
        mean_effective_cost_usd=canonical_float(
            case.total_effective_cost_usd / len(case.tasks)
        ),
        cost_per_acceptable_outcome_usd=canonical_float(
            case.cost_per_acceptable_outcome_usd
        ),
        expected_net_value_per_attempt_usd=canonical_float(
            case.expected_net_value_per_attempt_usd
        ),
        evidence_digest=case.evidence_digest,
        dominated=dominated,
    )


def _dominated_arms(cases: Mapping[str, AssuranceCase]) -> frozenset[str]:
    dominated: set[str] = set()
    for arm_id, case in cases.items():
        cost = case.total_effective_cost_usd / len(case.tasks)
        quality = case.acceptable_rate
        for other_id, other in cases.items():
            if other_id == arm_id:
                continue
            other_cost = other.total_effective_cost_usd / len(other.tasks)
            other_quality = other.acceptable_rate
            if (
                other_cost <= cost
                and other_quality >= quality
                and (other_cost < cost or other_quality > quality)
            ):
                dominated.add(arm_id)
                break
    return frozenset(dominated)


def evaluate_frontier(
    plan: ExperimentPlan,
    bundles: Mapping[str, EvidenceBundle],
    initial_problems: Sequence[str] = (),
) -> FrontierCase:
    problems = list(initial_problems)
    plan_problems = _validate_plan_instance(plan)
    if plan_problems:
        return FrontierCase(
            decision=FrontierDecision.INCOMPLETE,
            selected_arm=None,
            plan=plan,
            arms=(),
            comparisons=(),
            problems=tuple(problems) + plan_problems,
        )
    planned = set(plan.arm_paths)
    supplied = set(bundles)
    if supplied != planned:
        missing = sorted(planned - supplied)
        extra = sorted(supplied - planned)
        if missing:
            problems.append(f"missing planned arms: {missing}")
        if extra:
            problems.append(f"unplanned arms supplied: {extra}")

    for arm_id in sorted(planned & supplied):
        problems.extend(
            validate_evidence_bundle(
                bundles[arm_id],
                label=arm_id,
                require_explicit_costs=True,
                require_task_manifest=True,
            )
        )

    cases: dict[str, AssuranceCase] = {}
    if not problems:
        for arm_id in sorted(bundles):
            try:
                cases[arm_id] = evaluate_bundle(bundles[arm_id])
            except (ArithmeticError, TypeError, ValueError, RuntimeError) as error:
                problems.append(f"{arm_id}: assurance evaluation failed: {error}")

    for arm_id, case in cases.items():
        for label, value in (
            ("acceptable_rate", case.acceptable_rate),
            ("total_effective_cost_usd", case.total_effective_cost_usd),
            ("p95_task_cost_usd", case.p95_task_cost_usd),
            ("max_task_cost_usd", case.max_task_cost_usd),
            ("expected_net_value_per_attempt_usd", case.expected_net_value_per_attempt_usd),
            (
                "incremental_net_value_vs_baseline_usd",
                case.incremental_net_value_vs_baseline_usd,
            ),
        ):
            if not math.isfinite(value):
                problems.append(f"{arm_id}: computed {label} is not finite")
        if any(not math.isfinite(task.effective_cost_usd) for task in case.tasks):
            problems.append(f"{arm_id}: computed task cost is not finite")
        if arm_id == plan.reference_arm and case.total_effective_cost_usd <= 0:
            problems.append(
                f"{arm_id}: reference total effective cost must be greater than zero"
            )

    reference_tasks: set[str] = set()
    if plan.reference_arm in cases:
        reference_tasks = set(_task_map(cases[plan.reference_arm]))
        if len(reference_tasks) < plan.min_paired_tasks:
            problems.append(
                f"paired task count {len(reference_tasks)} is below the predeclared "
                f"minimum {plan.min_paired_tasks}"
            )
        for arm_id, case in cases.items():
            task_ids = set(_task_map(case))
            if task_ids != reference_tasks:
                problems.append(
                    f"{arm_id}: task IDs do not exactly match the reference; "
                    f"missing={sorted(reference_tasks - task_ids)}, "
                    f"extra={sorted(task_ids - reference_tasks)}"
                )

    if cases and plan.reference_arm in cases:
        reference_policy = bundles[plan.reference_arm].policy
        reference_baseline = bundles[plan.reference_arm].baseline
        reference_manifest = bundles[plan.reference_arm].task_manifest
        shared_rates: dict[str, tuple[str, Any]] = {}
        for arm_id, bundle in bundles.items():
            if bundle.policy != reference_policy:
                problems.append(
                    f"{arm_id}: economic policy differs from the reference arm"
                )
            if bundle.baseline != reference_baseline:
                problems.append(f"{arm_id}: baseline differs from the reference arm")
            if bundle.task_manifest != reference_manifest:
                problems.append(
                    f"{arm_id}: task input digests or rubric versions differ from "
                    "the reference arm"
                )
            manifest_digest = _task_manifest_digest(bundle)
            if manifest_digest != plan.task_manifest_digest:
                problems.append(
                    f"{arm_id}: task manifest digest {manifest_digest} does not "
                    f"match frozen plan digest {plan.task_manifest_digest}"
                )
            for model, rate in bundle.rates.items():
                if model in shared_rates and rate != shared_rates[model][1]:
                    problems.append(
                        f"{arm_id}: rate for shared model {model!r} differs from "
                        f"arm {shared_rates[model][0]!r}"
                    )
                else:
                    shared_rates[model] = (arm_id, rate)

    dominated = _dominated_arms(cases) if cases else frozenset()
    arm_summaries = tuple(
        _arm_summary(arm_id, cases[arm_id], arm_id in dominated)
        for arm_id in sorted(cases)
    )

    if problems or plan.reference_arm not in cases:
        return FrontierCase(
            decision=FrontierDecision.INCOMPLETE,
            selected_arm=None,
            plan=plan,
            arms=arm_summaries,
            comparisons=(),
            problems=tuple(problems),
        )

    candidate_count = len(plan.candidate_arms)
    adjusted_alpha = (1 - plan.confidence_level) / (2 * candidate_count)
    reference_case = cases[plan.reference_arm]
    reference_map = _task_map(reference_case)
    comparisons: list[PairedComparison] = []

    for candidate_id in plan.candidate_arms:
        candidate_case = cases[candidate_id]
        candidate_map = _task_map(candidate_case)
        ordered_tasks = sorted(reference_tasks)
        harmful = sum(
            reference_map[task_id].acceptable
            and not candidate_map[task_id].acceptable
            for task_id in ordered_tasks
        )
        beneficial = sum(
            not reference_map[task_id].acceptable
            and candidate_map[task_id].acceptable
            for task_id in ordered_tasks
        )
        breakage_upper = canonical_float(
            clopper_pearson_upper(harmful, len(ordered_tasks), adjusted_alpha)
        )
        quality_delta = canonical_float(
            sum(
                int(candidate_map[task_id].acceptable)
                - int(reference_map[task_id].acceptable)
                for task_id in ordered_tasks
            )
            / len(ordered_tasks)
        )
        seed_material = f"{plan.seed}:{candidate_id}".encode("utf-8")
        candidate_seed = int.from_bytes(
            hashlib.sha256(seed_material).digest()[:8], "big"
        )
        cost_point, cost_lower = _paired_cost_bootstrap(
            [reference_map[task_id].effective_cost_usd for task_id in ordered_tasks],
            [candidate_map[task_id].effective_cost_usd for task_id in ordered_tasks],
            samples=plan.bootstrap_samples,
            alpha=adjusted_alpha,
            seed=candidate_seed,
        )
        cost_point = canonical_float(cost_point)
        cost_lower = canonical_float(cost_lower)
        reasons: list[str] = []
        if reference_case.decision is not Decision.SCALE:
            reasons.append(
                f"reference assurance decision is {reference_case.decision.value}, not SCALE"
            )
        if candidate_case.decision is not Decision.SCALE:
            reasons.append(
                f"candidate assurance decision is {candidate_case.decision.value}, not SCALE"
            )
        if breakage_upper > plan.max_breakage_rate:
            reasons.append(
                f"breakage upper bound {breakage_upper:.3%} exceeds "
                f"{plan.max_breakage_rate:.3%}"
            )
        if cost_lower < plan.min_cost_reduction_rate:
            reasons.append(
                f"cost-reduction lower bound {cost_lower:.3%} is below "
                f"{plan.min_cost_reduction_rate:.3%}"
            )
        if not math.isfinite(cost_point) or not math.isfinite(cost_lower):
            reasons.append("paired cost estimate is not finite")
        comparisons.append(
            PairedComparison(
                candidate_arm=candidate_id,
                paired_tasks=len(ordered_tasks),
                harmful_regressions=harmful,
                beneficial_changes=beneficial,
                breakage_rate=canonical_float(harmful / len(ordered_tasks)),
                breakage_rate_upper=breakage_upper,
                acceptable_rate_delta=quality_delta,
                mean_cost_reduction_rate=cost_point,
                cost_reduction_rate_lower=cost_lower,
                adjusted_alpha=canonical_float(adjusted_alpha),
                eligible=not reasons,
                reasons=tuple(reasons),
            )
        )

    eligible_ids = {
        comparison.candidate_arm for comparison in comparisons if comparison.eligible
    }
    selected = (
        min(
            eligible_ids,
            key=lambda arm_id: (
                cases[arm_id].total_effective_cost_usd / len(cases[arm_id].tasks),
                -cases[arm_id].acceptable_rate,
                arm_id,
            ),
        )
        if eligible_ids
        else None
    )
    return FrontierCase(
        decision=(FrontierDecision.ADOPT if selected else FrontierDecision.HOLD),
        selected_arm=selected,
        plan=plan,
        arms=arm_summaries,
        comparisons=tuple(comparisons),
        problems=(),
    )


def run_frontier(plan_path: str | Path) -> FrontierCase:
    plan, bundles, problems = load_experiment(plan_path)
    return evaluate_frontier(plan, bundles, problems)


def frontier_payload(case: FrontierCase) -> dict[str, Any]:
    return {
        "schema": "frontier.case@1",
        "decision": case.decision.value,
        "selected_arm": case.selected_arm,
        "experiment_id": case.plan.experiment_id,
        "plan_digest": case.plan.plan_digest,
        "task_manifest_digest": case.plan.task_manifest_digest,
        "task_manifest_path": case.plan.task_manifest_path,
        "reference_arm": case.plan.reference_arm,
        "method": case.method,
        "numeric_precision_significant_digits": CANONICAL_SIGNIFICANT_DIGITS,
        "policy": {
            "max_breakage_rate": case.plan.max_breakage_rate,
            "min_cost_reduction_rate": case.plan.min_cost_reduction_rate,
            "confidence_level": case.plan.confidence_level,
            "bootstrap_samples": case.plan.bootstrap_samples,
            "seed": case.plan.seed,
            "min_paired_tasks": case.plan.min_paired_tasks,
            "expected_adjusted_tail_draws": (
                case.plan.bootstrap_samples
                * (1 - case.plan.confidence_level)
                / (2 * len(case.plan.candidate_arms))
                if case.plan.candidate_arms
                else None
            ),
        },
        "problems": list(case.problems),
        "arms": [asdict(arm) for arm in case.arms],
        "comparisons": [asdict(comparison) for comparison in case.comparisons],
    }
