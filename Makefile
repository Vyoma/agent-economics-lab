PYTHON ?= python3

# Every target depends on this, not just `reproduce` and `test`. It guarded two
# of thirty-four, so `make demo` -- the first command in the README, run by
# someone who has just cloned -- crashed with a TypeError from `mutation.py` on
# stock macOS Python 3.9 instead of printing the message below. A check that
# does not run on the path that matters is not a check that passed, which is
# this project's own thesis applied to its own front door.
#
# The package declares requires-python >= 3.10, but `make` cannot enforce that
# the way pip does. Without this guard a contributor whose default python3 is
# older gets obscure failures instead of a usable message: on such a machine
# `make reproduce` fails inside kimi_client with a mock error, six layers from
# the actual cause.
check-python:
	@$(PYTHON) -c 'import sys; sys.version_info >= (3, 10) or sys.exit("agent-economics-lab requires Python 3.10 or newer; %d.%d found. Retry with: make PYTHON=python3.12 <target>" % sys.version_info[:2])'

.PHONY: check-python lint coverage label-error demo falsegreen coverage-drift evidence-ablation frontier modularity claude-code claude-code-tree otel-genai public-case benchmark mutation-score sensitivity completion-vs-verdict kimi-judge kimi-doctor kimi-eval reproduce lessons test video

demo: check-python
	@$(PYTHON) -m agent_economics evaluate \
		--traces examples/support_trace.csv \
		--outcomes examples/outcomes.csv \
		--rates examples/rates.json \
		--baseline examples/baseline.json \
		--policy examples/policy.json

modularity: check-python
	PYTHONPATH=. $(PYTHON) examples/modularity_demo.py

coverage-drift: check-python
	@$(PYTHON) false_green.py

falsegreen: coverage-drift check-python

benchmark: check-python
	$(PYTHON) false_green.py \
		--verify research/results/decision-coverage-drift/results.csv \
		--summary-verify research/results/SUMMARY.md \
		--json-verify research/results/decision-coverage-drift/summary.json

evidence-ablation: check-python
	@$(PYTHON) evidence_ablation.py \
		--verify-dir research/results/evidence-ablation

mutation-score: check-python
	@$(PYTHON) mutation_score.py \
		--summary-verify research/results/mutation-score/summary.md \
		--json-verify research/results/mutation-score/summary.json

label-error: check-python
	@$(PYTHON) -m agent_economics.label_error

sensitivity: check-python
	@$(PYTHON) sensitivity_sweep.py \
		--summary-verify research/results/sensitivity/summary.md \
		--json-verify research/results/sensitivity/summary.json

completion-vs-verdict: check-python
	@$(PYTHON) completion_vs_verdict.py \
		--verify research/results/completion-vs-verdict/report.txt

# Diagnose a Kimi auth failure. Prints key shape and per-region HTTP status,
# never the key. Makes live calls, so it is excluded from `make reproduce`.
kimi-doctor: check-python
	@$(PYTHON) check_kimi_auth.py

# Live judge eval: scores Kimi labels against the hand-authored eval set.
# Requires MOONSHOT_API_KEY, so it is excluded from `make reproduce`. The scoring
# math and eval-set integrity are covered hermetically by `make test`.
kimi-eval: check-python
	@if [ -z "$$MOONSHOT_API_KEY" ]; then \
		echo "Cannot run the live judge eval: MOONSHOT_API_KEY is not set."; \
		echo "The scoring math and eval set are tested without a key: make test"; \
		exit 1; \
	fi
	@$(PYTHON) kimi_eval.py \
		--save-predictions /tmp/agent-economics-judge-predictions.json \
		--save-verdicts /tmp/agent-economics-judge-verdicts.json \
		--output /tmp/agent-economics-judge-eval.txt

# Live Kimi call. Opt-in: requires MOONSHOT_API_KEY and is excluded from
# `make reproduce` so the offline suite stays hermetic.
kimi-judge: check-python
	@if [ -z "$$MOONSHOT_API_KEY" ]; then \
		echo "Cannot run the live Kimi judge: MOONSHOT_API_KEY is not set."; \
		echo "This is a missing prerequisite, not a build failure."; \
		echo ""; \
		echo "  export MOONSHOT_API_KEY=...   # https://platform.kimi.ai"; \
		echo "  make kimi-judge"; \
		echo ""; \
		echo "Everything else runs without a key:"; \
		echo "  make test        rubric, schema, retry, and fallback conformance"; \
		echo "  make reproduce   the full offline suite"; \
		echo ""; \
		echo "Already set a key and getting 401? Run: make kimi-doctor"; \
		exit 1; \
	fi
	@$(PYTHON) -m agent_economics judge \
		--task-results examples/kimi-judge/task_results.csv \
		--rubric examples/kimi-judge/rubric.json \
		--out /tmp/agent-economics-kimi-outcomes.csv

frontier: check-python
	@$(PYTHON) -m agent_economics frontier \
		examples/compute-frontier/manifest.json \
		--output-dir /tmp/agent-economics-frontier \
		--verify-dir research/results/frontier

# The detector on code it did not come from. Deliberately NOT in `reproduce`:
# it measures the running interpreter's own standard library, so its numbers
# move with the Python version and the CI matrix spans four. Byte-comparing it
# there would fail on three of them for a reason that is not a defect. The
# artifact records the version it was generated on; this regenerates and diffs
# without asserting, so drift is visible without being fatal.
held-out: check-python
	@$(PYTHON) research/held_out.py --check research/HELD_OUT.md

# Append-only. Issues a NEW claim file named by date and revision; it never
# rewrites an existing one, because a record that overwrites itself is not a
# record. The first version overwrote two files on every reissue, so the
# "record" was permanently two current claims.
#   make issue-claim BUNDLE=examples/x/bundle.json SLUG=x ASSERTION="..."
issue-claim: check-python
	@test -n "$(BUNDLE)" -a -n "$(SLUG)" -a -n "$(ASSERTION)" \
		|| { echo "need BUNDLE, SLUG and ASSERTION"; exit 2; }
	@$(PYTHON) -m agent_economics claim \
		--bundle "$(BUNDLE)" \
		--issuer agent-economics-lab \
		--source-commit "$$(git rev-parse HEAD)" \
		--assertion "$(ASSERTION)" \
		--output "research/claims/$$(date +%Y-%m-%d)-$(SLUG)-$$(git rev-parse --short=8 HEAD).claim.json"

# Reads two outcome fields across every model arm that could be downloaded and
# reports where they disagree. Derived from frozen content-free evidence, so it
# needs no network and no 740MB of trajectories.
outcome-audit: check-python
	@$(PYTHON) research/outcome_audit.py > /tmp/agent-economics-outcome-audit.md
	@cmp /tmp/agent-economics-outcome-audit.md research/OUTCOME_AUDIT.md

# The instrument's own scorecard, assembled from the frozen eval artifacts.
evals: check-python
	@$(PYTHON) research/evals.py > /tmp/agent-economics-evals.md
	@cmp /tmp/agent-economics-evals.md research/EVALS.md

# The measured envelope: full decision path at three scales, written to
# bench/RESULTS.json and rendered to docs/at-scale.md. bench-smoke is the CI
# ratio guard: superlinear scaling on the realistic shape fails the build.
bench: check-python
	@$(PYTHON) bench/run.py
	@$(PYTHON) bench/render.py > docs/at-scale.md

bench-smoke: check-python
	@$(PYTHON) bench/run.py --smoke

bench-check: check-python
	@$(PYTHON) bench/render.py > /tmp/agent-economics-at-scale.md
	@cmp /tmp/agent-economics-at-scale.md docs/at-scale.md

# The one research target that needs the network, deliberately outside
# `reproduce`: spot-check frozen rows against the upstream dataset at its
# pinned revision, always including the rows the published findings stand on.
verify-upstream: check-python
	@$(PYTHON) research/verify_upstream.py --sample 3

# The registry of every public dataset audited, rendered from frozen evidence
# alone. Fails when the committed document and the evidence disagree.
corpus: check-python
	@$(PYTHON) research/corpus/audit.py > /tmp/agent-economics-corpus.md
	@cmp /tmp/agent-economics-corpus.md research/CORPUS.md

# The ledger is the record. --check fails the build on a REFUTED claim, on a
# malformed one, and on an UNVERIFIED one pinning no revision a reader could
# check it against. A published falsehood stays a failure until it is retracted
# rather than quietly regenerated.
ledger: check-python
	@$(PYTHON) research/ledger.py --check
	@$(PYTHON) research/ledger.py > /tmp/agent-economics-ledger.md
	@cmp /tmp/agent-economics-ledger.md research/claims/LEDGER.md

# The ledger verifies every claim against the evidence it names. This adds the
# other direction: handed the wrong evidence a claim must refuse. A verifier
# that only ever says SUPPORTED is not a verifier.
claims: ledger check-python
	@set -e; for claim in research/claims/*-claude-code-*.claim.json; do \
		! $(PYTHON) -m agent_economics verify \
			--claim "$$claim" \
			--bundle examples/checks-only/bundle.json > /dev/null 2>&1; \
	done

# Regenerates the pre-registered site list. It must not drift from the code it
# was derived from, or the search it authorises is against a different package.
probe-sites: check-python
	@$(PYTHON) research/probe_sites.py > /tmp/agent-economics-probe-sites.md
	@cmp /tmp/agent-economics-probe-sites.md research/PROBE_SITES.md

# Checks out the commit before each catalogued defect's fix, runs the whole
# suite there, and runs the probe that discriminates. Pinned commits, so the
# output is deterministic and byte-comparable like any other artifact.
green-defects: check-python
	@$(PYTHON) research/green_defects.py $(PYTHON) > /tmp/agent-economics-green-defects.md
	@cmp /tmp/agent-economics-green-defects.md research/GREEN_DEFECTS.md

# The same session as the claude-code example, converted under a contract that
# declares no rate card. Proves the checks-only path is reachable from a real
# trace through `convert`, not only from the Python API.
checks-only: check-python
	@$(PYTHON) -m agent_economics convert \
		--from claude-code \
		--in examples/claude-code/session.jsonl \
		--contract examples/checks-only/conversion-contract.json \
		--out /tmp/agent-economics-checks-only.json
	@cmp /tmp/agent-economics-checks-only.json examples/checks-only/bundle.json

# The audit is the package's front door and was outside the build gate entirely.
# --ci exits nonzero on any ground, so these assert the withheld verdicts stay
# withheld rather than merely that the command runs.
audit: check-python
	@$(PYTHON) -m agent_economics audit --bundle examples/checks-only/bundle.json >/dev/null
	@! $(PYTHON) -m agent_economics audit --bundle examples/checks-only/bundle.json --ci >/dev/null 2>&1
	@! $(PYTHON) -m agent_economics audit --bundle examples/claude-code/bundle.json --ci >/dev/null 2>&1
	@$(PYTHON) -m agent_economics audit --bundle examples/claude-code/bundle.json --format json >/dev/null

claude-code: check-python
	@$(PYTHON) -m agent_economics convert \
		--from claude-code \
		--in examples/claude-code/session.jsonl \
		--contract examples/claude-code/conversion-contract.json \
		--out /tmp/agent-economics-claude-code.json
	@cmp /tmp/agent-economics-claude-code.json examples/claude-code/bundle.json
	@$(PYTHON) -m agent_economics evaluate \
		--bundle /tmp/agent-economics-claude-code.json

claude-code-tree: check-python
	@$(PYTHON) -m agent_economics convert \
		--from claude-code-tree \
		--in examples/claude-code-tree/session.jsonl \
		--contract examples/claude-code-tree/conversion-contract.json \
		--out /tmp/agent-economics-claude-code-tree.json
	@cmp /tmp/agent-economics-claude-code-tree.json examples/claude-code-tree/bundle.json
	@$(PYTHON) -m agent_economics evaluate \
		--bundle /tmp/agent-economics-claude-code-tree.json \
		--attestations examples/attestations.json \
		--as-of 2026-09-01 \
		--ci

otel-genai: check-python
	@$(PYTHON) -m agent_economics convert \
		--from otel-genai \
		--in examples/otel-genai/langfuse-otlp.json \
		--contract examples/otel-genai/langfuse-conversion-contract.json \
		--out /tmp/agent-economics-otel-langfuse.json
	@cmp /tmp/agent-economics-otel-langfuse.json examples/otel-genai/langfuse-bundle.json
	@$(PYTHON) -m agent_economics evaluate \
		--bundle /tmp/agent-economics-otel-langfuse.json \
		--attestations examples/attestations.json \
		--as-of 2026-09-01 \
		--ci
	@$(PYTHON) -m agent_economics convert \
		--from otel-genai \
		--in examples/otel-genai/arize-openinference-otlp.json \
		--contract examples/otel-genai/arize-openinference-conversion-contract.json \
		--out /tmp/agent-economics-otel-arize.json
	@cmp /tmp/agent-economics-otel-arize.json examples/otel-genai/arize-openinference-bundle.json
	@$(PYTHON) -m agent_economics evaluate \
		--bundle /tmp/agent-economics-otel-arize.json \
		--attestations examples/attestations.json \
		--as-of 2026-09-01 \
		--ci

public-case: check-python
	@PYTHONPATH=. $(PYTHON) examples/public-swebench/build_case.py \
		--source examples/public-swebench/runs.json \
		--output-dir /tmp/agent-economics-public-swebench
	@cmp /tmp/agent-economics-public-swebench/arms/candidate-opus.json \
		examples/public-swebench/arms/candidate-opus.json
	@cmp /tmp/agent-economics-public-swebench/arms/reference-haiku.json \
		examples/public-swebench/arms/reference-haiku.json
	@$(PYTHON) -m agent_economics evaluate \
		--bundle /tmp/agent-economics-public-swebench/arms/candidate-opus.json
	@$(PYTHON) -m agent_economics frontier \
		/tmp/agent-economics-public-swebench/manifest.json \
		--output-dir /tmp/agent-economics-public-swebench-rendered \
		--verify-dir examples/public-swebench/frontier \
		|| [ $$? -eq 3 ]

reproduce: check-python test modularity lessons benchmark mutation-score label-error sensitivity completion-vs-verdict evidence-ablation frontier claude-code claude-code-tree otel-genai public-case checks-only audit green-defects probe-sites claims outcome-audit corpus evals

lessons: check-python
# Without set -e the loop reports only the LAST lesson's exit status, so a
# failing lesson 00-03 is masked whenever 04 succeeds. A check that can
# silently not run is the exact failure this repository exists to refuse.
	@set -e; for lesson in lessons/*.py; do PYTHONPATH=. $(PYTHON) "$$lesson"; done

video: check-python
	@$(PYTHON) render_video.py

lint: check-python
	@$(PYTHON) -m ruff check .

coverage: check-python
	@$(PYTHON) -m coverage run --source=agent_economics -m unittest discover -s tests
	@$(PYTHON) -m coverage report

test: check-python
	$(PYTHON) -m unittest discover -s tests -v
