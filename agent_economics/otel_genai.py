from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .conversion_contract import (
    load_conversion_contract,
    loads_strict_json,
    nonnegative_number,
    parse_baseline,
    parse_outcomes_and_manifest,
    parse_policy,
    required_mapping,
    required_string,
)
from .evidence import make_evidence_bundle, validate_evidence_bundle
from .models import EvidenceBundle, ModelRate, TraceEvent


SOURCE_ID = "source.otel-genai"
SOURCE_VERSION = "1"
CONTRACT_SCHEMA_VERSION = 1
TASK_UNIT = "contract-approved-otel-trace"
PRIVACY_MODE = "content-dropped-semantic-attributes-only"
SEMCONV_VERSION = "1.43.0"
SEMCONV_GENAI_COMMIT = "799e014b68f0e786dc44d9117c30758c5f864510"
TASK_MAPPING_POLICY = "one-export-trace-is-one-evaluation-task"
MODEL_OPERATIONS = frozenset(
    {
        "chat",
        "embeddings",
        "generate_content",
        "image_generation",
        "text_completion",
    }
)
TOOL_OPERATION = "execute_tool"
SAFE_ATTRIBUTES = frozenset(
    {
        "error.type",
        "gen_ai.operation.name",
        "gen_ai.provider.name",
        "gen_ai.request.model",
        "gen_ai.response.model",
        "gen_ai.tool.name",
        "gen_ai.usage.cache_creation.input_tokens",
        "gen_ai.usage.cache_read.input_tokens",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
    }
)


@dataclass(frozen=True)
class OtelGenAISpan:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    event_id: str
    task_id: str
    timestamp: str
    scope_name: str
    scope_version: str
    operation: str
    event_type: str
    model: str
    tool_name: str
    provider: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    status: str


@dataclass(frozen=True)
class OtelGenAITask:
    task_id: str
    trace_id: str
    trace_id_sha256: str
    started_at: str


@dataclass(frozen=True)
class OtelGenAISession:
    raw_sha256: str
    span_count: int
    structural_span_count: int
    tasks: tuple[OtelGenAITask, ...]
    spans: tuple[OtelGenAISpan, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    scopes: tuple[str, ...]
    inventory_sha256: str


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _opaque_id(prefix: str, *values: str) -> str:
    return f"{prefix}-{_sha256_bytes(chr(0).join(values).encode('utf-8'))}"


def _decode_identifier(value: Any, *, label: str, byte_length: int) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    if len(value) == byte_length * 2 and all(
        character in "0123456789abcdefABCDEF" for character in value
    ):
        decoded = bytes.fromhex(value)
    else:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError(
                f"{label} must be {byte_length}-byte base64 or hexadecimal"
            ) from error
    if len(decoded) != byte_length:
        raise ValueError(
            f"{label} must encode exactly {byte_length} bytes"
        )
    return decoded.hex()


def _parent_identifier(value: Any, *, label: str) -> str | None:
    if value in (None, ""):
        return None
    identifier = _decode_identifier(value, label=label, byte_length=8)
    return None if identifier == "0" * 16 else identifier


def _timestamp(value: Any, *, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{label} must be a non-negative Unix nanosecond integer")
    try:
        nanoseconds = int(value)
    except ValueError as error:
        raise ValueError(
            f"{label} must be a non-negative Unix nanosecond integer"
        ) from error
    if str(nanoseconds) != str(value) or nanoseconds < 0:
        raise ValueError(f"{label} must be a non-negative Unix nanosecond integer")
    seconds, remainder = divmod(nanoseconds, 1_000_000_000)
    try:
        prefix = datetime.fromtimestamp(seconds, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"{label} is outside the supported timestamp range") from error
    return f"{prefix}.{remainder:09d}Z"


def _decode_any_value(value: Any, *, label: str) -> Any:
    raw = required_mapping(value, label=label)
    supported = {
        "stringValue",
        "boolValue",
        "intValue",
        "doubleValue",
        "arrayValue",
        "kvlistValue",
        "bytesValue",
    }
    keys = set(raw)
    if len(keys) != 1 or not keys <= supported:
        raise ValueError(f"{label} must contain exactly one OTLP AnyValue field")
    key = next(iter(keys))
    decoded = raw[key]
    if key == "intValue":
        if isinstance(decoded, bool) or not isinstance(decoded, (str, int)):
            raise ValueError(f"{label}.intValue must be an integer")
        try:
            integer = int(decoded)
        except ValueError as error:
            raise ValueError(f"{label}.intValue must be an integer") from error
        if str(integer) != str(decoded):
            raise ValueError(f"{label}.intValue must be an integer")
        return integer
    if key == "doubleValue":
        return nonnegative_number(decoded, label=f"{label}.doubleValue")
    if key == "stringValue":
        if not isinstance(decoded, str):
            raise ValueError(f"{label}.stringValue must be a string")
        return decoded
    if key == "boolValue":
        if not isinstance(decoded, bool):
            raise ValueError(f"{label}.boolValue must be boolean")
        return decoded
    return decoded


def _safe_attributes(raw: Any, *, label: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ValueError(f"{label} must be an array")
    attributes: dict[str, Any] = {}
    seen: set[str] = set()
    for index, item in enumerate(raw):
        attribute = required_mapping(item, label=f"{label}[{index}]")
        key = required_string(
            attribute.get("key"), label=f"{label}[{index}].key"
        )
        if key in seen:
            raise ValueError(f"{label} contains duplicate attribute {key!r}")
        seen.add(key)
        if key in SAFE_ATTRIBUTES:
            attributes[key] = _decode_any_value(
                attribute.get("value"),
                label=f"{label}[{index}].value",
            )
    return attributes


def _optional_string(
    attributes: Mapping[str, Any], key: str, *, label: str
) -> str:
    value = attributes.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _required_tokens(
    attributes: Mapping[str, Any], key: str, *, label: str
) -> int:
    value = attributes.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _status(raw: Any, attributes: Mapping[str, Any], *, label: str) -> str:
    if raw is None:
        raw = {}
    status = required_mapping(raw, label=label)
    code = status.get("code", "STATUS_CODE_UNSET")
    if code not in {
        0,
        1,
        2,
        "STATUS_CODE_UNSET",
        "STATUS_CODE_OK",
        "STATUS_CODE_ERROR",
    }:
        raise ValueError(f"{label}.code is not a supported OTLP status code")
    return (
        "error"
        if code in {2, "STATUS_CODE_ERROR"} or "error.type" in attributes
        else "ok"
    )


def inspect_otel_genai_json(path: str | Path) -> OtelGenAISession:
    source = Path(path)
    raw_bytes = source.read_bytes()
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("OTLP JSON must be UTF-8") from error
    document = loads_strict_json(raw_text, label="OTLP JSON")
    root = required_mapping(document, label="OTLP JSON")
    resource_spans = root.get("resourceSpans")
    if not isinstance(resource_spans, list) or not resource_spans:
        raise ValueError("OTLP JSON resourceSpans must be a non-empty array")

    span_rows: list[dict[str, Any]] = []
    scopes: set[str] = set()
    for resource_index, resource_item in enumerate(resource_spans):
        resource = required_mapping(
            resource_item, label=f"resourceSpans[{resource_index}]"
        )
        scope_spans = resource.get("scopeSpans")
        if not isinstance(scope_spans, list) or not scope_spans:
            raise ValueError(
                f"resourceSpans[{resource_index}].scopeSpans must be a non-empty array"
            )
        for scope_index, scope_item in enumerate(scope_spans):
            scope_span = required_mapping(
                scope_item,
                label=f"resourceSpans[{resource_index}].scopeSpans[{scope_index}]",
            )
            scope = required_mapping(
                scope_span.get("scope", {}),
                label=(
                    f"resourceSpans[{resource_index}].scopeSpans[{scope_index}].scope"
                ),
            )
            scope_name = required_string(
                scope.get("name"),
                label=(
                    f"resourceSpans[{resource_index}].scopeSpans[{scope_index}]"
                    ".scope.name"
                ),
            )
            scope_version = scope.get("version", "")
            if not isinstance(scope_version, str):
                raise ValueError("OTLP instrumentation scope version must be a string")
            scope_key = (
                f"{scope_name}@{scope_version}" if scope_version else scope_name
            )
            scopes.add(scope_key)
            spans = scope_span.get("spans")
            if not isinstance(spans, list) or not spans:
                raise ValueError("OTLP scopeSpans.spans must be a non-empty array")
            for span_index, span_item in enumerate(spans):
                span = required_mapping(
                    span_item,
                    label=(
                        f"resourceSpans[{resource_index}].scopeSpans[{scope_index}]"
                        f".spans[{span_index}]"
                    ),
                )
                row_label = (
                    f"resourceSpans[{resource_index}].scopeSpans[{scope_index}]"
                    f".spans[{span_index}]"
                )
                trace_id = _decode_identifier(
                    span.get("traceId"),
                    label=f"{row_label}.traceId",
                    byte_length=16,
                )
                span_id = _decode_identifier(
                    span.get("spanId"),
                    label=f"{row_label}.spanId",
                    byte_length=8,
                )
                attributes = _safe_attributes(
                    span.get("attributes"), label=f"{row_label}.attributes"
                )
                span_rows.append(
                    {
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": _parent_identifier(
                            span.get("parentSpanId"),
                            label=f"{row_label}.parentSpanId",
                        ),
                        "timestamp": _timestamp(
                            span.get("startTimeUnixNano"),
                            label=f"{row_label}.startTimeUnixNano",
                        ),
                        "scope_name": scope_name,
                        "scope_version": scope_version,
                        "attributes": attributes,
                        "status": _status(
                            span.get("status"),
                            attributes,
                            label=f"{row_label}.status",
                        ),
                    }
                )
    if not span_rows:
        raise ValueError("OTLP JSON contains no spans")

    row_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in span_rows:
        key = (row["trace_id"], row["span_id"])
        if key in row_by_key:
            raise ValueError("OTLP JSON contains a duplicate traceId and spanId pair")
        row_by_key[key] = row

    trace_ids = sorted({row["trace_id"] for row in span_rows})
    task_by_trace = {
        trace_id: _opaque_id("otel-task", trace_id) for trace_id in trace_ids
    }
    tasks = tuple(
        OtelGenAITask(
            task_id=task_by_trace[trace_id],
            trace_id=trace_id,
            trace_id_sha256=_sha256_bytes(bytes.fromhex(trace_id)),
            started_at=min(
                row["timestamp"] for row in span_rows if row["trace_id"] == trace_id
            ),
        )
        for trace_id in trace_ids
    )

    economic_spans: list[OtelGenAISpan] = []
    economic_event_by_key: dict[tuple[str, str], str] = {}
    for row in span_rows:
        attributes = row["attributes"]
        operation = attributes.get("gen_ai.operation.name")
        if operation is None:
            continue
        if not isinstance(operation, str) or not operation:
            raise ValueError("gen_ai.operation.name must be a non-empty string")
        event_id = _opaque_id("otel-event", row["trace_id"], row["span_id"])
        if operation == TOOL_OPERATION:
            tool_name = _optional_string(
                attributes,
                "gen_ai.tool.name",
                label="gen_ai.tool.name",
            )
            if not tool_name:
                raise ValueError(
                    "execute_tool spans require gen_ai.tool.name"
                )
            event_type = "tool"
            model = ""
            input_tokens = 0
            output_tokens = 0
            cache_read = 0
            cache_creation = 0
        elif operation in MODEL_OPERATIONS:
            request_model = _optional_string(
                attributes,
                "gen_ai.request.model",
                label="gen_ai.request.model",
            )
            response_model = _optional_string(
                attributes,
                "gen_ai.response.model",
                label="gen_ai.response.model",
            )
            model = response_model or request_model
            if not model:
                raise ValueError(
                    f"{operation} spans require gen_ai.request.model or "
                    "gen_ai.response.model"
                )
            event_type = "model"
            tool_name = ""
            input_tokens = _required_tokens(
                attributes,
                "gen_ai.usage.input_tokens",
                label="gen_ai.usage.input_tokens",
            )
            output_tokens = _required_tokens(
                attributes,
                "gen_ai.usage.output_tokens",
                label="gen_ai.usage.output_tokens",
            )
            if input_tokens + output_tokens <= 0:
                raise ValueError("GenAI model spans require positive token usage")
            cache_read = attributes.get(
                "gen_ai.usage.cache_read.input_tokens", 0
            )
            cache_creation = attributes.get(
                "gen_ai.usage.cache_creation.input_tokens", 0
            )
            for label, value in (
                ("gen_ai.usage.cache_read.input_tokens", cache_read),
                ("gen_ai.usage.cache_creation.input_tokens", cache_creation),
            ):
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f"{label} must be a non-negative integer")
        else:
            raise ValueError(
                f"Unsupported economic gen_ai.operation.name: {operation!r}"
            )
        economic_event_by_key[(row["trace_id"], row["span_id"])] = event_id
        economic_spans.append(
            OtelGenAISpan(
                trace_id=row["trace_id"],
                span_id=row["span_id"],
                parent_span_id=row["parent_span_id"],
                event_id=event_id,
                task_id=task_by_trace[row["trace_id"]],
                timestamp=row["timestamp"],
                scope_name=row["scope_name"],
                scope_version=row["scope_version"],
                operation=operation,
                event_type=event_type,
                model=model,
                tool_name=tool_name,
                provider=_optional_string(
                    attributes,
                    "gen_ai.provider.name",
                    label="gen_ai.provider.name",
                ),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_input_tokens=cache_read,
                cache_creation_input_tokens=cache_creation,
                status=row["status"],
            )
        )
    if not economic_spans:
        raise ValueError("OTLP JSON contains no supported GenAI economic spans")

    dependency_edges: set[tuple[str, str]] = set()
    for span in economic_spans:
        parent = span.parent_span_id
        visited = {span.span_id}
        while parent is not None:
            if parent in visited:
                raise ValueError("Cycle detected in OTLP parentSpanId chain")
            visited.add(parent)
            parent_key = (span.trace_id, parent)
            parent_row = row_by_key.get(parent_key)
            if parent_row is None:
                raise ValueError(
                    "OTLP span has an unresolved parentSpanId in the export"
                )
            parent_event = economic_event_by_key.get(parent_key)
            if parent_event is not None:
                dependency_edges.add((parent_event, span.event_id))
                break
            parent = parent_row["parent_span_id"]

    normalized_spans = tuple(
        sorted(
            economic_spans,
            key=lambda span: (span.task_id, span.timestamp, span.event_id),
        )
    )
    normalized_edges = tuple(sorted(dependency_edges))
    inventory_payload = {
        "semconv_version": SEMCONV_VERSION,
        "semconv_genai_commit": SEMCONV_GENAI_COMMIT,
        "span_count": len(span_rows),
        "structural_span_count": len(span_rows) - len(normalized_spans),
        "tasks": [
            {
                "task_id": task.task_id,
                "trace_id_sha256": task.trace_id_sha256,
                "started_at": task.started_at,
            }
            for task in tasks
        ],
        "economic_spans": [
            {
                "event_id": span.event_id,
                "task_id": span.task_id,
                "timestamp": span.timestamp,
                "scope": (
                    f"{span.scope_name}@{span.scope_version}"
                    if span.scope_version
                    else span.scope_name
                ),
                "operation": span.operation,
                "event_type": span.event_type,
                "model": span.model,
                "tool_name": span.tool_name,
                "provider": span.provider,
                "input_tokens": span.input_tokens,
                "output_tokens": span.output_tokens,
                "cache_read_input_tokens": span.cache_read_input_tokens,
                "cache_creation_input_tokens": span.cache_creation_input_tokens,
                "status": span.status,
            }
            for span in normalized_spans
        ],
        "dependency_edges": [list(edge) for edge in normalized_edges],
    }
    return OtelGenAISession(
        raw_sha256=_sha256_bytes(raw_bytes),
        span_count=len(span_rows),
        structural_span_count=len(span_rows) - len(normalized_spans),
        tasks=tasks,
        spans=normalized_spans,
        dependency_edges=normalized_edges,
        scopes=tuple(sorted(scopes)),
        inventory_sha256=_sha256_json(inventory_payload),
    )


def conversion_contract_template(session: OtelGenAISession) -> dict[str, Any]:
    models = sorted({span.model for span in session.spans if span.event_type == "model"})
    tools = sorted(
        {span.tool_name for span in session.spans if span.event_type == "tool"}
    )
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "adapter": {
            "source_id": SOURCE_ID,
            "source_version": SOURCE_VERSION,
            "task_unit": TASK_UNIT,
            "privacy_mode": PRIVACY_MODE,
            "semantic_conventions_version": SEMCONV_VERSION,
            "semantic_conventions_genai_commit": SEMCONV_GENAI_COMMIT,
        },
        "source_inventory": {
            "raw_sha256": session.raw_sha256,
            "inventory_sha256": session.inventory_sha256,
            "span_count": session.span_count,
            "structural_span_count": session.structural_span_count,
            "task_count": len(session.tasks),
            "model_call_count": sum(
                span.event_type == "model" for span in session.spans
            ),
            "tool_call_count": sum(
                span.event_type == "tool" for span in session.spans
            ),
            "dependency_edge_count": len(session.dependency_edges),
            "scopes": list(session.scopes),
        },
        "task_mapping": {
            "policy": TASK_MAPPING_POLICY,
            "approved_by": None,
        },
        "outcome_contract": {
            "rubric_version": None,
            "label_source": None,
        },
        "tasks": [
            {
                "task_id": task.task_id,
                "trace_id_sha256": task.trace_id_sha256,
                "input_digest": None,
                "started_at": task.started_at,
                "acceptable": None,
                "business_value_usd": None,
                "human_minutes": None,
                "remediation_cost_usd": None,
                "incident_loss_usd": None,
            }
            for task in session.tasks
        ],
        "pricing": {
            "price_card_id": None,
            "models": {
                model: {
                    "input_per_million_usd": None,
                    "output_per_million_usd": None,
                }
                for model in models
            },
            "tools": {tool: None for tool in tools},
        },
        "baseline": {
            "name": None,
            "cost_per_attempt_usd": None,
            "acceptable_rate": None,
            "value_per_acceptable_outcome_usd": None,
        },
        "policy": {
            "human_hourly_cost_usd": None,
            "min_acceptable_rate": None,
            "max_cost_per_acceptable_outcome_usd": None,
            "max_p95_task_cost_usd": None,
            "max_trace_cost_per_task_usd": None,
            "max_calls_per_task": None,
            "min_expected_net_value_per_attempt_usd": None,
            "min_incremental_net_value_vs_baseline_usd": None,
            "repetition_warning_threshold": None,
        },
    }


def _validate_fixed_contract(session: OtelGenAISession, contract: Mapping[str, Any]) -> None:
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {CONTRACT_SCHEMA_VERSION}")
    adapter = required_mapping(contract.get("adapter"), label="adapter")
    expected_adapter = conversion_contract_template(session)["adapter"]
    for field, expected in expected_adapter.items():
        if adapter.get(field) != expected:
            raise ValueError(f"adapter.{field} must be {expected!r}")
    inventory = required_mapping(
        contract.get("source_inventory"), label="source_inventory"
    )
    expected_inventory = conversion_contract_template(session)["source_inventory"]
    for field, expected in expected_inventory.items():
        if inventory.get(field) != expected:
            raise ValueError(
                f"source_inventory.{field} does not match the frozen OTLP JSON"
            )
    task_mapping = required_mapping(
        contract.get("task_mapping"), label="task_mapping"
    )
    if task_mapping.get("policy") != TASK_MAPPING_POLICY:
        raise ValueError(
            f"task_mapping.policy must be {TASK_MAPPING_POLICY!r}"
        )
    required_string(
        task_mapping.get("approved_by"), label="task_mapping.approved_by"
    )


def otel_genai_bundle_from_session(
    session: OtelGenAISession,
    contract: Mapping[str, Any],
) -> EvidenceBundle:
    _validate_fixed_contract(session, contract)
    outcomes, task_manifest, _, _ = parse_outcomes_and_manifest(
        raw_tasks=contract.get("tasks"),
        outcome_contract_raw=contract.get("outcome_contract"),
        expected_tasks={
            task.task_id: {
                "input_digest": None,
                "started_at": task.started_at,
            }
            for task in session.tasks
        },
    )
    raw_task_rows = required_mapping(
        {
            required_string(row.get("task_id"), label="tasks[].task_id"): row
            for row in contract.get("tasks", [])
            if isinstance(row, dict)
        },
        label="tasks",
    )
    for task in session.tasks:
        if raw_task_rows[task.task_id].get("trace_id_sha256") != task.trace_id_sha256:
            raise ValueError(
                f"Task {task.task_id!r} trace_id_sha256 does not match source"
            )

    pricing = required_mapping(contract.get("pricing"), label="pricing")
    price_card_id = required_string(
        pricing.get("price_card_id"), label="pricing.price_card_id"
    )
    raw_models = required_mapping(pricing.get("models"), label="pricing.models")
    observed_models = {
        span.model for span in session.spans if span.event_type == "model"
    }
    if set(raw_models) != observed_models:
        raise ValueError(
            "pricing.models must exactly match the observed source models"
        )
    rates = {
        model: ModelRate(
            input_per_million_usd=nonnegative_number(
                required_mapping(
                    raw_models[model], label=f"pricing.models.{model}"
                ).get("input_per_million_usd"),
                label=f"pricing.models.{model}.input_per_million_usd",
            ),
            output_per_million_usd=nonnegative_number(
                required_mapping(
                    raw_models[model], label=f"pricing.models.{model}"
                ).get("output_per_million_usd"),
                label=f"pricing.models.{model}.output_per_million_usd",
            ),
        )
        for model in sorted(observed_models)
    }
    raw_tools = required_mapping(pricing.get("tools"), label="pricing.tools")
    observed_tools = {
        span.tool_name for span in session.spans if span.event_type == "tool"
    }
    if set(raw_tools) != observed_tools:
        raise ValueError(
            "pricing.tools must exactly match the observed source tools"
        )
    tool_rates = {
        tool: nonnegative_number(
            raw_tools[tool], label=f"pricing.tools.{tool}"
        )
        for tool in sorted(observed_tools)
    }

    events = []
    for span in session.spans:
        arguments = {
            "operation": span.operation,
            "provider": span.provider,
            "instrumentation_scope": (
                f"{span.scope_name}@{span.scope_version}"
                if span.scope_version
                else span.scope_name
            ),
            "price_card_id": price_card_id,
        }
        if span.event_type == "model":
            arguments["cache_read_input_tokens"] = span.cache_read_input_tokens
            arguments[
                "cache_creation_input_tokens"
            ] = span.cache_creation_input_tokens
            events.append(
                TraceEvent(
                    task_id=span.task_id,
                    event_id=span.event_id,
                    timestamp=span.timestamp,
                    event_type="model",
                    name=f"otel.gen_ai.{span.operation}",
                    model=span.model,
                    input_tokens=span.input_tokens,
                    output_tokens=span.output_tokens,
                    status=span.status,
                    arguments=arguments,
                )
            )
        else:
            events.append(
                TraceEvent(
                    task_id=span.task_id,
                    event_id=span.event_id,
                    timestamp=span.timestamp,
                    event_type="tool",
                    name=span.tool_name,
                    direct_cost_usd=tool_rates[span.tool_name],
                    status=span.status,
                    arguments=arguments,
                )
            )
    bundle = make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates=rates,
        baseline=parse_baseline(contract.get("baseline")),
        policy=parse_policy(contract.get("policy")),
        source_id=SOURCE_ID,
        source_version=SOURCE_VERSION,
        task_manifest=task_manifest,
        dependency_edges=session.dependency_edges,
    )
    problems = validate_evidence_bundle(
        bundle,
        label="OpenTelemetry GenAI conversion",
        require_explicit_costs=True,
        require_task_manifest=True,
    )
    if problems:
        raise ValueError(
            "Invalid OpenTelemetry GenAI conversion: " + "; ".join(problems)
        )
    return bundle


def otel_genai_bundle(
    source_path: str | Path,
    contract: Mapping[str, Any],
) -> EvidenceBundle:
    return otel_genai_bundle_from_session(
        inspect_otel_genai_json(source_path), contract
    )


def conversion_receipt(
    session: OtelGenAISession,
    contract: Mapping[str, Any],
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    outcome_contract = required_mapping(
        contract.get("outcome_contract"), label="outcome_contract"
    )
    pricing = required_mapping(contract.get("pricing"), label="pricing")
    task_mapping = required_mapping(
        contract.get("task_mapping"), label="task_mapping"
    )
    return {
        "source_id": SOURCE_ID,
        "source_version": SOURCE_VERSION,
        "contract_schema_version": CONTRACT_SCHEMA_VERSION,
        "raw_sha256": session.raw_sha256,
        "inventory_sha256": session.inventory_sha256,
        "conversion_contract_sha256": _sha256_json(contract),
        "evidence_digest": bundle.digest,
        "task_unit": TASK_UNIT,
        "privacy_mode": PRIVACY_MODE,
        "semantic_conventions_version": SEMCONV_VERSION,
        "semantic_conventions_genai_commit": SEMCONV_GENAI_COMMIT,
        "price_card_id": required_string(
            pricing.get("price_card_id"), label="pricing.price_card_id"
        ),
        "rubric_version": required_string(
            outcome_contract.get("rubric_version"),
            label="outcome_contract.rubric_version",
        ),
        "label_source": required_string(
            outcome_contract.get("label_source"),
            label="outcome_contract.label_source",
        ),
        "task_mapping_approved_by": required_string(
            task_mapping.get("approved_by"), label="task_mapping.approved_by"
        ),
        "counts": {
            "spans": session.span_count,
            "structural_spans": session.structural_span_count,
            "tasks": len(session.tasks),
            "model_calls": sum(
                span.event_type == "model" for span in session.spans
            ),
            "tool_calls": sum(
                span.event_type == "tool" for span in session.spans
            ),
            "dependency_edges": len(session.dependency_edges),
        },
        "scopes": list(session.scopes),
    }


__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "PRIVACY_MODE",
    "SEMCONV_GENAI_COMMIT",
    "SEMCONV_VERSION",
    "SOURCE_ID",
    "SOURCE_VERSION",
    "TASK_UNIT",
    "OtelGenAISession",
    "conversion_contract_template",
    "conversion_receipt",
    "inspect_otel_genai_json",
    "load_conversion_contract",
    "otel_genai_bundle",
    "otel_genai_bundle_from_session",
]
