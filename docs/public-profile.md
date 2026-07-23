# Public Profile Copy Aligned to the Artifact

This copy keeps the open-source, research, teaching, and fellowship narratives on
one technical spine. Update employer-specific facts separately before publishing.

## GitHub public profile

The profile should sell one scarce capability: turning messy agent behavior into
reproducible evidence and explicit enterprise decisions. It should not try to fit a
full executive biography into GitHub's small profile card.

Use these values:

| Field | Recommended value | Why |
|---|---|---|
| Name | `Vyoma Gajjar` | Use the searchable professional name, not only the handle. |
| Bio | `Applied AI research engineer building economic assurance for AI agents: trace-to-outcome evals, fail-safe decision gates, and reproducible benchmarks.` | 150 characters; names the category, the shipped mechanism, and the proof format. |
| URL | `https://github.com/Vyoma/agent-economics-lab` | Point at the flagship artifact after the repository is public. Replace this with a personal site only when that site has equally strong technical evidence. |
| Company | `@ServiceNow` only if the current affiliation and public disclosure are confirmed | The company field should be factual and current; do not use it as a list of past logos. |
| Location | Leave blank until a preferred public location is confirmed | Do not infer location from a timezone. |
| Public email | Leave blank for now | A personal email attracts spam. Prefer a dedicated professional alias or a contact page. |
| Pronouns | Use the owner's preference | Do not infer. |
| Social 1 | Exact LinkedIn profile URL | Best general professional identity link. |
| Social 2 | Exact Google Scholar profile URL, if active | Supports the applied-research positioning. |
| Social 3 | Exact ORCID URL, if active | Provides a persistent research identity. |
| Social 4 | Maven instructor page or personal site | Supports the technical-educator dimension without crowding the bio. |

Recommended visibility settings:

- include private contributions without revealing repository details;
- show achievements;
- leave `Available for hire` off unless a public search is intentional and compatible
  with the current role; and
- keep activity public so releases, issues, reviews, and contributions reinforce the
  profile narrative.

Publish in this order:

1. Publish `agent-economics-lab` and verify every README command from a clean clone.
2. Create the special public profile repository `Vyoma/Vyoma` and write a focused
   README from the positioning and evidence on this page.
3. Update the bio and URL above.
4. Pin the flagship repository first. Keep the research note, benchmark, protocol,
   and methodology inside that repository so stars and discussion accrue to one
   coherent artifact.
5. Add verified social links and current affiliation last.

The current public account foregrounds eight repositories but has no bio or profile
README. Several popular entries are 2017 Bluemix toolchain artifacts. That makes
the account look historical even though newer work exists. Archive or unpin old
scaffolding only after checking whether any external references depend on it; do
not delete contribution history merely for aesthetics.

The current repositories should not be used as filler pins:

- `map-ai-usage-to-deliverables` is a useful teaching deck, but its README says the
  engine is not in the repository. Keep it as a teaching artifact unless the code,
  tests, and reuse license are published.
- `expert-brief` currently contains only a short README. Do not pin it until the
  application or a meaningful technical artifact is public.
- `bee-agent` presents an upstream starter template. Keep it unpinned unless it is
  transformed into a clearly original, maintained project.
- the 2017 Bluemix toolchain repositories may be archived after checking external
  references. Archiving preserves history while removing the expectation of active
  maintenance.

## Headline

**Applied AI Research Engineer | Economic Assurance for AI Agents**

## About

I turn deployment-side AI-agent failures into reproducible benchmarks, evaluation
harnesses, and control methods.

My background is software-engineering-first: building and debugging production AI
systems where models interact with retrieval, tools, workflows, human reviewers,
and enterprise constraints. The failure modes I care about are the ones that remain
hidden when teams measure only model accuracy or token spend: multi-call cost,
unacceptable outcomes, weak counterfactuals, tail loss, authority leakage, missing
provenance, and controls that disappear without making the decision visibly weaker.

My current open-source project, Agent Economics Lab, converts traces, outcomes,
labor/risk cost, a named baseline, and versioned checks into an auditable
`INCOMPLETE / SCALE / ASSIST / STOP` result. Its first research artifact is a
deterministic false-green benchmark: 98 synthetic scenarios and 588 evidence
ablations testing whether missing assurance coverage can silently manufacture a
green decision.

The result is narrow but reproducible: an unsafe comparator produced 23 false
`SCALE` decisions; the fail-safe coverage model produced zero and returned
`INCOMPLETE` instead. This is a controlled software stress test, not a production
prevalence estimate.

Current research direction:

- agent evaluation and economic assurance;
- multi-agent handoff, authority, and provenance failures;
- tool-layer gates and runtime control;
- monitor blind spots in long-horizon traces; and
- methods that make missing evidence explicit rather than silently green.

I’m most interested in teams and collaborators who value empirical questions,
public artifacts, reproducibility, and clear negative scope.

## Featured section order

1. **Agent Economics Lab repository:** runnable system and modularity demo.
2. **False-Green Assurance note:** research question, method, result, limitations.
3. **Benchmark card and data card:** generated evidence and claim boundary.
4. **Two-minute demo:** optional deletion, fail-safe required deletion, custom gate.
5. **Methodology:** cost per acceptable outcome and counterfactual routing.
6. **Teaching/course material:** supporting proof after the technical artifacts.

## One-sentence introduction

> I build reproducible benchmarks and controls for the hidden ways AI agents fail
> when they use tools, accumulate cost, hand work off, and operate under real
> constraints.

## Evidence-safe short bio

> Vyoma Gajjar is a software-engineering-first applied AI research engineer focused
> on agent evaluation and economic assurance. Her open-source work turns
> deployment-side failure modes into reproducible code, synthetic benchmarks,
> explicit decision gates, and falsifiable technical notes; multi-agent handoff and
> provenance failures are the next research direction.

## Claims to avoid

- “Enterprise-proven” until independent workload cases are published.
- “Prevents false-green decisions” without specifying the synthetic benchmark.
- “Works with Galileo/LangSmith/OpenTelemetry” until their export mappers ship.
- “Semantic loop detection” or “deadlock proof.”
- “Research benchmark” without linking the protocol, generated rows, and data card.
