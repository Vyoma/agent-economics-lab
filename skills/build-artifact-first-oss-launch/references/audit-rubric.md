# Audit Rubric

Score each dimension `0`, `1`, or `2`.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Decision clarity | Generic problem | Audience or decision is named | Specific owner, decision, and consequence |
| Gap validity | Duplicates an existing feature | Fragmentation is plausible | Missing boundary/invariant is evidenced |
| Category focus | Broad platform | Several related capabilities | One memorable category and wedge |
| Artifact completeness | Slides or concept only | Demo works | Complete input → decision → report loop |
| Falsifiability | Success-only demo | Some negative tests | Fixed protocol, counterexamples, and regeneration |
| Evidence boundary | Inputs implicit | Schema exists | Canonical evidence, version, digest, provenance |
| Modularity | Add-on directory | Add/remove possible | Optional deletion safe; required deletion incomplete |
| Claim hygiene | Production/general claims | Limitations buried | Claim level, denominator, and limitation adjacent |
| Compatibility | Replacement posture | Offline boundary | Tested adapters or clearly labeled contribution lanes |
| Reproducibility | Manual setup | Documented command | Clean-run command, CI, deterministic checked-in results |
| OSS trust | Missing basics | License/tests present | CI, security, contribution paths, status, issue templates |
| Discoverability | Generic bio/readme | Keywords present | Category → question → test → result → CTA |

## Interpretation

- `0–8`: idea or content asset; do not position as a new OSS category.
- `9–16`: promising prototype; narrow claims and finish the evidence loop.
- `17–21`: credible alpha; launch to technical early adopters with limitations.
- `22–24`: strong artifact-first launch; pursue external cases and adapters.

The score is not a substitute for a blocker. Any blocker below overrides the total.

## Blockers

- Primary command fails.
- Results cannot be regenerated.
- Required coverage can disappear silently.
- Claimed integration has no fixture-backed test.
- Synthetic results are described as production evidence.
- License or provenance is unclear.
- Public biography or contact data is unconfirmed.

## Required audit output

Return:

1. score table with file/line or source evidence;
2. blocker list;
3. top three changes by trust gained per unit effort;
4. claims to delete, narrow, or defer;
5. commands actually executed and results; and
6. facts that still require user confirmation.
