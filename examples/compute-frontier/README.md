# Synthetic Support Budget Frontier

This fixture compares four recorded agent configurations on the same 180 task IDs,
input digests, and rubric version:

- `premium-8-step`, the reference route;
- `balanced-4-step`, a cheap-first route with escalation;
- `cheap-2-step`, a lower-cost route with more harmful regressions; and
- `premium-12-step`, a higher-compute route with a small point-quality gain.

The arm-independent task identities live in `task-manifest.json`; its SHA-256 digest
is frozen in `manifest.json` and verified before any arm is evaluated.

Run the complete experiment:

```bash
python3 -m agent_economics frontier \
  examples/compute-frontier/manifest.json \
  --output-dir /tmp/agent-economics-frontier
```

The expected result is `ADOPT balanced-4-step`. It is the lowest-cost tested arm
whose exact upper confidence bound on harmful regressions stays below the frozen
5% tolerance and whose paired full-cost reduction lower bound exceeds 25%.

Regenerate the transparent input fixtures with:

```bash
python3 examples/compute-frontier/generate.py
```

The fixture is synthetic. It validates the implementation and selection rule. It
does not demonstrate production prevalence, causal impact, or future model behavior.
