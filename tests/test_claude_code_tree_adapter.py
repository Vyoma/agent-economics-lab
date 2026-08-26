from __future__ import annotations

import copy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agent_economics import (
    Decision,
    claude_code_tree_bundle_from_session,
    conversion_contract_template,
    conversion_receipt,
    evaluate_bundle,
    inspect_claude_code_jsonl,
    inspect_claude_code_session_tree,
    load_conversion_contract,
    render_normalized_json,
)
from agent_economics.claude_code_tree import _event_boundaries
from agent_economics.cli import main
from agent_economics.report import render_markdown

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "claude-code-tree"
SESSION = EXAMPLE / "session.jsonl"
CONTRACT = EXAMPLE / "conversion-contract.json"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


class _QuietStdout(unittest.TestCase):
    """
    Base case that captures stdout for the duration of each test.

    The CLI and judge pipelines print their reports by design. Letting that
    reach the terminal buries the unittest summary under hundreds of lines, so
    the output is captured and left available on ``self.stdout`` for assertions.
    """

    def setUp(self) -> None:
        super().setUp()
        self.stdout = io.StringIO()
        redirect = redirect_stdout(self.stdout)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)


class ClaudeCodeTreeAdapterTests(_QuietStdout):
    def test_tree_expands_delegated_calls_into_the_root_task(self) -> None:
        parent = inspect_claude_code_jsonl(SESSION)
        tree = inspect_claude_code_session_tree(SESSION)
        self.assertEqual(parent.unexpanded_delegation_tools, ("Agent",))
        self.assertEqual(tree.source_id, "source.claude-code-session-tree")
        self.assertEqual(tree.source_file_count, 3)
        self.assertEqual(tree.subagent_count, 1)
        self.assertEqual(tree.expanded_delegation_count, 1)
        self.assertEqual(tree.max_spawn_depth, 1)
        self.assertEqual(tree.relevant_record_count, 9)
        self.assertEqual(len(tree.tasks), 1)
        self.assertEqual(len(tree.model_calls), 4)
        self.assertEqual(len(tree.tool_calls), 2)
        self.assertEqual(len(tree.dependency_edges), 6)
        self.assertEqual(tree.unexpanded_delegation_tools, ())
        task_ids = {
            call.task_id for call in tree.model_calls
        } | {call.task_id for call in tree.tool_calls}
        self.assertEqual(task_ids, {tree.tasks[0].task_id})

    def test_checked_in_tree_artifacts_are_byte_reproducible(self) -> None:
        session = inspect_claude_code_session_tree(SESSION)
        contract = load_conversion_contract(CONTRACT)
        bundle = claude_code_tree_bundle_from_session(session, contract)
        rendered_bundle = render_normalized_json(
            bundle,
            conversion=conversion_receipt(session, contract, bundle),
        )
        self.assertEqual(
            rendered_bundle,
            (EXAMPLE / "bundle.json").read_text(encoding="utf-8"),
        )
        case = evaluate_bundle(bundle)
        self.assertEqual(case.decision, Decision.SCALE)
        self.assertEqual(
            render_markdown(case),
            (EXAMPLE / "assurance-case.md").read_text(encoding="utf-8"),
        )

    def test_tree_content_firewall_covers_parent_child_and_metadata(self) -> None:
        session = inspect_claude_code_session_tree(SESSION)
        contract = load_conversion_contract(CONTRACT)
        bundle = claude_code_tree_bundle_from_session(session, contract)
        rendered = json.dumps(
            conversion_contract_template(session),
            sort_keys=True,
        ) + render_normalized_json(
            bundle,
            conversion=conversion_receipt(session, contract, bundle),
        )
        for secret in (
            "SECRET_ROOT_PROMPT",
            "SECRET_DELEGATED_TASK",
            "SECRET_SUBAGENT_PROMPT",
            "SECRET_SUBAGENT_RESULT",
            "SECRET_SUBAGENT_THINKING",
            "SECRET_CHILD_TOOL_RESULT",
            "SECRET_CHILD_RESPONSE",
            "SECRET_META_DESCRIPTION",
            "/secret/customer.txt",
            "session-tree-example-001",
            "child-001",
            "tool-root-agent",
        ):
            self.assertNotIn(secret, rendered)

    def test_mixed_root_prompt_is_hashed_without_decoding_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "tree"
            shutil.copytree(EXAMPLE, copied)
            parent = copied / "session.jsonl"
            rows = _read_jsonl(parent)
            rows[0]["message"]["content"] = [
                {
                    "text": "SECRET_MIXED_TEXT",
                    "type": "text",
                },
                {
                    "source": {
                        "data": "SECRET_IMAGE_BYTES",
                        "media_type": "image/png",
                        "type": "base64",
                    },
                    "type": "image",
                },
            ]
            _write_jsonl(parent, rows)
            session = inspect_claude_code_session_tree(parent)
            rendered = json.dumps(
                conversion_contract_template(session),
                sort_keys=True,
            )
        self.assertEqual(len(session.tasks), 1)
        self.assertNotIn("SECRET_MIXED_TEXT", rendered)
        self.assertNotIn("SECRET_IMAGE_BYTES", rendered)

    def test_changed_child_transcript_invalidates_the_contract(self) -> None:
        contract = load_conversion_contract(CONTRACT)
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "tree"
            shutil.copytree(EXAMPLE, copied)
            child = copied / "session" / "subagents" / "agent-child-001.jsonl"
            rows = _read_jsonl(child)
            rows[-1]["message"]["usage"]["output_tokens"] = 46
            _write_jsonl(child, rows)
            session = inspect_claude_code_session_tree(copied / "session.jsonl")
            with self.assertRaisesRegex(
                ValueError,
                "does not match the frozen JSONL",
            ):
                claude_code_tree_bundle_from_session(session, contract)

    def test_unpaired_or_unknown_subagent_metadata_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "tree"
            shutil.copytree(EXAMPLE, copied)
            metadata = (
                copied
                / "session"
                / "subagents"
                / "agent-child-001.meta.json"
            )
            metadata.unlink()
            with self.assertRaisesRegex(ValueError, "Unpaired subagent files"):
                inspect_claude_code_session_tree(copied / "session.jsonl")

        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "tree"
            shutil.copytree(EXAMPLE, copied)
            metadata = (
                copied
                / "session"
                / "subagents"
                / "agent-child-001.meta.json"
            )
            value = json.loads(metadata.read_text(encoding="utf-8"))
            value["toolUseId"] = "unknown-delegation"
            metadata.write_text(
                json.dumps(value, sort_keys=True),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "bootstrap must bind its delegation tool",
            ):
                inspect_claude_code_session_tree(copied / "session.jsonl")

    def test_legacy_direct_prompt_subagent_shape_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "tree"
            shutil.copytree(EXAMPLE, copied)
            child = copied / "session" / "subagents" / "agent-child-001.jsonl"
            rows = _read_jsonl(child)
            direct_prompt = rows[2]
            direct_prompt["message"] = {
                "content": "SECRET_LEGACY_SUBAGENT_PROMPT",
                "role": "user",
            }
            direct_prompt["parentUuid"] = None
            _write_jsonl(child, [direct_prompt, *rows[3:]])
            metadata = child.with_name("agent-child-001.meta.json")
            value = json.loads(metadata.read_text(encoding="utf-8"))
            value.pop("isFork")
            value.pop("spawnDepth")
            metadata.write_text(
                json.dumps(value, sort_keys=True),
                encoding="utf-8",
            )
            session = inspect_claude_code_session_tree(copied / "session.jsonl")
        self.assertEqual(len(session.model_calls), 4)
        self.assertEqual(len(session.tool_calls), 2)
        self.assertEqual(session.max_spawn_depth, 1)

    def test_nested_subagent_inherits_the_root_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "tree"
            shutil.copytree(EXAMPLE, copied)
            subagents = copied / "session" / "subagents"
            child_path = subagents / "agent-child-001.jsonl"
            child_rows = _read_jsonl(child_path)
            original_final = copy.deepcopy(child_rows[-1])
            child_rows[-1]["message"]["content"] = [
                {
                    "caller": {"type": "direct"},
                    "id": "tool-child-agent",
                    "input": {
                        "description": "SECRET_NESTED_TASK",
                        "prompt": "SECRET_NESTED_PROMPT",
                        "subagent_type": "researcher",
                    },
                    "name": "Agent",
                    "type": "tool_use",
                }
            ]
            child_rows[-1]["message"]["stop_reason"] = "tool_use"
            child_rows.append(
                {
                    "agentId": "child-001",
                    "isSidechain": True,
                    "message": {
                        "content": [
                            {
                                "content": "SECRET_NESTED_RESULT",
                                "tool_use_id": "tool-child-agent",
                                "type": "tool_result",
                            }
                        ],
                        "role": "user",
                    },
                    "parentUuid": child_rows[-1]["uuid"],
                    "sessionId": "session-tree-example-001",
                    "sourceToolAssistantUUID": child_rows[-1]["uuid"],
                    "timestamp": "2026-07-29T16:00:05.500Z",
                    "type": "user",
                    "uuid": "tool-result-child-agent",
                    "version": "2.1.212",
                }
            )
            original_final["message"]["id"] = "message-child-after-agent"
            original_final["parentUuid"] = "tool-result-child-agent"
            original_final["requestId"] = "request-child-after-agent"
            original_final["timestamp"] = "2026-07-29T16:00:07.000Z"
            original_final["uuid"] = "assistant-child-after-agent"
            child_rows.append(original_final)
            _write_jsonl(child_path, child_rows)

            grandchild_rows = [
                {
                    "agentId": "grandchild-001",
                    "parentLastUuid": child_rows[-3]["uuid"],
                    "parentSessionId": "session-tree-example-001",
                    "type": "fork-context-ref",
                },
                {
                    **copy.deepcopy(child_rows[-3]),
                    "agentId": "grandchild-001",
                    "parentUuid": None,
                    "uuid": "assistant-grandchild-bootstrap",
                },
                {
                    "agentId": "grandchild-001",
                    "isSidechain": True,
                    "message": {
                        "content": [
                            {
                                "content": "SECRET_NESTED_RESULT",
                                "tool_use_id": "tool-child-agent",
                                "type": "tool_result",
                            },
                            {
                                "text": "SECRET_NESTED_PROMPT",
                                "type": "text",
                            },
                        ],
                        "role": "user",
                    },
                    "parentUuid": "assistant-grandchild-bootstrap",
                    "sessionId": "session-tree-example-001",
                    "timestamp": "2026-07-29T16:00:05.750Z",
                    "type": "user",
                    "uuid": "user-grandchild-bootstrap",
                    "version": "2.1.212",
                },
                {
                    **copy.deepcopy(original_final),
                    "agentId": "grandchild-001",
                    "message": {
                        **copy.deepcopy(original_final["message"]),
                        "id": "message-grandchild-final",
                    },
                    "parentUuid": "user-grandchild-bootstrap",
                    "requestId": "request-grandchild-final",
                    "timestamp": "2026-07-29T16:00:06.000Z",
                    "uuid": "assistant-grandchild-final",
                },
            ]
            _write_jsonl(
                subagents / "agent-grandchild-001.jsonl",
                grandchild_rows,
            )
            (
                subagents / "agent-grandchild-001.meta.json"
            ).write_text(
                json.dumps(
                    {
                        "agentType": "researcher",
                        "description": "SECRET_GRANDCHILD_DESCRIPTION",
                        "isFork": True,
                        "spawnDepth": 2,
                        "toolUseId": "tool-child-agent",
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            session = inspect_claude_code_session_tree(copied / "session.jsonl")
        self.assertEqual(session.subagent_count, 2)
        self.assertEqual(session.max_spawn_depth, 2)
        self.assertEqual(session.unexpanded_delegation_tools, ())
        task_ids = {
            call.task_id for call in session.model_calls
        } | {call.task_id for call in session.tool_calls}
        self.assertEqual(task_ids, {session.tasks[0].task_id})

    def test_cyclic_child_graph_has_deterministic_tree_boundaries(self) -> None:
        roots, leaves = _event_boundaries(
            {
                "a": "2026-07-29T16:00:01.000Z",
                "b": "2026-07-29T16:00:02.000Z",
                "c": "2026-07-29T16:00:03.000Z",
            },
            (
                ("a", "b"),
                ("b", "a"),
                ("b", "c"),
            ),
        )
        self.assertEqual(roots, ("a",))
        self.assertEqual(leaves, ("c",))

    def test_zero_compute_child_is_bound_without_inventing_an_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "tree"
            shutil.copytree(EXAMPLE, copied)
            child = copied / "session" / "subagents" / "agent-child-001.jsonl"
            rows = _read_jsonl(child)
            api_error = {
                "agentId": "child-001",
                "isApiErrorMessage": True,
                "isSidechain": True,
                "message": {
                    "content": [
                        {
                            "text": "SECRET_CHILD_API_ERROR",
                            "type": "text",
                        }
                    ],
                    "id": "synthetic-child-error",
                    "model": "<synthetic>",
                    "role": "assistant",
                    "stop_reason": "stop_sequence",
                    "type": "message",
                    "usage": {
                        "cache_creation": {},
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "server_tool_use": {},
                    },
                },
                "parentUuid": rows[2]["uuid"],
                "sessionId": "session-tree-example-001",
                "timestamp": "2026-07-29T16:00:03.000Z",
                "type": "assistant",
                "uuid": "assistant-child-api-error",
                "version": "2.1.212",
            }
            _write_jsonl(child, [*rows[:3], api_error])
            session = inspect_claude_code_session_tree(copied / "session.jsonl")
        self.assertEqual(session.subagent_count, 1)
        self.assertEqual(session.unexpanded_delegation_tools, ())
        self.assertEqual(len(session.model_calls), 2)
        self.assertEqual(len(session.tool_calls), 1)

    def test_cli_template_convert_and_evaluate_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template_path = root / "template.json"
            bundle_path = root / "bundle.json"
            self.assertEqual(
                main(
                    [
                        "convert",
                        "--from",
                        "claude-code-tree",
                        "--in",
                        str(SESSION),
                        "--template",
                        str(template_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "convert",
                        "--from",
                        "claude-code-tree",
                        "--in",
                        str(SESSION),
                        "--contract",
                        str(CONTRACT),
                        "--out",
                        str(bundle_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                bundle_path.read_text(encoding="utf-8"),
                (EXAMPLE / "bundle.json").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                main(["evaluate", "--bundle", str(bundle_path), "--ci"]),
                0,
            )

    def test_cli_cannot_overwrite_a_child_source_file(self) -> None:
        child = (
            EXAMPLE
            / "session"
            / "subagents"
            / "agent-child-001.jsonl"
        )
        original = child.read_bytes()
        exit_code = main(
            [
                "convert",
                "--from",
                "claude-code-tree",
                "--in",
                str(SESSION),
                "--contract",
                str(CONTRACT),
                "--out",
                str(child),
            ]
        )
        self.assertEqual(exit_code, 2)
        self.assertEqual(child.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
