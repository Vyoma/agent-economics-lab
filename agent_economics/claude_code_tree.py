from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .claude_code import (
    ClaudeCodeSession,
    ClaudeCodeToolCall,
    _inspect_claude_code_jsonl_bytes,
    claude_code_bundle_from_session,
)
from .conversion_contract import loads_strict_json
from .models import EvidenceBundle


SOURCE_ID = "source.claude-code-session-tree"
SOURCE_VERSION = "1"
TASK_UNIT = "root-external-user-prompt"
PRIVACY_MODE = "content-redacted-type-shapes-only"
DELEGATION_TOOLS = frozenset({"Agent", "Task"})


@dataclass(frozen=True)
class _SubagentSource:
    agent_id: str
    tool_use_id: str
    claimed_spawn_depth: int | None
    transcript_bytes: bytes
    metadata_bytes: bytes
    session: ClaudeCodeSession


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


def _required_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _jsonl_records(raw_bytes: bytes, *, label: str) -> list[dict[str, Any]]:
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} must be UTF-8") from error
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            continue
        value = loads_strict_json(
            line,
            label=f"{label} line {line_number}",
        )
        if not isinstance(value, dict):
            raise ValueError(f"{label} line {line_number} must be an object")
        records.append(value)
    if not records:
        raise ValueError(f"{label} contains no records")
    return records


def _tool_use_blocks(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    message = record.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [
        block
        for block in content
        if isinstance(block, dict) and block.get("type") == "tool_use"
    ]


def _contains_tool_result(record: Mapping[str, Any], tool_use_id: str) -> bool:
    message = record.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content")
    if not isinstance(content, list):
        return False
    return any(
        isinstance(block, dict)
        and block.get("type") == "tool_result"
        and block.get("tool_use_id") == tool_use_id
        for block in content
    )


def _prepare_parent_transcript(raw_bytes: bytes) -> bytes:
    records = _jsonl_records(raw_bytes, label="parent Claude Code JSONL")
    changed = False
    for record in records:
        if (
            record.get("type") != "user"
            or record.get("isSidechain") is True
            or record.get("sourceToolAssistantUUID")
            or record.get("userType") not in (None, "external")
        ):
            continue
        message = record.get("message")
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        if all(
            isinstance(block, dict) and block.get("type") == "text"
            for block in content
        ):
            continue
        message["content"] = _canonical_json(content)
        changed = True
    if not changed:
        return raw_bytes
    return (
        "".join(_canonical_json(record) + "\n" for record in records)
    ).encode("utf-8")


def _prepare_subagent_transcript(
    raw_bytes: bytes,
    *,
    agent_id: str,
    tool_use_id: str,
) -> tuple[bytes, str]:
    records = _jsonl_records(
        raw_bytes,
        label=f"subagent {agent_id!r} JSONL",
    )
    relevant_indexes = [
        index
        for index, record in enumerate(records)
        if record.get("type") in {"user", "assistant"}
    ]
    if not relevant_indexes:
        raise ValueError(f"Subagent {agent_id!r} has no user or assistant records")
    for record in records:
        record_agent_id = record.get("agentId")
        if record_agent_id is not None and record_agent_id != agent_id:
            raise ValueError(
                f"Subagent {agent_id!r} record agentId does not match its filename"
            )
    for index in relevant_indexes:
        record = records[index]
        if record.get("agentId") != agent_id:
            raise ValueError(
                f"Subagent {agent_id!r} record agentId does not match its filename"
            )
        if record.get("isSidechain") is False:
            raise ValueError(
                f"Subagent {agent_id!r} contains a non-sidechain message"
            )

    first_index = relevant_indexes[0]
    first = records[first_index]
    if first.get("parentUuid") not in (None, ""):
        raise ValueError(
            f"Subagent {agent_id!r} must begin at a local parent boundary"
        )

    if first.get("type") == "assistant":
        all_blocks = _tool_use_blocks(first)
        blocks = [
            block
            for block in all_blocks
            if block.get("id") == tool_use_id
            and block.get("name") in DELEGATION_TOOLS
        ]
        if len(all_blocks) != 1 or len(blocks) != 1:
            raise ValueError(
                f"Subagent {agent_id!r} bootstrap must bind its delegation tool"
            )
        if len(relevant_indexes) < 2:
            raise ValueError(
                f"Subagent {agent_id!r} bootstrap has no prompt envelope"
            )
        prompt_index = relevant_indexes[1]
        prompt_record = records[prompt_index]
        if prompt_record.get("type") != "user" or not _contains_tool_result(
            prompt_record, tool_use_id
        ):
            raise ValueError(
                f"Subagent {agent_id!r} bootstrap result does not match "
                "its delegation tool"
            )
        prompt_message = prompt_record.get("message")
        prompt_content = (
            prompt_message.get("content")
            if isinstance(prompt_message, dict)
            else None
        )
        if not isinstance(prompt_content, list) or any(
            not isinstance(block, dict)
            or block.get("type") not in {"text", "tool_result"}
            or (
                block.get("type") == "tool_result"
                and block.get("tool_use_id") != tool_use_id
            )
            for block in prompt_content
        ):
            raise ValueError(
                f"Subagent {agent_id!r} bootstrap prompt envelope is ambiguous"
            )
        prompt_material = blocks[0].get("input", {})
        del records[first_index]
        if prompt_index > first_index:
            prompt_index -= 1
        prompt_record = records[prompt_index]
        prompt_record["message"] = {
            "role": "user",
            "content": _canonical_json(prompt_material),
        }
        prompt_record["parentUuid"] = None
        prompt_record["userType"] = "external"
        prompt_record.pop("sourceToolAssistantUUID", None)
    elif first.get("type") == "user":
        prompt_record = first
        prompt_record["userType"] = "external"
    else:
        raise ValueError(
            f"Subagent {agent_id!r} has an unsupported transcript bootstrap"
        )

    for record in records:
        if record.get("type") in {"user", "assistant"}:
            record["isSidechain"] = False
        if record.get("type") == "user" and record is not prompt_record:
            record["userType"] = "internal"

    normalized = (
        "".join(_canonical_json(record) + "\n" for record in records)
    ).encode("utf-8")
    session_ids = {
        record.get("sessionId")
        for record in records
        if record.get("type") in {"user", "assistant"}
        and isinstance(record.get("sessionId"), str)
        and record.get("sessionId")
    }
    if len(session_ids) != 1:
        raise ValueError(
            f"Subagent {agent_id!r} must contain exactly one sessionId"
        )
    session_id = next(iter(session_ids))
    parent_session_ids = {
        record.get("parentSessionId")
        for record in records
        if record.get("parentSessionId") is not None
    }
    if parent_session_ids and parent_session_ids != {session_id}:
        raise ValueError(
            f"Subagent {agent_id!r} parentSessionId does not match its session"
        )
    return normalized, session_id


def _agent_id_from_transcript(path: Path) -> str:
    prefix = "agent-"
    suffix = ".jsonl"
    if not path.name.startswith(prefix) or not path.name.endswith(suffix):
        raise ValueError(f"Unsupported subagent transcript name: {path.name!r}")
    return _required_string(
        path.name[len(prefix) : -len(suffix)],
        label="subagent filename agent ID",
    )


def _agent_id_from_metadata(path: Path) -> str:
    prefix = "agent-"
    suffix = ".meta.json"
    if not path.name.startswith(prefix) or not path.name.endswith(suffix):
        raise ValueError(f"Unsupported subagent metadata name: {path.name!r}")
    return _required_string(
        path.name[len(prefix) : -len(suffix)],
        label="subagent metadata agent ID",
    )


def _load_metadata(
    path: Path,
    *,
    agent_id: str,
) -> tuple[dict[str, Any], bytes]:
    raw_bytes = path.read_bytes()
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"Subagent {agent_id!r} metadata must be UTF-8"
        ) from error
    value = loads_strict_json(
        raw_text,
        label=f"subagent {agent_id!r} metadata",
    )
    if not isinstance(value, dict):
        raise ValueError(f"Subagent {agent_id!r} metadata must be an object")
    return value, raw_bytes


def _delegation_calls(
    sessions: Mapping[str | None, ClaudeCodeSession],
) -> tuple[
    dict[str, tuple[str | None, ClaudeCodeToolCall]],
    list[tuple[str | None, ClaudeCodeToolCall]],
]:
    calls_by_source_id: dict[str, tuple[str | None, ClaudeCodeToolCall]] = {}
    delegation: list[tuple[str | None, ClaudeCodeToolCall]] = []
    duplicates: list[str] = []
    for owner, session in sessions.items():
        for call in session.tool_calls:
            if call.source_tool_use_id in calls_by_source_id:
                duplicates.append(call.source_tool_use_id)
            else:
                calls_by_source_id[call.source_tool_use_id] = (owner, call)
            if call.name in DELEGATION_TOOLS:
                delegation.append((owner, call))
    if duplicates:
        raise ValueError(
            "Duplicate tool use IDs across the session tree: "
            + ", ".join(sorted(set(duplicates)))
        )
    return calls_by_source_id, delegation


def _event_boundaries(
    event_timestamps: Mapping[str, str],
    dependency_edges: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    event_ids = set(event_timestamps)
    adjacency: dict[str, set[str]] = {
        event_id: set() for event_id in event_ids
    }
    for source, target in dependency_edges:
        if source in event_ids and target in event_ids:
            adjacency[source].add(target)

    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for neighbor in sorted(adjacency[node]):
            if neighbor not in indexes:
                visit(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[neighbor])
        if lowlinks[node] != indexes[node]:
            return
        component: list[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        components.append(tuple(sorted(component)))

    for event_id in sorted(event_ids):
        if event_id not in indexes:
            visit(event_id)

    component_by_event = {
        event_id: component_index
        for component_index, component in enumerate(components)
        for event_id in component
    }
    incoming_components: set[int] = set()
    outgoing_components: set[int] = set()
    for source, targets in adjacency.items():
        source_component = component_by_event[source]
        for target in targets:
            target_component = component_by_event[target]
            if source_component == target_component:
                continue
            outgoing_components.add(source_component)
            incoming_components.add(target_component)

    root_components = [
        component
        for component_index, component in enumerate(components)
        if component_index not in incoming_components
    ]
    leaf_components = [
        component
        for component_index, component in enumerate(components)
        if component_index not in outgoing_components
    ]
    roots = tuple(
        sorted(
            min(
                component,
                key=lambda event_id: (
                    event_timestamps[event_id],
                    event_id,
                ),
            )
            for component in root_components
        )
    )
    leaves = tuple(
        sorted(
            max(
                component,
                key=lambda event_id: (
                    event_timestamps[event_id],
                    event_id,
                ),
            )
            for component in leaf_components
        )
    )
    return roots, leaves


def inspect_claude_code_session_tree(path: str | Path) -> ClaudeCodeSession:
    parent_path = Path(path)
    if not parent_path.is_file():
        raise ValueError("Claude Code session-tree input must be a parent JSONL file")
    if parent_path.is_symlink():
        raise ValueError("Claude Code session-tree parent must not be a symlink")
    subagent_dir = parent_path.with_suffix("") / "subagents"
    if not subagent_dir.is_dir():
        raise ValueError(
            "Claude Code session tree has no adjacent subagents directory"
        )
    if subagent_dir.is_symlink():
        raise ValueError("Claude Code subagents directory must not be a symlink")

    transcript_paths = sorted(subagent_dir.glob("agent-*.jsonl"))
    metadata_paths = sorted(subagent_dir.glob("agent-*.meta.json"))
    unknown_jsonl = sorted(
        set(subagent_dir.glob("*.jsonl")) - set(transcript_paths)
    )
    if unknown_jsonl:
        raise ValueError(
            "Unsupported JSONL files in the subagent tree: "
            + ", ".join(path.name for path in unknown_jsonl)
        )
    if not transcript_paths and not metadata_paths:
        raise ValueError("Claude Code session tree contains no subagent files")
    if any(path.is_symlink() for path in transcript_paths + metadata_paths):
        raise ValueError("Claude Code session-tree files must not be symlinks")

    transcripts_by_agent = {
        _agent_id_from_transcript(source): source
        for source in transcript_paths
    }
    metadata_by_agent = {
        _agent_id_from_metadata(source): source
        for source in metadata_paths
    }
    if set(transcripts_by_agent) != set(metadata_by_agent):
        missing_transcripts = sorted(set(metadata_by_agent) - set(transcripts_by_agent))
        missing_metadata = sorted(set(transcripts_by_agent) - set(metadata_by_agent))
        details: list[str] = []
        if missing_transcripts:
            details.append("missing transcripts: " + ", ".join(missing_transcripts))
        if missing_metadata:
            details.append("missing metadata: " + ", ".join(missing_metadata))
        raise ValueError("Unpaired subagent files: " + "; ".join(details))

    parent_bytes = parent_path.read_bytes()
    parent = _inspect_claude_code_jsonl_bytes(
        _prepare_parent_transcript(parent_bytes)
    )
    subagents: dict[str, _SubagentSource] = {}
    source_manifest: list[dict[str, Any]] = [
        {
            "role": "parent-transcript",
            "raw_sha256": _sha256_bytes(parent_bytes),
        }
    ]
    tool_use_ids: list[str] = []
    for agent_id in sorted(transcripts_by_agent):
        transcript_bytes = transcripts_by_agent[agent_id].read_bytes()
        metadata, metadata_bytes = _load_metadata(
            metadata_by_agent[agent_id],
            agent_id=agent_id,
        )
        tool_use_id = _required_string(
            metadata.get("toolUseId"),
            label=f"subagent {agent_id!r} metadata.toolUseId",
        )
        tool_use_ids.append(tool_use_id)
        raw_depth = metadata.get("spawnDepth")
        if raw_depth is None:
            claimed_depth = None
        elif isinstance(raw_depth, bool) or not isinstance(raw_depth, int):
            raise ValueError(
                f"Subagent {agent_id!r} metadata.spawnDepth must be an integer"
            )
        elif raw_depth < 1:
            raise ValueError(
                f"Subagent {agent_id!r} metadata.spawnDepth must be positive"
            )
        else:
            claimed_depth = raw_depth
        normalized_bytes, child_session_id = _prepare_subagent_transcript(
            transcript_bytes,
            agent_id=agent_id,
            tool_use_id=tool_use_id,
        )
        if child_session_id != parent.session_id:
            raise ValueError(
                f"Subagent {agent_id!r} sessionId does not match the parent"
            )
        child = _inspect_claude_code_jsonl_bytes(
            normalized_bytes,
            allow_empty_tasks=True,
        )
        subagents[agent_id] = _SubagentSource(
            agent_id=agent_id,
            tool_use_id=tool_use_id,
            claimed_spawn_depth=claimed_depth,
            transcript_bytes=transcript_bytes,
            metadata_bytes=metadata_bytes,
            session=child,
        )
        opaque_agent_id = _sha256_bytes(agent_id.encode("utf-8"))
        source_manifest.extend(
            [
                {
                    "role": "subagent-transcript",
                    "agent_id_sha256": opaque_agent_id,
                    "raw_sha256": _sha256_bytes(transcript_bytes),
                },
                {
                    "role": "subagent-metadata",
                    "agent_id_sha256": opaque_agent_id,
                    "raw_sha256": _sha256_bytes(metadata_bytes),
                },
            ]
        )
    duplicate_meta_tools = sorted(
        tool_use_id
        for tool_use_id, count in Counter(tool_use_ids).items()
        if count > 1
    )
    if duplicate_meta_tools:
        raise ValueError(
            "Multiple subagents bind the same delegation tool: "
            + ", ".join(duplicate_meta_tools)
        )

    sessions: dict[str | None, ClaudeCodeSession] = {
        None: parent,
        **{agent_id: source.session for agent_id, source in subagents.items()},
    }
    calls_by_source_id, delegation_calls = _delegation_calls(sessions)
    spawn_owner: dict[str, str | None] = {}
    spawn_call: dict[str, ClaudeCodeToolCall] = {}
    for agent_id, source in subagents.items():
        match = calls_by_source_id.get(source.tool_use_id)
        if match is None:
            raise ValueError(
                f"Subagent {agent_id!r} metadata references an unknown "
                "delegation tool"
            )
        owner, call = match
        if call.name not in DELEGATION_TOOLS:
            raise ValueError(
                f"Subagent {agent_id!r} metadata does not reference "
                "an Agent or Task call"
            )
        if owner == agent_id:
            raise ValueError(f"Subagent {agent_id!r} cannot spawn itself")
        spawn_owner[agent_id] = owner
        spawn_call[agent_id] = call

    covered_tools = set(tool_use_ids)
    unexpanded = tuple(
        sorted(
            {
                call.name
                for _, call in delegation_calls
                if call.source_tool_use_id not in covered_tools
            }
        )
    )

    resolved_task: dict[str, str] = {}
    resolved_depth: dict[str, int] = {}

    def resolve_agent(agent_id: str, trail: tuple[str, ...] = ()) -> tuple[str, int]:
        if agent_id in resolved_task:
            return resolved_task[agent_id], resolved_depth[agent_id]
        if agent_id in trail:
            raise ValueError("Cycle detected in subagent spawn metadata")
        owner = spawn_owner[agent_id]
        if owner is None:
            task_id = spawn_call[agent_id].task_id
            depth = 1
        else:
            task_id, owner_depth = resolve_agent(owner, trail + (agent_id,))
            depth = owner_depth + 1
        claimed_depth = subagents[agent_id].claimed_spawn_depth
        if claimed_depth is not None and claimed_depth != depth:
            raise ValueError(
                f"Subagent {agent_id!r} spawnDepth does not match "
                "the transcript tree"
            )
        resolved_task[agent_id] = task_id
        resolved_depth[agent_id] = depth
        return task_id, depth

    for agent_id in subagents:
        resolve_agent(agent_id)

    model_calls = list(parent.model_calls)
    tool_calls = list(parent.tool_calls)
    dependency_edges = set(parent.dependency_edges)
    all_event_ids = {
        call.event_id for call in parent.model_calls
    } | {call.event_id for call in parent.tool_calls}
    for agent_id, source in subagents.items():
        task_id = resolved_task[agent_id]
        child = source.session
        child_event_timestamps = {
            call.event_id: call.timestamp for call in child.model_calls
        } | {call.event_id: call.timestamp for call in child.tool_calls}
        child_event_ids = set(child_event_timestamps)
        collision = sorted(all_event_ids & child_event_ids)
        if collision:
            raise ValueError(
                "Duplicate event IDs across the session tree: " + collision[0]
            )
        all_event_ids.update(child_event_ids)
        model_calls.extend(
            replace(call, task_id=task_id) for call in child.model_calls
        )
        tool_calls.extend(
            replace(call, task_id=task_id) for call in child.tool_calls
        )
        dependency_edges.update(child.dependency_edges)

        if not child_event_ids:
            continue
        roots, leaves = _event_boundaries(
            child_event_timestamps,
            child.dependency_edges,
        )
        delegation_event = spawn_call[agent_id].event_id
        dependency_edges.update(
            (delegation_event, root_event) for root_event in roots
        )
        owner_session = sessions[spawn_owner[agent_id]]
        owner_successors = sorted(
            target
            for source_id, target in owner_session.dependency_edges
            if source_id == delegation_event
        )
        dependency_edges.update(
            (leaf_event, successor)
            for leaf_event in leaves
            for successor in owner_successors
        )

    normalized_model_calls = tuple(
        sorted(model_calls, key=lambda item: (item.task_id, item.timestamp, item.event_id))
    )
    normalized_tool_calls = tuple(
        sorted(tool_calls, key=lambda item: (item.task_id, item.timestamp, item.event_id))
    )
    normalized_edges = tuple(sorted(dependency_edges))
    versions = tuple(
        sorted(
            {
                version
                for session in sessions.values()
                for version in session.claude_code_versions
            }
        )
    )
    inventory_payload = {
        "session_id_sha256": _sha256_bytes(parent.session_id.encode("utf-8")),
        "source_manifest": sorted(
            source_manifest,
            key=_canonical_json,
        ),
        "tasks": [
            {
                "task_id": task.task_id,
                "input_digest": task.input_digest,
                "started_at": task.started_at,
            }
            for task in parent.tasks
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
        "dependency_edges": [list(edge) for edge in normalized_edges],
        "tree": {
            "source_file_count": 1 + 2 * len(subagents),
            "subagent_count": len(subagents),
            "expanded_delegation_count": len(subagents),
            "max_spawn_depth": max(resolved_depth.values()),
        },
    }
    return ClaudeCodeSession(
        session_id=parent.session_id,
        raw_sha256=_sha256_json(sorted(source_manifest, key=_canonical_json)),
        relevant_record_count=sum(
            session.relevant_record_count for session in sessions.values()
        ),
        claude_code_versions=versions,
        tasks=parent.tasks,
        model_calls=normalized_model_calls,
        tool_calls=normalized_tool_calls,
        dependency_edges=normalized_edges,
        inventory_sha256=_sha256_json(inventory_payload),
        unexpanded_delegation_tools=unexpanded,
        source_id=SOURCE_ID,
        source_version=SOURCE_VERSION,
        task_unit=TASK_UNIT,
        privacy_mode=PRIVACY_MODE,
        source_file_count=1 + 2 * len(subagents),
        subagent_count=len(subagents),
        expanded_delegation_count=len(subagents),
        max_spawn_depth=max(resolved_depth.values()),
    )


def claude_code_tree_bundle_from_session(
    session: ClaudeCodeSession,
    contract: Mapping[str, Any],
) -> EvidenceBundle:
    if session.source_id != SOURCE_ID or session.source_version != SOURCE_VERSION:
        raise ValueError("Expected a Claude Code session-tree inspection")
    return claude_code_bundle_from_session(session, contract)


def claude_code_tree_bundle(
    source_path: str | Path,
    contract: Mapping[str, Any],
) -> EvidenceBundle:
    return claude_code_tree_bundle_from_session(
        inspect_claude_code_session_tree(source_path),
        contract,
    )
