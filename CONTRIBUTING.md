# Contributing

The project optimizes for auditable claims over feature breadth.

## Best first contributions

- An offline source adapter that maps a documented export to `EvidenceBundle` and
  proves digest/result equivalence against a canonical fixture.
- A typed assurance gate or diagnostic with declared coverage and failure semantics.
- A synthetic or fully anonymized assurance case from a real workload pattern.
- A counterexample that falsifies or narrows a benchmark hypothesis.
- A clearer outcome contract or counterfactual.
- A failure case that exposes incorrect math or a hidden assumption.
- A statistically sound uncertainty or segmentation method with no heavy runtime.

Please open an issue before adding a hosted service, dashboard, runtime proxy,
framework abstraction, or generalized policy language.

## Local verification

```bash
make test
make demo
make modularity
make lessons
make benchmark
make reproduce
```

The project supports Python 3.10+ and keeps the core dependency-free. New runtime
dependencies require an issue explaining why the assurance claim cannot be made
without them.

## Claim discipline

Use precise language in code, docs, and issues:

- say **structural repetition warning**, not semantic-loop proof;
- say **dependency cycle**, not deadlock, unless wait/progress semantics are present;
- say **no additional model inference**, not zero compute;
- say **observed association**, not causal savings, without a valid design; and
- name the population, observation window, and counterfactual.

Tests should cover important non-claims as well as happy paths.

## Case-study safety

Do not submit customer data, secrets, personal information, proprietary prompts,
real customer identifiers, internal model names, or contract pricing. Aggregate,
redact, or synthesize evidence before opening an issue or pull request. Contributors
are responsible for having permission to share their material.
