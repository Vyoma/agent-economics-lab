# One Cohesive Research and Open-Source Agenda

## Thesis

Convert field-observed agent failures into small, falsifiable, public artifacts:

```text
field observation
    -> research question
    -> controlled evidence or simulator
    -> baseline and ablation
    -> reproducible result
    -> honest claim boundary
    -> reusable open-source component
```

This standard matches current public selection signals for empirical research work.
The [Anthropic Fellows program](https://alignment.anthropic.com/2025/anthropic-fellows-program-2026/)
emphasizes Python execution, progress on ambiguous technical questions, shipping
under uncertainty, and public outputs. The
[OpenAI Safety Fellowship](https://openai.com/index/introducing-openai-safety-fellowship/)
expects empirically grounded work and a substantial output such as a paper,
benchmark, or dataset. The
[Astra empirical stream](https://constellation.org/programs/astra/empirical)
uses coding tests, work tests, interviews, and references.

The implication is not to create many superficial repos. It is to make each public
artifact carry code, data, method, result, and limitations.

## The unified stack

| Layer | Current artifact | Evidence it provides |
|---|---|---|
| Open-source kernel | Agent Economics Lab | Software engineering, explicit contracts, reproducibility |
| Paired experiment | Economic Assurance Frontier | Exact task pairing, breakage bounds, full-cost intervals, bounded selection |
| Engine conformance | False-Green Assurance Benchmark | Fail-safe coverage invariant under constructed ablations |
| Research communication | Frontier protocol and data card | Method, hypotheses, threats to validity, and claim boundary |
| External validation | Paired frontier contribution lane | Permissioned, redacted matched-workload evidence |
| Next integration | OpenTelemetry GenAI fixture adapter | A real normalized intake path without a live vendor dependency |

Every layer reuses the canonical `EvidenceBundle`, typed checks, coverage manifest,
plan and evidence digests, and reproducibility command.

## Portfolio decisions from the deep-research report

The report proposed JudgeBench, HandoffLab, ToolGate-Control, MonitorBlind, and
DeepResearch-Eval. They are all plausible; building all five in parallel would
weaken the evidence.

| Proposed artifact | Cohesive decision |
|---|---|
| JudgeBench-Reliability | Defer until outcome-label reliability is measured on an external frontier case |
| HandoffLab | Defer; current delegation benchmarks already cover quality, routing, and handoff efficiency, while this repo still needs a real paired economic case |
| ToolGate-Control | Downstream enforcement consumer; keep outside this offline assurance kernel |
| MonitorBlind | Later diagnostic benchmark; do not add an LLM judge to the standard-library-only core |
| DeepResearch-Eval | Separate OpenAI-oriented lane only if application timing justifies it |

## Sequenced twelve-week plan

### Weeks 1–2: ship the paired frontier

- Ship paired task alignment, exact breakage bounds, simultaneous cost intervals,
  fail-closed completeness, portable reports, a protocol, and a transparent fixture.
- Keep the old false-green result as an engine invariant rather than the headline.
- Ask five agent engineers and three eval/FinOps practitioners to reproduce the result.

### Weeks 3–5: real intake and independent reproduction

- Add one offline OpenTelemetry GenAI mapper with pinned fixtures.
- Collect one permissioned, redacted matched-task case with at least 100 task IDs and
  three tested configurations.
- Freeze the rubric, candidate family, margins, and subgroup plan before analysis.
- Publish at least one negative or null candidate result, not only the selected arm.

### Weeks 6–9: label reliability and subgroup robustness

- Add outcome-label provenance and agreement metadata.
- Predeclare critical subgroups and refuse aggregate selection when a protected or
  high-risk slice exceeds breakage tolerance.
- Test sensitivity to missing failed runs, delayed remediation, and provider drift.

### Weeks 10–12: consolidate evidence

- Publish one benchmark report and one negative or null finding.
- Record which hypotheses failed or narrowed.
- Create a short portfolio page linking the code, data card, note, and demo.
- Begin targeted outreach only after independent reproduction or external cases.

## Public proof stack

The Featured section or portfolio should link, in order:

1. repository README;
2. generated frontier report and plot;
3. frontier protocol and data card;
4. permissioned external case when available;
5. engine conformance and modularity demo; and
6. only then a lesson, talk, or course.

Ready-to-use headline, About copy, Featured ordering, and claim-safe bio are in
[`public-profile.md`](public-profile.md).

The public claim should be:

> I turn deployment-side failure modes into reproducible agent-evaluation and
> control experiments, then publish the code, data, result, and limitations.

Avoid claiming that synthetic results establish production prevalence, that a
structural warning proves semantic failure, or that a modular API is itself novel.
