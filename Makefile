PYTHON ?= python3

# The package declares requires-python >= 3.10, but `make` cannot enforce that
# the way pip does. Without this guard a contributor whose default python3 is
# older gets obscure failures instead of a usable message: on such a machine
# `make reproduce` fails inside kimi_client with a mock error, six layers from
# the actual cause.
check-python:
	@$(PYTHON) -c 'import sys; sys.version_info >= (3, 10) or sys.exit("agent-economics-lab requires Python 3.10 or newer; %d.%d found. Retry with: make PYTHON=python3.12 <target>" % sys.version_info[:2])'

.PHONY: check-python lint coverage label-error demo falsegreen coverage-drift evidence-ablation frontier modularity claude-code claude-code-tree otel-genai public-case benchmark mutation-score sensitivity completion-vs-verdict kimi-judge kimi-doctor kimi-eval reproduce lessons test video

demo:
	@$(PYTHON) -m agent_economics evaluate \
		--traces examples/support_trace.csv \
		--outcomes examples/outcomes.csv \
		--rates examples/rates.json \
		--baseline examples/baseline.json \
		--policy examples/policy.json

modularity:
	PYTHONPATH=. $(PYTHON) examples/modularity_demo.py

coverage-drift:
	@$(PYTHON) false_green.py

falsegreen: coverage-drift

benchmark:
	$(PYTHON) false_green.py \
		--verify research/results/decision-coverage-drift/results.csv \
		--summary-verify research/results/SUMMARY.md \
		--json-verify research/results/decision-coverage-drift/summary.json

evidence-ablation:
	@$(PYTHON) evidence_ablation.py \
		--verify-dir research/results/evidence-ablation

mutation-score:
	@$(PYTHON) mutation_score.py \
		--summary-verify research/results/mutation-score/summary.md \
		--json-verify research/results/mutation-score/summary.json

label-error:
	@$(PYTHON) -m agent_economics.label_error

sensitivity:
	@$(PYTHON) sensitivity_sweep.py \
		--summary-verify research/results/sensitivity/summary.md \
		--json-verify research/results/sensitivity/summary.json

completion-vs-verdict:
	@$(PYTHON) completion_vs_verdict.py \
		--verify research/results/completion-vs-verdict/report.txt

# Diagnose a Kimi auth failure. Prints key shape and per-region HTTP status,
# never the key. Makes live calls, so it is excluded from `make reproduce`.
kimi-doctor:
	@$(PYTHON) check_kimi_auth.py

# Live judge eval: scores Kimi labels against the hand-authored eval set.
# Requires MOONSHOT_API_KEY, so it is excluded from `make reproduce`. The scoring
# math and eval-set integrity are covered hermetically by `make test`.
kimi-eval:
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
kimi-judge:
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

frontier:
	@$(PYTHON) -m agent_economics frontier \
		examples/compute-frontier/manifest.json \
		--output-dir /tmp/agent-economics-frontier \
		--verify-dir research/results/frontier

# Regenerates the pre-registered site list. It must not drift from the code it
# was derived from, or the search it authorises is against a different package.
probe-sites:
	@$(PYTHON) research/probe_sites.py > /tmp/agent-economics-probe-sites.md
	@cmp /tmp/agent-economics-probe-sites.md research/PROBE_SITES.md

# Checks out the commit before each catalogued defect's fix, runs the whole
# suite there, and runs the probe that discriminates. Pinned commits, so the
# output is deterministic and byte-comparable like any other artifact.
green-defects:
	@$(PYTHON) research/green_defects.py $(PYTHON) > /tmp/agent-economics-green-defects.md
	@cmp /tmp/agent-economics-green-defects.md research/GREEN_DEFECTS.md

# The same session as the claude-code example, converted under a contract that
# declares no rate card. Proves the checks-only path is reachable from a real
# trace through `convert`, not only from the Python API.
checks-only:
	@$(PYTHON) -m agent_economics convert \
		--from claude-code \
		--in examples/claude-code/session.jsonl \
		--contract examples/checks-only/conversion-contract.json \
		--out /tmp/agent-economics-checks-only.json
	@cmp /tmp/agent-economics-checks-only.json examples/checks-only/bundle.json

# The audit is the package's front door and was outside the build gate entirely.
# --ci exits nonzero on any ground, so these assert the withheld verdicts stay
# withheld rather than merely that the command runs.
audit:
	@$(PYTHON) -m agent_economics audit --bundle examples/checks-only/bundle.json >/dev/null
	@! $(PYTHON) -m agent_economics audit --bundle examples/checks-only/bundle.json --ci >/dev/null 2>&1
	@! $(PYTHON) -m agent_economics audit --bundle examples/claude-code/bundle.json --ci >/dev/null 2>&1
	@$(PYTHON) -m agent_economics audit --bundle examples/claude-code/bundle.json --format json >/dev/null

claude-code:
	@$(PYTHON) -m agent_economics convert \
		--from claude-code \
		--in examples/claude-code/session.jsonl \
		--contract examples/claude-code/conversion-contract.json \
		--out /tmp/agent-economics-claude-code.json
	@cmp /tmp/agent-economics-claude-code.json examples/claude-code/bundle.json
	@$(PYTHON) -m agent_economics evaluate \
		--bundle /tmp/agent-economics-claude-code.json

claude-code-tree:
	@$(PYTHON) -m agent_economics convert \
		--from claude-code-tree \
		--in examples/claude-code-tree/session.jsonl \
		--contract examples/claude-code-tree/conversion-contract.json \
		--out /tmp/agent-economics-claude-code-tree.json
	@cmp /tmp/agent-economics-claude-code-tree.json examples/claude-code-tree/bundle.json
	@$(PYTHON) -m agent_economics evaluate \
		--bundle /tmp/agent-economics-claude-code-tree.json \
		--ci

otel-genai:
	@$(PYTHON) -m agent_economics convert \
		--from otel-genai \
		--in examples/otel-genai/langfuse-otlp.json \
		--contract examples/otel-genai/langfuse-conversion-contract.json \
		--out /tmp/agent-economics-otel-langfuse.json
	@cmp /tmp/agent-economics-otel-langfuse.json examples/otel-genai/langfuse-bundle.json
	@$(PYTHON) -m agent_economics evaluate \
		--bundle /tmp/agent-economics-otel-langfuse.json \
		--ci
	@$(PYTHON) -m agent_economics convert \
		--from otel-genai \
		--in examples/otel-genai/arize-openinference-otlp.json \
		--contract examples/otel-genai/arize-openinference-conversion-contract.json \
		--out /tmp/agent-economics-otel-arize.json
	@cmp /tmp/agent-economics-otel-arize.json examples/otel-genai/arize-openinference-bundle.json
	@$(PYTHON) -m agent_economics evaluate \
		--bundle /tmp/agent-economics-otel-arize.json \
		--ci

public-case:
	@PYTHONPATH=. $(PYTHON) examples/public-swebench/build_case.py \
		--source examples/public-swebench/runs.json \
		--output-dir /tmp/agent-economics-public-swebench
	@$(PYTHON) -m agent_economics evaluate \
		--bundle /tmp/agent-economics-public-swebench/arms/candidate-opus.json
	@$(PYTHON) -m agent_economics frontier \
		/tmp/agent-economics-public-swebench/manifest.json \
		--output-dir /tmp/agent-economics-public-swebench-rendered \
		--verify-dir examples/public-swebench/frontier \
		|| [ $$? -eq 3 ]

reproduce: check-python test modularity lessons benchmark mutation-score label-error sensitivity completion-vs-verdict evidence-ablation frontier claude-code claude-code-tree otel-genai public-case checks-only audit green-defects probe-sites

lessons:
# Without set -e the loop reports only the LAST lesson's exit status, so a
# failing lesson 00-03 is masked whenever 04 succeeds. A check that can
# silently not run is the exact failure this repository exists to refuse.
	@set -e; for lesson in lessons/*.py; do PYTHONPATH=. $(PYTHON) "$$lesson"; done

video:
	@$(PYTHON) render_video.py

lint:
	@$(PYTHON) -m ruff check .

coverage:
	@$(PYTHON) -m coverage run --source=agent_economics -m unittest discover -s tests
	@$(PYTHON) -m coverage report

test: check-python
	$(PYTHON) -m unittest discover -s tests -v
