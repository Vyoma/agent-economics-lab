"""The single inference egress for this package.

Every model call in `agent_economics` goes through `call_kimi` in this module.
Nothing else in the package opens a network connection for inference, and
`tests/test_inference_routing.py` asserts that rather than trusting it.

Why centralize it. The decision kernel is deliberately deterministic: cost
reconstruction, gate thresholds, confidence bounds, and digests are arithmetic,
and their byte-reproducibility is the property the whole repository sells. That
leaves exactly two places where a judgment call cannot be computed and a model is
appropriate:

    kimi-judge@1     was this outcome acceptable against a frozen rubric?
    kimi-analyst@1   given a decided case, what should be fixed first?

Concentrating both in one client means the provider, model, request contract, and
retry policy are reviewed once and cannot drift apart between modules. It also
makes "all inference routes to Kimi" checkable in a test instead of being a claim
in a README.

Provider contract, per https://platform.kimi.ai/docs/api/chat:

- `kimi-k3` is the current flagship: 2.8T parameters, 1M context, always
  reasoning.
- `reasoning_effort` is a top-level field with `low`, `high`, and `max`. `max` is
  the documented default and the level guaranteed available, so it is the default
  here; the others are opt-in.
- Sampling is fixed server-side. Never send `temperature`, `top_p`, or penalty
  fields; they are not part of the K3 request schema.
- Output length is `max_completion_tokens`. `max_tokens` is not part of the K3
  schema.
- Only `content` is read. Reasoning is returned separately as
  `reasoning_content`, and a JSON schema constrains the final content field
  rather than the reasoning trace.
- Context caching is automatic and needs no parameters, but it only helps when
  the prefix is stable. Callers must keep per-request content out of the system
  prompt.

Zero external dependencies: stdlib `urllib` only.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

PROVIDER = "moonshot-ai"
API_URL = "https://api.moonshot.ai/v1/chat/completions"
API_KEY_ENV_VAR = "MOONSHOT_API_KEY"
BASE_URL_ENV_VAR = "MOONSHOT_BASE_URL"
CONSOLE_URL = "https://platform.kimi.ai"

# Moonshot operates three credential systems whose keys and base URLs are NOT
# interchangeable. Using a key from one against another returns
# `401 Invalid Authentication` with a perfectly valid key, and that is by far the
# most common cause of an auth failure here. Each host therefore carries its own
# path, because Kimi Code does not share the Open Platform's route.
CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
KIMI_ENDPOINTS = {
    "api.moonshot.ai": "/v1/chat/completions",
    "api.moonshot.cn": "/v1/chat/completions",
    "api.kimi.com": "/coding/v1/chat/completions",
}
KIMI_HOSTS = frozenset(KIMI_ENDPOINTS)
KIMI_SYSTEMS = {
    "api.moonshot.ai": "Open Platform, international",
    "api.moonshot.cn": "Open Platform, China",
    "api.kimi.com": "Kimi Code coding subscription",
}
REGION_CONSOLES = {
    "api.moonshot.ai": "https://platform.kimi.ai",
    "api.moonshot.cn": "https://platform.moonshot.cn",
    "api.kimi.com": "https://www.kimi.com/code",
}

DEFAULT_MODEL = "kimi-k3"
DEFAULT_REASONING_EFFORT = "max"
REASONING_EFFORTS = ("low", "high", "max")

# Transient-failure retry. An exhausted call in the judge falls back to an
# unacceptable label, so a swallowed rate limit would quietly depress
# `acceptable_rate` and move every gate downstream of it. Retry first.
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 1.5
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

# Timeout has to cover the reasoning trace, not just the answer. K3 always
# reasons, and at `max` effort it can think for minutes before emitting any
# content. A timeout sized for a chat reply turns every call into four timed-out
# attempts plus backoff, which reads as a hang rather than as a misconfiguration.
TIMEOUT_BY_REASONING_EFFORT = {"low": 60, "high": 180, "max": 420}


def timeout_for(reasoning_effort: str) -> int:
    return TIMEOUT_BY_REASONING_EFFORT.get(
        reasoning_effort, TIMEOUT_BY_REASONING_EFFORT["max"]
    )

# A real key is `sk-` plus roughly 48 more characters. Anything much shorter is a
# placeholder or a truncated paste, and sending it wastes three round trips to
# learn what the length already proved. Set the floor well under the real length
# so a format change does not reject a valid key.
MIN_API_KEY_LENGTH = 20

# Substrings that only appear in documentation placeholders, never in a key.
PLACEHOLDER_MARKERS = (
    "...",
    "your",
    "YOUR",
    "xxx",
    "XXX",
    "<",
    ">",
    "example",
    "EXAMPLE",
    "replace",
    "REPLACE",
    "abc123",
)

# Moonshot Flavored JSON Schema (MFJS) accepts only `type`, `enum`, and
# `required` as validation keywords. Numeric range and string-format keywords are
# rejected with `400 invalid_request_error`, so a schema carrying them never
# reaches the model at all. Bounds must be enforced by the caller after parsing.
# Spec: https://github.com/MoonshotAI/walle/blob/main/docs/mfjs-spec.md
MFJS_REJECTED_KEYWORDS = frozenset(
    {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minContains",
        "maxContains",
        "minProperties",
        "maxProperties",
        "prefixItems",
        "unevaluatedItems",
        "title",
        "$comment",
        "$schema",
    }
)


class KimiRequestError(RuntimeError):
    """The request itself was rejected: bad contract, bad key, bad model.

    Separated from transient failures on purpose. A caller that degrades on a
    flaky network must not degrade on a malformed request, because a rejected
    schema would otherwise be indistinguishable from a genuine model verdict and
    would silently relabel an entire batch.
    """

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"Kimi rejected the request with HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


def assert_mfjs_compatible(schema: Any, *, path: str = "$") -> None:
    """Raise ValueError if a schema carries a keyword MFJS rejects.

    Called before a request goes out so a schema bug surfaces as a local error
    with a path, rather than as a remote 400 that a fallback turns into data.
    """
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in MFJS_REJECTED_KEYWORDS:
                raise ValueError(
                    f"{path}.{key} is not accepted by Moonshot Flavored JSON "
                    "Schema and would be rejected with HTTP 400. Enforce this "
                    "constraint in code after parsing instead."
                )
            if key == "properties" and isinstance(value, dict):
                for name, subschema in value.items():
                    assert_mfjs_compatible(subschema, path=f"{path}.{name}")
            else:
                assert_mfjs_compatible(value, path=f"{path}.{key}")
    elif isinstance(schema, list):
        for index, item in enumerate(schema):
            assert_mfjs_compatible(item, path=f"{path}[{index}]")


def require_api_key() -> str:
    """Return the configured key, or explain how to set one.

    Surrounding whitespace and shell quote characters are stripped. A key pasted
    with a trailing newline produces a 401 that looks identical to a wrong key,
    and that is not a distinction worth making the user debug.
    """
    raw = os.environ.get(API_KEY_ENV_VAR)
    if not raw:
        raise RuntimeError(
            f"{API_KEY_ENV_VAR} not set. "
            f"Get a key at {CONSOLE_URL} and export it."
        )
    api_key = raw.strip().strip("'\"").strip()
    if not api_key:
        raise RuntimeError(
            f"{API_KEY_ENV_VAR} is set but contains only whitespace or quotes."
        )
    problem = api_key_shape_problem(api_key)
    if problem:
        raise RuntimeError(
            f"{API_KEY_ENV_VAR} does not look like a real key: {problem}\n"
            f"A key is 'sk-' followed by roughly 48 more characters. Copy yours "
            f"from one of:\n"
            + "\n".join(
                f"  {REGION_CONSOLES[host]:<34} {KIMI_SYSTEMS[host]}"
                for host in sorted(KIMI_HOSTS)
            )
        )
    return api_key


def api_key_shape_problem(api_key: str) -> str | None:
    """Return why a key cannot be real, or None if its shape is plausible.

    Checked locally so a placeholder fails in milliseconds with an accurate
    reason, instead of costing three network round trips and arriving as
    "the credential is rejected", which invites debugging the wrong thing.
    """
    for marker in PLACEHOLDER_MARKERS:
        if marker in api_key:
            return (
                f"it contains {marker!r}, which appears in documentation "
                "placeholders but never in a key. Paste the actual key."
            )
    if len(api_key) < MIN_API_KEY_LENGTH:
        return (
            f"it is {len(api_key)} characters, and a key is at least "
            f"{MIN_API_KEY_LENGTH}. This is a truncated paste or a placeholder."
        )
    return None


def resolve_api_url() -> str:
    """Return the chat-completions URL, honouring a region override.

    `MOONSHOT_BASE_URL` exists so a China-console or Kimi Code key can reach its
    own system without editing source. The host is checked against `KIMI_HOSTS`:
    the override selects a Kimi system, and cannot be used to point inference at
    a different provider. That keeps the single-provider invariant true under
    configuration, not just in the source.

    An origin-only override resolves to that host's documented route, since Kimi
    Code uses `/coding/v1` rather than the Open Platform's `/v1`.
    """
    override = os.environ.get(BASE_URL_ENV_VAR)
    if not override:
        return API_URL
    base = override.strip().rstrip("/")
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "https":
        raise ValueError(
            f"{BASE_URL_ENV_VAR} must use https, got {override!r}"
        )
    host = parsed.hostname
    if host not in KIMI_HOSTS:
        raise ValueError(
            f"{BASE_URL_ENV_VAR} host must be one of {sorted(KIMI_HOSTS)}, got "
            f"{host!r}. This override selects a Kimi system; it cannot redirect "
            "inference to another provider."
        )
    if base.endswith("/chat/completions"):
        return base
    default_path = KIMI_ENDPOINTS[host]
    if parsed.path.rstrip("/") in ("", "/v1", "/coding", "/coding/v1"):
        return f"https://{parsed.netloc}{default_path}"
    raise ValueError(
        f"{BASE_URL_ENV_VAR} should be an origin or end in /chat/completions, "
        f"got {override!r}"
    )


def validate_reasoning_effort(reasoning_effort: str) -> str:
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(
            f"reasoning_effort must be one of {list(REASONING_EFFORTS)}, "
            f"got {reasoning_effort!r}"
        )
    return reasoning_effort


def _error_detail(error: urllib.error.HTTPError) -> str:
    """Return the provider's error message, which names the offending field."""
    try:
        body = json.loads(error.read())
    except (OSError, ValueError):
        return error.reason if isinstance(error.reason, str) else str(error.reason)
    if isinstance(body, dict):
        detail = body.get("error")
        if isinstance(detail, dict):
            return str(detail.get("message") or detail)
        if detail:
            return str(detail)
    return str(body)[:500]


def _remediation(status: int, url: str) -> str:
    """Return actionable next steps for a rejected request."""
    if status != 401:
        return ""
    host = urllib.parse.urlparse(url).hostname or ""
    system = KIMI_SYSTEMS.get(host, "unknown")
    console = REGION_CONSOLES.get(host, CONSOLE_URL)
    lines = [
        "",
        f"The request went to {host} ({system}), whose keys come from {console}.",
        "",
        "Moonshot runs three credential systems. Keys and base URLs are not",
        "interchangeable, so a key from the wrong one returns 401 even when the",
        "key itself is valid:",
        "",
    ]
    for candidate in sorted(KIMI_HOSTS):
        marker = "->" if candidate == host else "  "
        lines.append(
            f"  {marker} {candidate:<18} {KIMI_SYSTEMS[candidate]:<32} "
            f"{REGION_CONSOLES[candidate]}"
        )
    lines.extend(
        [
            "",
            "Find which system issued your key, then point at it:",
            f"  export {BASE_URL_ENV_VAR}=https://<host from the table above>",
            "",
            "Run `make kimi-doctor` to probe all three and see which one accepts",
            "the key. It never prints the key.",
            "",
            "If every system returns 401, the key itself is rejected: confirm it",
            "is complete, active, and not revoked, then reissue it.",
        ]
    )
    return "\n".join(lines)


def _post(payload: dict[str, Any], *, api_key: str, timeout_s: int) -> dict[str, Any]:
    request = urllib.request.Request(
        resolve_api_url(),
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return json.loads(response.read())


def call_kimi(
    system_prompt: str,
    user_message: str,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    response_format: dict[str, Any] | None = None,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    max_completion_tokens: int = 2048,
    timeout_s: int | None = None,
) -> str:
    """Return the assistant `content` for one single-turn request.

    The system prompt is sent first and must be invariant across a batch so
    Moonshot's automatic context caching can reuse it. Put per-request content in
    `user_message`.

    Retries `RETRYABLE_STATUS` with exponential backoff. Any other HTTP status
    raises `KimiRequestError` immediately: retrying a rejected key or a malformed
    schema only converts one error into a rate-limit error, and a caller that
    degrades gracefully on network trouble must not degrade on a broken request.

    Single-turn only. K3 is trained in preserved-thinking-history mode, so a
    multi-turn caller must append the complete assistant message, including its
    reasoning content, to the next request. This client does not do that, and a
    follow-up turn built on it would degrade quality.
    """
    validate_reasoning_effort(reasoning_effort)
    if timeout_s is None:
        timeout_s = timeout_for(reasoning_effort)
    if response_format is not None:
        assert_mfjs_compatible(response_format)
    payload: dict[str, Any] = {
        "model": model,
        "max_completion_tokens": max_completion_tokens,
        "reasoning_effort": reasoning_effort,
        "response_format": response_format or {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }

    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            body = _post(payload, api_key=api_key, timeout_s=timeout_s)
            break
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code not in RETRYABLE_STATUS:
                raise KimiRequestError(
                    error.code,
                    _error_detail(error) + _remediation(error.code, resolve_api_url()),
                ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
        if attempt < MAX_ATTEMPTS - 1:
            delay = BACKOFF_BASE_S * (2**attempt)
            logger.warning(
                "kimi call failed (%s), retry %s/%s in %.1fs",
                last_error,
                attempt + 1,
                MAX_ATTEMPTS - 1,
                delay,
            )
            time.sleep(delay)
    else:
        assert last_error is not None
        raise last_error

    content = body["choices"][0]["message"]["content"]
    if not content or not content.strip():
        completion_tokens = body.get("usage", {}).get("completion_tokens", "?")
        raise RuntimeError(
            f"Kimi returned empty content. Completion tokens used: "
            f"{completion_tokens}. Raise max_completion_tokens or lower "
            "reasoning_effort."
        )
    return content


def call_kimi_json(
    system_prompt: str,
    user_message: str,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    response_format: dict[str, Any] | None = None,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    max_completion_tokens: int = 2048,
    timeout_s: int | None = None,
) -> dict[str, Any]:
    """Call Kimi and parse the response content as JSON."""
    content = call_kimi(
        system_prompt,
        user_message,
        api_key=api_key,
        model=model,
        response_format=response_format,
        reasoning_effort=reasoning_effort,
        max_completion_tokens=max_completion_tokens,
        timeout_s=timeout_s,
    )
    return json.loads(content)
