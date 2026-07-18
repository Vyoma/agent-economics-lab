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
| Controlled benchmark | False-Green Assurance Benchmark | Falsifiable hypothesis, ablation, generated dataset, result |
| Paper-style communication | `research/NOTE.md` | Method, interpretation, threats to validity |
| External validation | Contribution case-study lane | Independent, redacted workload evidence |
| Next research environment | Handoff/provenance simulator | Multi-agent safety question built on the same evidence model |

Every layer reuses the canonical `EvidenceBundle`, typed checks, coverage manifest,
and reproducibility command. Product and research do not fork into separate stories.

## Portfolio decisions from the deep-research report

The report proposed JudgeBench, HandoffLab, ToolGate-Control, MonitorBlind, and
DeepResearch-Eval. They are all plausible; building all five in parallel would
weaken the evidence.

| Proposed artifact | Cohesive decision |
|---|---|
| JudgeBench-Reliability | Valuable independent benchmark; defer until the current benchmark is externally reviewed |
| HandoffLab | **Next primary research extension** because provenance, authority, and responsibility can extend the existing evidence schema |
| ToolGate-Control | Downstream enforcement consumer; keep outside this offline assurance kernel |
| MonitorBlind | Later diagnostic benchmark; do not add an LLM judge to the standard-library-only core |
| DeepResearch-Eval | Separate OpenAI-oriented lane only if application timing justifies it |

## Sequenced twelve-week plan

### Weeks 1–2: publish one complete artifact

- Ship the modular engine, false-green benchmark, data card, protocol, note, and demo.
- Ask five engineers and three eval/FinOps practitioners to reproduce the result.
- Record setup failures and counterexamples publicly.

### Weeks 3–5: external evidence cases

- Add one offline OpenTelemetry GenAI mapper with pinned fixtures.
- Collect three synthetic or fully anonymized assurance cases from independent users.
- Pre-register thresholds before calculating each case.
- Publish decision-preserving and decision-reversing cases.

### Weeks 6–9: HandoffLab as an extension, not a restart

- Extend `EvidenceBundle` with role, authority, provenance, and handoff fields only
  after writing the research protocol.
- Generate controlled heterogeneous-agent workflows.
- Measure privilege leakage, provenance completeness, failed escalation,
  responsibility drop, and unsafe action rate.
- Compare a no-control baseline with explicit handoff gates.

### Weeks 10–12: consolidate evidence

- Publish one benchmark report and one negative or null finding.
- Record which hypotheses failed or narrowed.
- Create a short portfolio page linking the code, data card, note, and demo.
- Begin targeted outreach only after independent reproduction or external cases.

## Public proof stack

The Featured section or portfolio should link, in order:

1. repository README;
2. generated benchmark result;
3. paper-style note;
4. data card and protocol;
5. two-minute modularity demo; and
6. only then a lesson, talk, or course.

Ready-to-use headline, About copy, Featured ordering, and claim-safe bio are in
[`public-profile.md`](public-profile.md).

The public claim should be:

> I turn deployment-side failure modes into reproducible agent-evaluation and
> control experiments, then publish the code, data, result, and limitations.

Avoid claiming that synthetic results establish production prevalence, that a
structural warning proves semantic failure, or that a modular API is itself novel.
