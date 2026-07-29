from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any, Mapping, Sequence

from .conversion_contract import (
    load_conversion_contract,
    loads_strict_json,
    parse_baseline,
    parse_outcomes_and_manifest,
    parse_policy,
)
from .evidence import make_evidence_bundle, validate_evidence_bundle
from .models import (
    EvidenceBundle,
    ModelRate,
    Outcome,
    TaskIdentity,
    TraceEvent,
)


SOURCE_ID = "source.claude-code-jsonl"
SOURCE_VERSION = "1"
CONTRACT_SCHEMA_VERSION = 1
TASK_UNIT = "external-user-prompt"
PRIVACY_MODE = "content-redacted-type-shapes-only"
UNEXPANDED_DELEGATION_TOOLS = frozenset({"Agent", "Task"})


@dataclass(frozen=True)
class ClaudeCodeTask:
    task_id: str
    source_uuid: str
    input_digest: str
    started_at: str


@dataclass(frozen=True)
class ClaudeCodeModelCall:
    source_message_id: str
    source_record_uuids: tuple[str, ...]
    event_id: str
    task_id: str
    timestamp: str
    model: str
    usage: dict[str, Any]


@dataclass(frozen=True)
class ClaudeCodeToolCall:
    source_tool_use_id: str
    source_record_uuid: str
    result_record_uuid: str
    event_id: str
    task_id: str
    timestamp: str
    name: str
    status: str
    redacted_arguments: Any


@dataclass(frozen=True)
class ClaudeCodeSession:
    session_id: str
    raw_sha256: str
    relevant_record_count: int
    claude_code_versions: tuple[str, ...]
    tasks: tuple[ClaudeCodeTask, ...]
    model_calls: tuple[ClaudeCodeModelCall, ...]
    tool_calls: tuple[ClaudeCodeToolCall, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    inventory_sha256: str
    unexpanded_delegation_tools: tuple[str, ...]
    source_id: str = SOURCE_ID
    source_version: str = SOURCE_VERSION
    task_unit: str = TASK_UNIT
    privacy_mode: str = PRIVACY_MODE
    source_file_count: int = 1
    subagent_count: int = 0
    expanded_delegation_count: int = 0
    max_spawn_depth: int = 0


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


def _opaque_id(prefix: str, session_id: str, source_id: str) -> str:
    digest = _sha256_bytes(f"{session_id}\0{source_id}".encode("utf-8"))
    return f"{prefix}-{digest}"


def _nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _finite_number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _nonnegative_number(value: Any, *, label: str) -> float:
    number = _finite_number(value, label=label)
    if number < 0:
        raise ValueError(f"{label} must be non-negative")
    return number


def _required_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _required_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _required_list(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _required_bool(value: Any, *, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _extract_prompt_content(record: Mapping[str, Any]) -> Any | None:
    if record.get("type") != "user":
        return None
    if record.get("isSidechain") is True:
        return None
    if record.get("sourceToolAssistantUUID"):
        return None
    if record.get("userType") not in (None, "external"):
        return None
    message = record.get("message")
    if not isinstance(message, dict) or message.get("role") != "user":
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    if not content:
        return None
    text_blocks = [
        block
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    non_text_blocks = [
        block
        for block in content
        if not (isinstance(block, dict) and block.get("type") == "text")
    ]
    if non_text_blocks:
        block_types = sorted(
            {
                str(block.get("type", "unknown"))
                if isinstance(block, dict)
                else type(block).__name__
                for block in non_text_blocks
            }
        )
        raise ValueError(
            "Unsupported external user prompt content blocks: "
            + ", ".join(block_types)
        )
    if not text_blocks:
        return None
    return text_blocks


def _redact_argument_values(value: Any) -> Any:
    """Preserve type shape while discarding source keys and values."""
    if isinstance(value, dict):
        return {
            "kind": "object",
            "field_count": len(value),
            "fields": sorted(
                (_redact_argument_values(item) for item in value.values()),
                key=_canonical_json,
            ),
        }
    if isinstance(value, list):
        return {
            "kind": "array",
            "item_count": len(value),
            "sample": [_redact_argument_values(item) for item in value[:3]],
            "sample_truncated": len(value) > 3,
        }
    if value is None:
        return {"kind": "null"}
    if isinstance(value, bool):
        return {"kind": "boolean"}
    if isinstance(value, int):
        return {"kind": "integer"}
    if isinstance(value, float):
        return {"kind": "number"}
    if isinstance(value, str):
        return {"kind": "string"}
    return {"kind": "unsupported"}


def _normalize_usage(
    raw: Any,
    *,
    label: str,
    allow_zero: bool = False,
) -> dict[str, Any]:
    usage = _required_mapping(raw, label=label)
    input_tokens = _nonnegative_int(
        usage.get("input_tokens", 0), label=f"{label}.input_tokens"
    )
    output_tokens = _nonnegative_int(
        usage.get("output_tokens", 0), label=f"{label}.output_tokens"
    )
    cache_read = _nonnegative_int(
        usage.get("cache_read_input_tokens", 0),
        label=f"{label}.cache_read_input_tokens",
    )
    cache_creation_total = _nonnegative_int(
        usage.get("cache_creation_input_tokens", 0),
        label=f"{label}.cache_creation_input_tokens",
    )
    raw_cache_creation = usage.get("cache_creation", {})
    cache_creation = _required_mapping(
        raw_cache_creation, label=f"{label}.cache_creation"
    )
    normalized_cache_creation = {
        key: _nonnegative_int(
            value, label=f"{label}.cache_creation.{key}"
        )
        for key, value in sorted(cache_creation.items())
    }
    if sum(normalized_cache_creation.values()) != cache_creation_total:
        raise ValueError(
            f"{label} cache-creation buckets do not sum to "
            "cache_creation_input_tokens"
        )
    raw_server_tools = usage.get("server_tool_use", {})
    server_tools = _required_mapping(
        raw_server_tools, label=f"{label}.server_tool_use"
    )
    normalized_server_tools = {
        key: _nonnegative_int(value, label=f"{label}.server_tool_use.{key}")
        for key, value in sorted(server_tools.items())
    }
    billing_context: dict[str, str | None] = {}
    for field in ("service_tier", "speed", "inference_geo"):
        value = usage.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{label}.{field} must be a string or null")
        billing_context[field] = value
    has_usage = (
        input_tokens + output_tokens + cache_read + cache_creation_total > 0
        or any(normalized_server_tools.values())
    )
    if not has_usage and not allow_zero:
        raise ValueError(f"{label} contains no positive token usage")
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation_total,
        "cache_creation": normalized_cache_creation,
        "server_tool_use": normalized_server_tools,
        "billing_context": billing_context,
    }


def _merge_streamed_usage(
    variants: Sequence[dict[str, Any]],
    *,
    label: str,
) -> dict[str, Any]:
    if not variants:
        raise ValueError(f"{label} has no usage records")
    fixed_fields = (
        "input_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "cache_creation",
    )
    for field in fixed_fields:
        values = {
            _canonical_json(variant[field])
            for variant in variants
        }
        if len(values) != 1:
            raise ValueError(f"{label} has inconsistent {field}")

    billing_context: dict[str, str | None] = {}
    for field in ("service_tier", "speed", "inference_geo"):
        observed = {
            variant["billing_context"][field]
            for variant in variants
            if variant["billing_context"][field] is not None
        }
        if len(observed) > 1:
            raise ValueError(f"{label} has inconsistent billing context")
        billing_context[field] = next(iter(observed)) if observed else None

    server_tool_names = {
        name
        for variant in variants
        for name in variant["server_tool_use"]
    }
    first = variants[0]
    return {
        "input_tokens": first["input_tokens"],
        "output_tokens": max(
            variant["output_tokens"] for variant in variants
        ),
        "cache_read_input_tokens": first["cache_read_input_tokens"],
        "cache_creation_input_tokens": first[
            "cache_creation_input_tokens"
        ],
        "cache_creation": first["cache_creation"],
        "server_tool_use": {
            name: max(
                variant["server_tool_use"].get(name, 0)
                for variant in variants
            )
            for name in sorted(server_tool_names)
        },
        "billing_context": billing_context,
    }


def _inspect_claude_code_jsonl_bytes(
    raw_bytes: bytes,
    *,
    allow_empty_tasks: bool = False,
) -> ClaudeCodeSession:
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Claude Code JSONL must be UTF-8") from error

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            continue
        value = loads_strict_json(line, label=f"JSONL line {line_number}")
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line {line_number} must be an object")
        records.append(value)
    if not records:
        raise ValueError("Claude Code JSONL contains no records")

    relevant_records = [
        record
        for record in records
        if record.get("type") in {"user", "assistant"}
    ]
    if not relevant_records:
        raise ValueError("Claude Code JSONL contains no user or assistant records")
    if any(record.get("isSidechain") is True for record in relevant_records):
        raise ValueError(
            "Sidechain records are not supported by source.claude-code-jsonl@1"
        )

    session_ids = {
        record.get("sessionId")
        for record in relevant_records
        if isinstance(record.get("sessionId"), str) and record.get("sessionId")
    }
    if len(session_ids) != 1:
        raise ValueError("Claude Code JSONL must contain exactly one sessionId")
    session_id = next(iter(session_ids))

    records_by_uuid: dict[str, dict[str, Any]] = {}
    for record in records:
        uuid = record.get("uuid")
        if uuid is None:
            continue
        if not isinstance(uuid, str) or not uuid:
            raise ValueError("Claude Code record uuid must be a non-empty string")
        if uuid in records_by_uuid:
            raise ValueError(f"Duplicate Claude Code record uuid: {uuid!r}")
        records_by_uuid[uuid] = record
    if any(
        not isinstance(record.get("uuid"), str) or not record.get("uuid")
        for record in relevant_records
    ):
        raise ValueError("Relevant Claude Code records must have a non-empty uuid")

    task_rows: dict[str, dict[str, Any]] = {}
    task_content: dict[str, Any] = {}
    for record in relevant_records:
        content = _extract_prompt_content(record)
        if content is None:
            continue
        uuid = str(record["uuid"])
        task_rows[uuid] = record
        task_content[uuid] = content
    if not task_rows:
        raise ValueError("Claude Code JSONL contains no external user prompts")

    task_by_record_uuid: dict[str, str] = {}

    def nearest_task_uuid(record_uuid: str) -> str:
        if record_uuid in task_by_record_uuid:
            return task_by_record_uuid[record_uuid]
        visited: set[str] = set()
        current = record_uuid
        while True:
            if current in visited:
                raise ValueError("Cycle detected in Claude Code parentUuid chain")
            visited.add(current)
            if current in task_rows:
                task_by_record_uuid[record_uuid] = current
                return current
            record = records_by_uuid.get(current)
            if record is None:
                raise ValueError(
                    f"Record {record_uuid!r} has an unresolved parentUuid chain"
                )
            parent = record.get("parentUuid")
            if not isinstance(parent, str) or not parent:
                raise ValueError(
                    f"Record {record_uuid!r} is not descended from an external prompt"
                )
            current = parent

    tasks_by_source_uuid: dict[str, ClaudeCodeTask] = {}
    for source_uuid, row in task_rows.items():
        task_id = _opaque_id("cc-task", session_id, source_uuid)
        tasks_by_source_uuid[source_uuid] = ClaudeCodeTask(
            task_id=task_id,
            source_uuid=source_uuid,
            input_digest=_sha256_json(task_content[source_uuid]),
            started_at=_required_string(
                row.get("timestamp"), label=f"task {task_id} timestamp"
            ),
        )

    assistant_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in relevant_records:
        if record.get("type") != "assistant":
            continue
        message = _required_mapping(
            record.get("message"), label="assistant message"
        )
        if record.get("isApiErrorMessage") is True:
            usage = _normalize_usage(
                message.get("usage"),
                label="API error assistant usage",
                allow_zero=True,
            )
            if (
                usage["input_tokens"]
                + usage["output_tokens"]
                + usage["cache_read_input_tokens"]
                + usage["cache_creation_input_tokens"]
                > 0
                or any(usage["server_tool_use"].values())
            ):
                raise ValueError(
                    "API error assistant record contains billable usage"
                )
            continue
        message_id = _required_string(
            message.get("id"), label="assistant message.id"
        )
        assistant_groups[message_id].append(record)

    model_calls: list[ClaudeCodeModelCall] = []
    for message_id, rows in assistant_groups.items():
        models: set[str] = set()
        task_source_uuids: set[str] = set()
        requests: set[str] = set()
        usage_variants: list[dict[str, Any]] = []
        timestamps: list[str] = []
        for row in rows:
            message = _required_mapping(row.get("message"), label="assistant message")
            models.add(
                _required_string(
                    message.get("model"), label=f"message {message_id} model"
                )
            )
            task_source_uuids.add(nearest_task_uuid(str(row["uuid"])))
            request_id = row.get("requestId")
            if isinstance(request_id, str) and request_id:
                requests.add(request_id)
            usage = _normalize_usage(
                message.get("usage"), label=f"message {message_id} usage"
            )
            usage_variants.append(usage)
            timestamps.append(
                _required_string(
                    row.get("timestamp"), label=f"message {message_id} timestamp"
                )
            )
        if len(models) != 1:
            raise ValueError(f"Message {message_id!r} has inconsistent models")
        if len(task_source_uuids) != 1:
            raise ValueError(f"Message {message_id!r} crosses task boundaries")
        if len(requests) > 1:
            raise ValueError(f"Message {message_id!r} has inconsistent request IDs")
        normalized_usage = _merge_streamed_usage(
            usage_variants,
            label=f"Message {message_id!r}",
        )
        source_task_uuid = next(iter(task_source_uuids))
        model_calls.append(
            ClaudeCodeModelCall(
                source_message_id=message_id,
                source_record_uuids=tuple(
                    sorted(str(row["uuid"]) for row in rows)
                ),
                event_id=_opaque_id("cc-model", session_id, message_id),
                task_id=tasks_by_source_uuid[source_task_uuid].task_id,
                timestamp=min(timestamps),
                model=next(iter(models)),
                usage=normalized_usage,
            )
        )

    tool_results: dict[str, list[tuple[bool, str, str]]] = defaultdict(list)
    for record in relevant_records:
        if record.get("type") != "user":
            continue
        message = record.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            continue
        for block in message["content"]:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            tool_use_id = _required_string(
                block.get("tool_use_id"), label="tool_result.tool_use_id"
            )
            is_error = block.get("is_error", False)
            if not isinstance(is_error, bool):
                raise ValueError(
                    f"tool result {tool_use_id!r} is_error must be boolean"
                )
            result_task_uuid = nearest_task_uuid(str(record["uuid"]))
            tool_results[tool_use_id].append(
                (is_error, result_task_uuid, str(record["uuid"]))
            )

    tool_calls: list[ClaudeCodeToolCall] = []
    source_tool_ids: list[str] = []
    cross_task_tool_results: list[str] = []
    for record in relevant_records:
        if record.get("type") != "assistant":
            continue
        message = _required_mapping(record.get("message"), label="assistant message")
        content = _required_list(
            message.get("content"), label="assistant message.content"
        )
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            source_tool_id = _required_string(
                block.get("id"), label="tool_use.id"
            )
            source_tool_ids.append(source_tool_id)
            results = tool_results.get(source_tool_id, [])
            if len(results) != 1:
                raise ValueError(
                    f"Tool use {source_tool_id!r} must have exactly one tool result"
                )
            source_task_uuid = nearest_task_uuid(str(record["uuid"]))
            is_error, result_task_uuid, result_record_uuid = results[0]
            if result_task_uuid != source_task_uuid:
                cross_task_tool_results.append(source_tool_id)
            tool_calls.append(
                ClaudeCodeToolCall(
                    source_tool_use_id=source_tool_id,
                    source_record_uuid=str(record["uuid"]),
                    result_record_uuid=result_record_uuid,
                    event_id=_opaque_id("cc-tool", session_id, source_tool_id),
                    task_id=tasks_by_source_uuid[source_task_uuid].task_id,
                    timestamp=_required_string(
                        record.get("timestamp"),
                        label=f"tool use {source_tool_id} timestamp",
                    ),
                    name=_required_string(
                        block.get("name"), label=f"tool use {source_tool_id} name"
                    ),
                    status="error" if is_error else "ok",
                    redacted_arguments=_redact_argument_values(
                        block.get("input", {})
                    ),
                )
            )
    duplicate_tool_ids = sorted(
        source_id
        for source_id, count in Counter(source_tool_ids).items()
        if count > 1
    )
    if duplicate_tool_ids:
        raise ValueError(f"Duplicate tool use IDs: {duplicate_tool_ids}")
    if cross_task_tool_results:
        raise ValueError(
            f"Tool result {sorted(cross_task_tool_results)[0]!r} "
            "crosses task boundaries"
        )
    orphan_results = sorted(set(tool_results) - set(source_tool_ids))
    if orphan_results:
        raise ValueError(f"Orphan tool result IDs: {orphan_results}")

    tasks = tuple(sorted(tasks_by_source_uuid.values(), key=lambda item: item.task_id))
    normalized_model_calls = tuple(
        sorted(model_calls, key=lambda item: (item.task_id, item.timestamp, item.event_id))
    )
    normalized_tool_calls = tuple(
        sorted(tool_calls, key=lambda item: (item.task_id, item.timestamp, item.event_id))
    )
    tasks_with_events = {
        call.task_id for call in normalized_model_calls
    } | {call.task_id for call in normalized_tool_calls}
    empty_tasks = sorted({task.task_id for task in tasks} - tasks_with_events)
    if empty_tasks and not allow_empty_tasks:
        raise ValueError(f"External prompts contain no execution events: {empty_tasks}")

    model_event_by_record_uuid = {
        source_uuid: call.event_id
        for call in normalized_model_calls
        for source_uuid in call.source_record_uuids
    }
    tool_event_by_result_uuid = {
        call.result_record_uuid: call.event_id for call in normalized_tool_calls
    }
    event_by_record_uuid = {
        **model_event_by_record_uuid,
        **tool_event_by_result_uuid,
    }
    dependency_edges: set[tuple[str, str]] = set()
    for call in normalized_model_calls:
        for source_record_uuid in call.source_record_uuids:
            visited: set[str] = set()
            current = source_record_uuid
            while True:
                if current in visited:
                    raise ValueError(
                        "Cycle detected while resolving Claude Code event parentage"
                    )
                visited.add(current)
                row = records_by_uuid[current]
                parent = row.get("parentUuid")
                if not isinstance(parent, str) or not parent:
                    break
                if parent in task_rows:
                    break
                parent_event = event_by_record_uuid.get(parent)
                if parent_event is not None and parent_event != call.event_id:
                    dependency_edges.add((parent_event, call.event_id))
                    break
                if parent not in records_by_uuid:
                    raise ValueError(
                        f"Record {source_record_uuid!r} has unresolved event parentage"
                    )
                current = parent
    for call in normalized_tool_calls:
        model_event = model_event_by_record_uuid.get(call.source_record_uuid)
        if model_event is None:
            raise ValueError(
                f"Tool use {call.source_tool_use_id!r} has no model-call parent"
            )
        dependency_edges.add((model_event, call.event_id))
    normalized_dependency_edges = tuple(sorted(dependency_edges))

    versions = tuple(
        sorted(
            {
                str(record["version"])
                for record in relevant_records
                if isinstance(record.get("version"), str) and record.get("version")
            }
        )
    )
    inventory_payload = {
        "session_id_sha256": _sha256_bytes(session_id.encode("utf-8")),
        "tasks": [
            {
                "task_id": task.task_id,
                "input_digest": task.input_digest,
                "started_at": task.started_at,
            }
            for task in tasks
        ],
        "model_calls": [
            {
                "event_id": call.event_id,
                "task_id": call.task_id,
                "timestamp": call.timestamp,
                "model": call.model,
                "usage": call.usage,
            }
            for call in normalized_model_calls
        ],
        "tool_calls": [
            {
                "event_id": call.event_id,
                "task_id": call.task_id,
                "timestamp": call.timestamp,
                "name": call.name,
                "status": call.status,
                "redacted_arguments": call.redacted_arguments,
            }
            for call in normalized_tool_calls
        ],
        "dependency_edges": [
            list(edge) for edge in normalized_dependency_edges
        ],
    }
    delegation_tools = tuple(
        sorted(
            {
                call.name
                for call in normalized_tool_calls
                if call.name in UNEXPANDED_DELEGATION_TOOLS
            }
        )
    )
    return ClaudeCodeSession(
        session_id=session_id,
        raw_sha256=_sha256_bytes(raw_bytes),
        relevant_record_count=len(relevant_records),
        claude_code_versions=versions,
        tasks=tasks,
        model_calls=normalized_model_calls,
        tool_calls=normalized_tool_calls,
        dependency_edges=normalized_dependency_edges,
        inventory_sha256=_sha256_json(inventory_payload),
        unexpanded_delegation_tools=delegation_tools,
    )


def inspect_claude_code_jsonl(path: str | Path) -> ClaudeCodeSession:
    return _inspect_claude_code_jsonl_bytes(Path(path).read_bytes())


def conversion_contract_template(
    session: ClaudeCodeSession,
) -> dict[str, Any]:
    models = sorted({call.model for call in session.model_calls})
    cache_buckets_by_model: dict[str, set[str]] = defaultdict(set)
    billing_contexts_by_model: dict[str, set[str]] = defaultdict(set)
    for call in session.model_calls:
        cache_buckets_by_model[call.model].update(call.usage["cache_creation"])
        billing_contexts_by_model[call.model].add(
            _canonical_json(call.usage["billing_context"])
        )
    tools = sorted({call.name for call in session.tool_calls})
    server_tools = sorted(
        {
            name
            for call in session.model_calls
            for name, count in call.usage["server_tool_use"].items()
            if count
        }
    )
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "adapter": {
            "source_id": session.source_id,
            "source_version": session.source_version,
            "task_unit": session.task_unit,
            "privacy_mode": session.privacy_mode,
        },
        "source_inventory": {
            "raw_sha256": session.raw_sha256,
            "inventory_sha256": session.inventory_sha256,
            "relevant_record_count": session.relevant_record_count,
            "task_count": len(session.tasks),
            "model_call_count": len(session.model_calls),
            "tool_call_count": len(session.tool_calls),
            "dependency_edge_count": len(session.dependency_edges),
            "claude_code_versions": list(session.claude_code_versions),
            "unexpanded_delegation_tools": list(
                session.unexpanded_delegation_tools
            ),
            **(
                {
                    "source_file_count": session.source_file_count,
                    "subagent_count": session.subagent_count,
                    "expanded_delegation_count": (
                        session.expanded_delegation_count
                    ),
                    "max_spawn_depth": session.max_spawn_depth,
                }
                if session.subagent_count
                else {}
            ),
        },
        "outcome_contract": {
            "rubric_version": None,
            "label_source": None,
        },
        "tasks": [
            {
                "task_id": task.task_id,
                "input_digest": task.input_digest,
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
                    "billing_contexts": [
                        json.loads(context)
                        for context in sorted(billing_contexts_by_model[model])
                    ],
                    "tiers": [
                        {
                            "up_to_input_tokens": None,
                            "input_per_million_usd": None,
                            "output_per_million_usd": None,
                            "cache_read_per_million_usd": None,
                            "cache_write_per_million_usd": {
                                bucket: None
                                for bucket in sorted(cache_buckets_by_model[model])
                            },
                        }
                    ]
                }
                for model in models
            },
            "tools": {tool: None for tool in tools},
            "server_tools": {tool: None for tool in server_tools},
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


def inspect_to_contract_template(path: str | Path) -> dict[str, Any]:
    return conversion_contract_template(inspect_claude_code_jsonl(path))


def _validate_inventory(
    session: ClaudeCodeSession,
    raw: Any,
) -> None:
    inventory = _required_mapping(raw, label="source_inventory")
    expected = {
        "raw_sha256": session.raw_sha256,
        "inventory_sha256": session.inventory_sha256,
        "relevant_record_count": session.relevant_record_count,
        "task_count": len(session.tasks),
        "model_call_count": len(session.model_calls),
        "tool_call_count": len(session.tool_calls),
        "dependency_edge_count": len(session.dependency_edges),
        "claude_code_versions": list(session.claude_code_versions),
        "unexpanded_delegation_tools": list(session.unexpanded_delegation_tools),
        **(
            {
                "source_file_count": session.source_file_count,
                "subagent_count": session.subagent_count,
                "expanded_delegation_count": session.expanded_delegation_count,
                "max_spawn_depth": session.max_spawn_depth,
            }
            if session.subagent_count
            else {}
        ),
    }
    for field, expected_value in expected.items():
        if inventory.get(field) != expected_value:
            raise ValueError(
                f"source_inventory.{field} does not match the frozen JSONL"
            )
    if session.unexpanded_delegation_tools:
        raise ValueError(
            "Unexpanded delegation tools are not supported because their nested "
            "model calls may be absent: "
            + ", ".join(session.unexpanded_delegation_tools)
        )


def _validate_adapter_contract(session: ClaudeCodeSession, raw: Any) -> None:
    adapter = _required_mapping(raw, label="adapter")
    expected = {
        "source_id": session.source_id,
        "source_version": session.source_version,
        "task_unit": session.task_unit,
        "privacy_mode": session.privacy_mode,
    }
    for field, expected_value in expected.items():
        if adapter.get(field) != expected_value:
            raise ValueError(
                f"adapter.{field} must be {expected_value!r}"
            )


def _parse_task_contract(
    session: ClaudeCodeSession,
    raw_tasks: Any,
    outcome_contract_raw: Any,
) -> tuple[dict[str, Outcome], dict[str, TaskIdentity], str, str]:
    return parse_outcomes_and_manifest(
        raw_tasks=raw_tasks,
        outcome_contract_raw=outcome_contract_raw,
        expected_tasks={
            task.task_id: {
                "input_digest": task.input_digest,
                "started_at": task.started_at,
            }
            for task in session.tasks
        },
    )


def _parse_tiers(
    raw: Any,
    *,
    model: str,
    expected_cache_buckets: set[str],
    expected_billing_contexts: set[str],
) -> list[dict[str, Any]]:
    model_contract = _required_mapping(raw, label=f"pricing.models.{model}")
    raw_billing_contexts = _required_list(
        model_contract.get("billing_contexts"),
        label=f"pricing.models.{model}.billing_contexts",
    )
    normalized_billing_contexts = {
        _canonical_json(
            _required_mapping(
                context,
                label=f"pricing.models.{model}.billing_contexts",
            )
        )
        for context in raw_billing_contexts
    }
    if normalized_billing_contexts != expected_billing_contexts:
        raise ValueError(
            f"pricing.models.{model}.billing_contexts must exactly match "
            "the observed source contexts"
        )
    raw_tiers = _required_list(
        model_contract.get("tiers"), label=f"pricing.models.{model}.tiers"
    )
    if not raw_tiers:
        raise ValueError(f"pricing.models.{model}.tiers must not be empty")
    tiers: list[dict[str, Any]] = []
    previous_limit = -1
    saw_unbounded = False
    for index, value in enumerate(raw_tiers):
        tier = _required_mapping(
            value, label=f"pricing.models.{model}.tiers[{index}]"
        )
        raw_limit = tier.get("up_to_input_tokens")
        if raw_limit is None:
            if index != len(raw_tiers) - 1:
                raise ValueError(
                    f"pricing.models.{model} unbounded tier must be last"
                )
            limit: int | None = None
            saw_unbounded = True
        else:
            limit = _nonnegative_int(
                raw_limit,
                label=(
                    f"pricing.models.{model}.tiers[{index}]"
                    ".up_to_input_tokens"
                ),
            )
            if limit <= previous_limit:
                raise ValueError(
                    f"pricing.models.{model} tier limits must increase"
                )
            previous_limit = limit
        raw_cache_rates = _required_mapping(
            tier.get("cache_write_per_million_usd"),
            label=(
                f"pricing.models.{model}.tiers[{index}]"
                ".cache_write_per_million_usd"
            ),
        )
        if set(raw_cache_rates) != expected_cache_buckets:
            raise ValueError(
                f"pricing.models.{model} cache-write buckets must exactly match "
                "the observed source buckets"
            )
        tiers.append(
            {
                "up_to_input_tokens": limit,
                "input_per_million_usd": _nonnegative_number(
                    tier.get("input_per_million_usd"),
                    label=(
                        f"pricing.models.{model}.tiers[{index}]"
                        ".input_per_million_usd"
                    ),
                ),
                "output_per_million_usd": _nonnegative_number(
                    tier.get("output_per_million_usd"),
                    label=(
                        f"pricing.models.{model}.tiers[{index}]"
                        ".output_per_million_usd"
                    ),
                ),
                "cache_read_per_million_usd": _nonnegative_number(
                    tier.get("cache_read_per_million_usd"),
                    label=(
                        f"pricing.models.{model}.tiers[{index}]"
                        ".cache_read_per_million_usd"
                    ),
                ),
                "cache_write_per_million_usd": {
                    bucket: _nonnegative_number(
                        raw_cache_rates[bucket],
                        label=(
                            f"pricing.models.{model}.tiers[{index}]"
                            f".cache_write_per_million_usd.{bucket}"
                        ),
                    )
                    for bucket in sorted(raw_cache_rates)
                },
            }
        )
    if not saw_unbounded:
        raise ValueError(
            f"pricing.models.{model}.tiers must end with an unbounded tier"
        )
    return tiers


def _select_tier(
    tiers: Sequence[dict[str, Any]],
    *,
    total_input_tokens: int,
    model: str,
) -> dict[str, Any]:
    for tier in tiers:
        limit = tier["up_to_input_tokens"]
        if limit is None or total_input_tokens <= limit:
            return tier
    raise ValueError(
        f"No pricing tier covers {total_input_tokens} input tokens for {model!r}"
    )


def claude_code_bundle_from_session(
    session: ClaudeCodeSession,
    contract: Mapping[str, Any],
) -> EvidenceBundle:
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {CONTRACT_SCHEMA_VERSION}"
        )
    _validate_adapter_contract(session, contract.get("adapter"))
    _validate_inventory(session, contract.get("source_inventory"))
    outcomes, task_manifest, _, _ = _parse_task_contract(
        session,
        contract.get("tasks"),
        contract.get("outcome_contract"),
    )

    pricing = _required_mapping(contract.get("pricing"), label="pricing")
    price_card_id = _required_string(
        pricing.get("price_card_id"), label="pricing.price_card_id"
    )
    raw_model_contracts = _required_mapping(
        pricing.get("models"), label="pricing.models"
    )
    observed_models = {call.model for call in session.model_calls}
    if set(raw_model_contracts) != observed_models:
        raise ValueError(
            "pricing.models must exactly match the observed source models"
        )
    cache_buckets_by_model: dict[str, set[str]] = defaultdict(set)
    billing_contexts_by_model: dict[str, set[str]] = defaultdict(set)
    for call in session.model_calls:
        cache_buckets_by_model[call.model].update(call.usage["cache_creation"])
        billing_contexts_by_model[call.model].add(
            _canonical_json(call.usage["billing_context"])
        )
    tiers_by_model = {
        model: _parse_tiers(
            raw_model_contracts[model],
            model=model,
            expected_cache_buckets=cache_buckets_by_model[model],
            expected_billing_contexts=billing_contexts_by_model[model],
        )
        for model in sorted(observed_models)
    }
    rates = {
        model: ModelRate(
            input_per_million_usd=tiers[0]["input_per_million_usd"],
            output_per_million_usd=tiers[0]["output_per_million_usd"],
        )
        for model, tiers in tiers_by_model.items()
    }

    raw_tool_rates = _required_mapping(
        pricing.get("tools"), label="pricing.tools"
    )
    observed_tools = {call.name for call in session.tool_calls}
    if set(raw_tool_rates) != observed_tools:
        raise ValueError("pricing.tools must exactly match observed client tools")
    tool_rates = {
        tool: _nonnegative_number(
            raw_tool_rates[tool], label=f"pricing.tools.{tool}"
        )
        for tool in sorted(raw_tool_rates)
    }
    raw_server_tool_rates = _required_mapping(
        pricing.get("server_tools"), label="pricing.server_tools"
    )
    observed_server_tools = {
        name
        for call in session.model_calls
        for name, count in call.usage["server_tool_use"].items()
        if count
    }
    if set(raw_server_tool_rates) != observed_server_tools:
        raise ValueError(
            "pricing.server_tools must exactly match observed non-zero server tools"
        )
    server_tool_rates = {
        tool: _nonnegative_number(
            raw_server_tool_rates[tool],
            label=f"pricing.server_tools.{tool}",
        )
        for tool in sorted(raw_server_tool_rates)
    }

    events: list[TraceEvent] = []
    for call in session.model_calls:
        usage = call.usage
        total_input_tokens = (
            usage["input_tokens"]
            + usage["cache_read_input_tokens"]
            + usage["cache_creation_input_tokens"]
        )
        tier = _select_tier(
            tiers_by_model[call.model],
            total_input_tokens=total_input_tokens,
            model=call.model,
        )
        token_cost = (
            usage["input_tokens"] * tier["input_per_million_usd"]
            + usage["output_tokens"] * tier["output_per_million_usd"]
            + usage["cache_read_input_tokens"]
            * tier["cache_read_per_million_usd"]
            + sum(
                token_count
                * tier["cache_write_per_million_usd"][bucket]
                for bucket, token_count in usage["cache_creation"].items()
            )
        ) / 1_000_000
        server_tool_cost = sum(
            count * server_tool_rates[name]
            for name, count in usage["server_tool_use"].items()
            if count
        )
        cost = token_cost + server_tool_cost
        events.append(
            TraceEvent(
                task_id=call.task_id,
                event_id=call.event_id,
                timestamp=call.timestamp,
                event_type="model",
                name="claude-code.model",
                model=call.model,
                input_tokens=total_input_tokens,
                output_tokens=usage["output_tokens"],
                direct_cost_usd=cost,
                status="ok",
                arguments={
                    "price_card_id": price_card_id,
                    "pricing_tier_up_to_input_tokens": tier[
                        "up_to_input_tokens"
                    ],
                    "usage": usage,
                },
            )
        )
    for call in session.tool_calls:
        events.append(
            TraceEvent(
                task_id=call.task_id,
                event_id=call.event_id,
                timestamp=call.timestamp,
                event_type="tool",
                name=call.name,
                direct_cost_usd=tool_rates[call.name],
                status=call.status,
                arguments=call.redacted_arguments,
            )
        )

    bundle = make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates=rates,
        baseline=parse_baseline(contract.get("baseline")),
        policy=parse_policy(contract.get("policy")),
        source_id=session.source_id,
        source_version=session.source_version,
        task_manifest=task_manifest,
        dependency_edges=session.dependency_edges,
    )
    strict_problems = validate_evidence_bundle(
        bundle,
        label="Claude Code conversion",
        require_explicit_costs=True,
        require_task_manifest=True,
    )
    if strict_problems:
        raise ValueError("Invalid Claude Code conversion: " + "; ".join(strict_problems))
    return bundle


def claude_code_bundle(
    source_path: str | Path,
    contract: Mapping[str, Any],
) -> EvidenceBundle:
    return claude_code_bundle_from_session(
        inspect_claude_code_jsonl(source_path), contract
    )


def conversion_receipt(
    session: ClaudeCodeSession,
    contract: Mapping[str, Any],
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    outcome_contract = _required_mapping(
        contract.get("outcome_contract"), label="outcome_contract"
    )
    pricing = _required_mapping(contract.get("pricing"), label="pricing")
    return {
        "source_id": session.source_id,
        "source_version": session.source_version,
        "contract_schema_version": CONTRACT_SCHEMA_VERSION,
        "raw_sha256": session.raw_sha256,
        "inventory_sha256": session.inventory_sha256,
        "conversion_contract_sha256": _sha256_json(contract),
        "evidence_digest": bundle.digest,
        "task_unit": session.task_unit,
        "privacy_mode": session.privacy_mode,
        "price_card_id": _required_string(
            pricing.get("price_card_id"), label="pricing.price_card_id"
        ),
        "rubric_version": _required_string(
            outcome_contract.get("rubric_version"),
            label="outcome_contract.rubric_version",
        ),
        "label_source": _required_string(
            outcome_contract.get("label_source"),
            label="outcome_contract.label_source",
        ),
        "counts": {
            "relevant_records": session.relevant_record_count,
            "tasks": len(session.tasks),
            "model_calls": len(session.model_calls),
            "tool_calls": len(session.tool_calls),
            "dependency_edges": len(session.dependency_edges),
            **(
                {
                    "source_files": session.source_file_count,
                    "subagents": session.subagent_count,
                    "expanded_delegations": (
                        session.expanded_delegation_count
                    ),
                    "max_spawn_depth": session.max_spawn_depth,
                }
                if session.subagent_count
                else {}
            ),
        },
        "claude_code_versions": list(session.claude_code_versions),
    }
