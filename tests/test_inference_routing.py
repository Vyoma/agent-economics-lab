"""All inference in this package routes to Kimi, and nothing else infers.

This is the enforcement for a claim that is otherwise unverifiable prose. Two
properties are asserted:

  1. Every model call goes through `kimi_client`. No other module opens a
     connection for inference, and no second provider endpoint exists.
  2. The deterministic decision kernel performs no inference at all. Cost
     reconstruction, gates, confidence bounds, and digests are arithmetic. If a
     model call ever appears in that path, byte-reproducible verdicts and the
     fixed-contract guarantee both stop being true, so this test fails loudly
     rather than letting it happen quietly.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from agent_economics import kimi_client

PACKAGE = Path(__file__).resolve().parents[1] / "agent_economics"

# The only modules permitted to invoke the inference egress.
INFERENCE_MODULES = frozenset(
    {"kimi_client.py", "kimi_judge.py", "kimi_analyst.py"}
)

# Modules permitted to import the client to read its declared identity, for
# example to print the provider in `capabilities`. They must not call it.
METADATA_READERS = frozenset({"cli.py"})

# The functions that actually perform a model call.
CALL_FUNCTIONS = frozenset({"call_kimi", "call_kimi_json"})

# Shaped like a real key: "sk-" plus 48 characters. The client rejects short or
# templated values locally, so a fixture must look plausible to exercise the
# accept path.
_REALISTIC_KEY = "sk-K3nQ7wZ2pR8sT1vY4bM6jL9cX0dF5gH2aN7eU3iO8kP1rW6z"

# Hosts belonging to other model providers. Any appearance means inference was
# routed somewhere other than Kimi.
FOREIGN_PROVIDER_HOSTS = (
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.cohere.ai",
    "api.mistral.ai",
    "api.together.xyz",
    "api.groq.com",
    "openrouter.ai",
    "api.deepseek.com",
    "bedrock-runtime",
    "openai.azure.com",
    "localhost:11434",
)

# Import names that would let a module reach a provider SDK directly.
FOREIGN_PROVIDER_MODULES = frozenset(
    {
        "openai",
        "anthropic",
        "google.generativeai",
        "cohere",
        "mistralai",
        "litellm",
        "langchain",
        "langchain_openai",
        "ollama",
        "transformers",
        "torch",
    }
)


def _python_files() -> list[Path]:
    return sorted(path for path in PACKAGE.glob("*.py"))


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class InferenceRoutingTests(unittest.TestCase):
    def test_the_package_has_files_to_check(self) -> None:
        """Guard against a glob that silently matches nothing."""
        self.assertGreater(len(_python_files()), 10)

    def test_only_the_client_opens_a_connection(self) -> None:
        """One egress point. Everything else must delegate to it."""
        offenders = []
        for path in _python_files():
            if path.name == "kimi_client.py":
                continue
            source = path.read_text(encoding="utf-8")
            if "urlopen" in source or "http.client" in source:
                offenders.append(path.name)
        self.assertEqual(
            offenders,
            [],
            "these modules bypass kimi_client to open their own connection",
        )

    def test_only_the_client_declares_the_endpoint(self) -> None:
        offenders = []
        for path in _python_files():
            if path.name == "kimi_client.py":
                continue
            if "api.moonshot.ai" in path.read_text(encoding="utf-8"):
                offenders.append(path.name)
        self.assertEqual(
            offenders,
            [],
            "the API endpoint must be declared once, in kimi_client",
        )

    def test_no_foreign_provider_endpoint_appears(self) -> None:
        for path in _python_files():
            source = path.read_text(encoding="utf-8")
            for host in FOREIGN_PROVIDER_HOSTS:
                with self.subTest(module=path.name, host=host):
                    self.assertNotIn(
                        host,
                        source,
                        f"{path.name} references a non-Kimi provider",
                    )

    def test_the_auth_diagnostic_only_probes_moonshot_hosts(self) -> None:
        """The doctor makes raw calls by design; it must still stay on Kimi."""
        doctor = PACKAGE.parent / "check_kimi_auth.py"
        self.assertTrue(doctor.exists())
        source = doctor.read_text(encoding="utf-8")
        for host in FOREIGN_PROVIDER_HOSTS:
            with self.subTest(host=host):
                self.assertNotIn(host, source)
        self.assertIn("KIMI_HOSTS", source)

    def test_no_foreign_provider_sdk_is_imported(self) -> None:
        for path in _python_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported = _imported_names(tree)
            for name in imported:
                root = name.split(".")[0]
                with self.subTest(module=path.name, imported=name):
                    self.assertNotIn(name, FOREIGN_PROVIDER_MODULES)
                    self.assertNotIn(root, FOREIGN_PROVIDER_MODULES)

    def test_only_declared_modules_touch_the_client(self) -> None:
        """A new inference site must be a deliberate, reviewed addition."""
        importers = set()
        for path in _python_files():
            if path.name == "kimi_client.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in {
                    None,
                    "kimi_client",
                }:
                    if any(
                        alias.name == "kimi_client" for alias in node.names
                    ):
                        importers.add(path.name)
                elif isinstance(node, ast.Import) and any(
                    alias.name.endswith("kimi_client") for alias in node.names
                ):
                    importers.add(path.name)
        permitted = INFERENCE_MODULES | METADATA_READERS
        self.assertTrue(
            importers <= permitted,
            f"unexpected inference sites: {sorted(importers - permitted)}",
        )

    def test_metadata_readers_never_invoke_the_client(self) -> None:
        """Reading the provider name is not the same as calling the model."""
        for name in METADATA_READERS:
            path = PACKAGE / name
            with self.subTest(module=name):
                self.assertTrue(path.exists(), f"{name} is missing")
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                called = {
                    node.func.attr
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                }
                self.assertEqual(
                    called & CALL_FUNCTIONS,
                    set(),
                    f"{name} may read client constants but must not call it",
                )

    def test_decision_kernel_is_inference_free(self) -> None:
        """The verdict path must stay deterministic and reproducible."""
        kernel = (
            "assurance.py",
            "checks.py",
            "evidence.py",
            "models.py",
            "controls.py",
            "frontier.py",
            "report.py",
            "frontier_report.py",
            "io.py",
            "adapters.py",
            "conversion_contract.py",
            "claude_code.py",
            "claude_code_tree.py",
            "otel_genai.py",
            "github_action.py",
        )
        for name in kernel:
            path = PACKAGE / name
            with self.subTest(module=name):
                self.assertTrue(path.exists(), f"{name} is missing")
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("kimi", source.lower())
                self.assertNotIn("urlopen", source)


class KimiClientContractTests(unittest.TestCase):
    def test_provider_and_model_are_kimi(self) -> None:
        self.assertEqual(kimi_client.PROVIDER, "moonshot-ai")
        self.assertTrue(kimi_client.API_URL.startswith("https://api.moonshot.ai/"))
        self.assertTrue(kimi_client.DEFAULT_MODEL.startswith("kimi-"))

    def test_default_reasoning_effort_is_the_deepest_documented_level(self) -> None:
        self.assertEqual(kimi_client.DEFAULT_REASONING_EFFORT, "max")
        self.assertIn("max", kimi_client.REASONING_EFFORTS)

    def test_unknown_reasoning_effort_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            kimi_client.validate_reasoning_effort("medium")
        for effort in kimi_client.REASONING_EFFORTS:
            with self.subTest(effort=effort):
                self.assertEqual(
                    kimi_client.validate_reasoning_effort(effort), effort
                )

    def test_missing_key_names_the_variable_and_the_console(self) -> None:
        import os
        from unittest.mock import patch

        env = {k: v for k, v in os.environ.items() if k != "MOONSHOT_API_KEY"}
        with (
            patch.dict("os.environ", env, clear=True),
            self.assertRaises(RuntimeError) as caught,
        ):
            kimi_client.require_api_key()
        message = str(caught.exception)
        self.assertIn(kimi_client.API_KEY_ENV_VAR, message)
        self.assertIn(kimi_client.CONSOLE_URL, message)

    def test_region_override_reaches_the_china_host(self) -> None:
        """A China-console key needs the .cn host or it 401s forever."""
        from unittest.mock import patch

        for override, expected in (
            ("https://api.moonshot.cn", "https://api.moonshot.cn/v1/chat/completions"),
            ("https://api.moonshot.cn/", "https://api.moonshot.cn/v1/chat/completions"),
            ("https://api.moonshot.cn/v1", "https://api.moonshot.cn/v1/chat/completions"),
            (
                "https://api.moonshot.cn/v1/chat/completions",
                "https://api.moonshot.cn/v1/chat/completions",
            ),
        ):
            with self.subTest(override=override), patch.dict(
                "os.environ", {kimi_client.BASE_URL_ENV_VAR: override}
            ):
                self.assertEqual(kimi_client.resolve_api_url(), expected)

    def test_no_override_uses_the_international_host(self) -> None:
        import os
        from unittest.mock import patch

        env = {
            k: v
            for k, v in os.environ.items()
            if k != kimi_client.BASE_URL_ENV_VAR
        }
        with patch.dict("os.environ", env, clear=True):
            self.assertEqual(kimi_client.resolve_api_url(), kimi_client.API_URL)

    def test_override_cannot_redirect_to_another_provider(self) -> None:
        """The override selects a Moonshot region, not a different vendor.

        Without this the single-provider invariant would hold in the source and
        be defeated by an environment variable.
        """
        from unittest.mock import patch

        for hostile in (
            "https://api.openai.com/v1",
            "https://api.anthropic.com/v1",
            "https://openrouter.ai/api/v1",
            "https://api.moonshot.ai.evil.example/v1",
            "http://api.moonshot.ai/v1",
            "https://localhost:11434/v1",
        ):
            with self.subTest(override=hostile), patch.dict(
                "os.environ", {kimi_client.BASE_URL_ENV_VAR: hostile}
            ), self.assertRaises(ValueError):
                kimi_client.resolve_api_url()

    def test_every_allowed_host_is_a_kimi_host(self) -> None:
        """The allowlist is the invariant. It must stay Kimi-only and complete."""
        for host in kimi_client.KIMI_HOSTS:
            with self.subTest(host=host):
                self.assertTrue(
                    host.endswith(("moonshot.ai", "moonshot.cn", "kimi.com")),
                    f"{host} is not a Kimi host",
                )
                self.assertIn(host, kimi_client.REGION_CONSOLES)
                self.assertIn(host, kimi_client.KIMI_SYSTEMS)
                self.assertIn(host, kimi_client.KIMI_ENDPOINTS)

    def test_each_system_resolves_to_its_own_documented_route(self) -> None:
        """Kimi Code uses /coding/v1, not the Open Platform's /v1."""
        from unittest.mock import patch

        expected = {
            "api.moonshot.ai": "https://api.moonshot.ai/v1/chat/completions",
            "api.moonshot.cn": "https://api.moonshot.cn/v1/chat/completions",
            "api.kimi.com": "https://api.kimi.com/coding/v1/chat/completions",
        }
        self.assertEqual(set(expected), set(kimi_client.KIMI_HOSTS))
        for host, url in expected.items():
            with self.subTest(host=host), patch.dict(
                "os.environ",
                {kimi_client.BASE_URL_ENV_VAR: f"https://{host}"},
            ):
                self.assertEqual(kimi_client.resolve_api_url(), url)

    def test_api_key_whitespace_and_quotes_are_stripped(self) -> None:
        """A trailing newline 401s exactly like a wrong key. Do not make the
        user debug that distinction."""
        from unittest.mock import patch

        key = _REALISTIC_KEY
        for raw in (f"{key}\n", f"  {key}  ", f"'{key}'", f'"{key}"'):
            with self.subTest(raw=repr(raw)), patch.dict(
                "os.environ", {kimi_client.API_KEY_ENV_VAR: raw}
            ):
                self.assertEqual(kimi_client.require_api_key(), key)

    def test_blank_api_key_is_rejected(self) -> None:
        from unittest.mock import patch

        for raw in ("   ", "\n", "''"):
            with self.subTest(raw=repr(raw)), patch.dict(
                "os.environ", {kimi_client.API_KEY_ENV_VAR: raw}
            ), self.assertRaises(RuntimeError):
                kimi_client.require_api_key()

    def test_placeholder_key_is_rejected_before_any_request(self) -> None:
        """The literal placeholder from the docs must fail locally, not remotely.

        A short or templated value cannot authenticate anywhere, so spending
        network calls on it only produces a misleading "credential rejected".
        """
        for placeholder in (
            "sk-...",
            "...",
            "sk-your-key-here",
            "sk-YOUR_API_KEY",
            "<your-key>",
            "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
            "sk-REPLACE_THIS_WITH_YOUR_KEY",
            "sk-abc123",
            "sk-short",
        ):
            with self.subTest(placeholder=placeholder):
                self.assertIsNotNone(
                    kimi_client.api_key_shape_problem(placeholder),
                    f"{placeholder!r} should be detected as unusable",
                )

    def test_a_realistic_key_shape_is_accepted(self) -> None:
        """The guard must not reject a real key."""
        realistic = _REALISTIC_KEY
        self.assertGreater(len(realistic), kimi_client.MIN_API_KEY_LENGTH)
        self.assertIsNone(kimi_client.api_key_shape_problem(realistic))

        from unittest.mock import patch

        with patch.dict("os.environ", {kimi_client.API_KEY_ENV_VAR: realistic}):
            self.assertEqual(kimi_client.require_api_key(), realistic)

    def test_placeholder_rejection_names_the_consoles(self) -> None:
        from unittest.mock import patch

        with (
            patch.dict("os.environ", {kimi_client.API_KEY_ENV_VAR: "sk-..."}),
            self.assertRaises(RuntimeError) as caught,
        ):
            kimi_client.require_api_key()
        message = str(caught.exception)
        for host in kimi_client.KIMI_HOSTS:
            with self.subTest(host=host):
                self.assertIn(kimi_client.REGION_CONSOLES[host], message)

    def test_docs_do_not_ship_a_pasteable_fake_key(self) -> None:
        """This exact copy-paste is what produced a 6-character key."""
        root = PACKAGE.parent
        for name in ("README.md", "docs/kimi-integration.md"):
            path = root / name
            with self.subTest(doc=name):
                self.assertTrue(path.exists())
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(
                    f"export {kimi_client.API_KEY_ENV_VAR}=...",
                    text,
                    "a bare '...' invites exporting the placeholder verbatim",
                )
                self.assertNotIn(
                    f"export {kimi_client.API_KEY_ENV_VAR}=sk-...", text
                )

    def test_401_lists_every_credential_system(self) -> None:
        """The most common cause of a 401 here is a valid key, wrong system."""
        message = kimi_client._remediation(401, kimi_client.API_URL)
        for host in kimi_client.KIMI_HOSTS:
            with self.subTest(host=host):
                self.assertIn(host, message)
                self.assertIn(kimi_client.REGION_CONSOLES[host], message)
        self.assertIn(kimi_client.BASE_URL_ENV_VAR, message)
        self.assertIn("kimi-doctor", message)
        self.assertEqual(kimi_client._remediation(400, kimi_client.API_URL), "")

    def test_both_inference_sites_share_one_contract(self) -> None:
        """Duplicated constants were how the two modules drifted apart."""
        from agent_economics import kimi_analyst, kimi_judge

        for module in (kimi_judge, kimi_analyst):
            with self.subTest(module=module.__name__):
                self.assertEqual(module._DEFAULT_MODEL, kimi_client.DEFAULT_MODEL)
                self.assertEqual(
                    module._DEFAULT_REASONING_EFFORT,
                    kimi_client.DEFAULT_REASONING_EFFORT,
                )
                self.assertEqual(
                    module._REASONING_EFFORTS, kimi_client.REASONING_EFFORTS
                )


if __name__ == "__main__":
    unittest.main()
