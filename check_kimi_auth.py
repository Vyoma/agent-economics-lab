"""Diagnose a Kimi 401 without printing the key.

Moonshot runs three credential systems whose keys and base URLs are not
interchangeable, so a valid key returns 401 against the wrong one. This probes
every system with the configured key and reports which accepts it.

Only safe information is printed: key length, prefix, whether stray whitespace or
quotes are present, and the HTTP status per system. Never the key.

    python3 check_kimi_auth.py
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from agent_economics import kimi_client


def probe(host: str, api_key: str) -> tuple[bool, str]:
    """Return (accepted, status text) for one Kimi system."""
    url = f"https://{host}{kimi_client.KIMI_ENDPOINTS[host]}"
    payload = {
        "model": kimi_client.DEFAULT_MODEL,
        "max_completion_tokens": 16,
        "messages": [{"role": "user", "content": "ping"}],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return True, f"{response.status} authenticated"
    except urllib.error.HTTPError as error:
        detail = kimi_client._error_detail(error)[:60]
        # 401 and 403 are credential rejections. Any other status means the key
        # was accepted and the request failed for a different reason, which still
        # identifies the correct system.
        accepted = error.code not in (401, 403)
        return accepted, f"{error.code} {detail}"
    except urllib.error.URLError as error:
        return False, f"unreachable ({error.reason})"


def main() -> int:
    raw = os.environ.get(kimi_client.API_KEY_ENV_VAR)
    if not raw:
        print(f"{kimi_client.API_KEY_ENV_VAR} is not set.")
        print(f"Get a key, then: export {kimi_client.API_KEY_ENV_VAR}=...")
        return 1

    cleaned = raw.strip().strip("'\"").strip()
    print("KEY SHAPE  (no secret shown)")
    print(f"  raw length                  {len(raw)}")
    print(f"  cleaned length              {len(cleaned)}")
    print(f"  starts with 'sk-'           {cleaned.startswith('sk-')}")
    print(f"  stray whitespace or quotes  {raw != cleaned}")
    print()

    # Stop before the network. A placeholder cannot be authenticated by anyone,
    # and probing it three times only produces a misleading "rejected" verdict.
    problem = kimi_client.api_key_shape_problem(cleaned)
    if problem:
        print(f"This is not a usable key: {problem}")
        print()
        print("Get a real key from the console matching your plan:")
        for host in sorted(kimi_client.KIMI_HOSTS):
            print(
                f"  {kimi_client.REGION_CONSOLES[host]:<34} "
                f"{kimi_client.KIMI_SYSTEMS[host]}"
            )
        print()
        print("Then export it. Do not copy the placeholder text from the docs:")
        print(f"  export {kimi_client.API_KEY_ENV_VAR}='<paste the real key>'")
        return 1


    override = os.environ.get(kimi_client.BASE_URL_ENV_VAR)
    print(f"CURRENT TARGET  {kimi_client.resolve_api_url()}")
    print(
        f"  {kimi_client.BASE_URL_ENV_VAR} "
        f"{'= ' + override if override else 'not set, using the default'}"
    )
    print()

    print("PROBE  which system accepts this key?")
    accepted: list[str] = []
    for host in sorted(kimi_client.KIMI_HOSTS):
        ok, status = probe(host, cleaned)
        mark = "OK  " if ok else "no  "
        print(f"  [{mark}] {host:<18} {kimi_client.KIMI_SYSTEMS[host]:<32} {status}")
        if ok:
            accepted.append(host)
    print()

    if not accepted:
        print("No system accepted the key. The credential itself is rejected.")
        print("Confirm it is complete, active, and not revoked, then reissue it.")
        print("Consoles:")
        for host in sorted(kimi_client.KIMI_HOSTS):
            print(
                f"  {kimi_client.REGION_CONSOLES[host]:<34} "
                f"{kimi_client.KIMI_SYSTEMS[host]}"
            )
        return 2

    target = accepted[0]
    print(f"This key belongs to: {kimi_client.KIMI_SYSTEMS[target]} ({target})")
    if kimi_client.resolve_api_url().startswith(f"https://{target}"):
        print("Already pointed at the right system. Run: make kimi-judge")
    else:
        print("Point at it with:")
        print(f"  export {kimi_client.BASE_URL_ENV_VAR}=https://{target}")
        print("  make kimi-judge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
