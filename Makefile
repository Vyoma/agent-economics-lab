.PHONY: demo falsegreen coverage-drift evidence-ablation frontier modularity claude-code claude-code-tree otel-genai public-case benchmark mutation-score sensitivity completion-vs-verdict kimi-judge kimi-doctor kimi-eval reproduce lessons test

demo:
	@python3 -m agent_economics evaluate \
		--traces examples/support_trace.csv \
		--outcomes examples/outcomes.csv \
		--rates examples/rates.json \
		--baseline examples/baseline.json \
		--policy examples/policy.json

modularity:
	PYTHONPATH=. python3 examples/modularity_demo.py

coverage-drift:
	@python3 false_green.py

falsegreen: coverage-drift

benchmark:
	python3 false_green.py \
		--verify research/results/decision-coverage-drift/results.csv \
		--summary-verify research/results/SUMMARY.md \
		--json-verify research/results/decision-coverage-drift/summary.json

evidence-ablation:
	@python3 evidence_ablation.py \
		--verify-dir research/results/evidence-ablation

mutation-score:
	@python3 mutation_score.py \
		--summary-verify research/results/mutation-score/summary.md \
		--json-verify research/results/mutation-score/summary.json

sensitivity:
	@python3 sensitivity_sweep.py \
		--summary-verify research/results/sensitivity/summary.md \
		--json-verify research/results/sensitivity/summary.json

completion-vs-verdict:
	@python3 completion_vs_verdict.py \
		--verify research/results/completion-vs-verdict/report.txt

# Diagnose a Kimi auth failure. Prints key shape and per-region HTTP status,
# never the key. Makes live calls, so it is excluded from `make reproduce`.
kimi-doctor:
	@python3 check_kimi_auth.py

# Live judge eval: scores Kimi labels against the hand-authored eval set.
# Requires MOONSHOT_API_KEY, so it is excluded from `make reproduce`. The scoring
# math and eval-set integrity are covered hermetically by `make test`.
kimi-eval:
	@if [ -z "$$MOONSHOT_API_KEY" ]; then \
		echo "Cannot run the live judge eval: MOONSHOT_API_KEY is not set."; \
		echo "The scoring math and eval set are tested without a key: make test"; \
		exit 1; \
	fi
	@python3 kimi_eval.py \
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
	@python3 -m agent_economics judge \
		--task-results examples/kimi-judge/task_results.csv \
		--rubric examples/kimi-judge/rubric.json \
		--out /tmp/agent-economics-kimi-outcomes.csv

frontier:
	@python3 -m agent_economics frontier \
		examples/compute-frontier/manifest.json \
		--output-dir /tmp/agent-economics-frontier \
		--verify-dir research/results/frontier

claude-code:
	@python3 -m agent_economics convert \
		--from claude-code \
		--in examples/claude-code/session.jsonl \
		--contract examples/claude-code/conversion-contract.json \
		--out /tmp/agent-economics-claude-code.json
	@cmp /tmp/agent-economics-claude-code.json examples/claude-code/bundle.json
	@python3 -m agent_economics evaluate \
		--bundle /tmp/agent-economics-claude-code.json

claude-code-tree:
	@python3 -m agent_economics convert \
		--from claude-code-tree \
		--in examples/claude-code-tree/session.jsonl \
		--contract examples/claude-code-tree/conversion-contract.json \
		--out /tmp/agent-economics-claude-code-tree.json
	@cmp /tmp/agent-economics-claude-code-tree.json examples/claude-code-tree/bundle.json
	@python3 -m agent_economics evaluate \
		--bundle /tmp/agent-economics-claude-code-tree.json \
		--ci

otel-genai:
	@python3 -m agent_economics convert \
		--from otel-genai \
		--in examples/otel-genai/langfuse-otlp.json \
		--contract examples/otel-genai/langfuse-conversion-contract.json \
		--out /tmp/agent-economics-otel-langfuse.json
	@cmp /tmp/agent-economics-otel-langfuse.json examples/otel-genai/langfuse-bundle.json
	@python3 -m agent_economics evaluate \
		--bundle /tmp/agent-economics-otel-langfuse.json \
		--ci
	@python3 -m agent_economics convert \
		--from otel-genai \
		--in examples/otel-genai/arize-openinference-otlp.json \
		--contract examples/otel-genai/arize-openinference-conversion-contract.json \
		--out /tmp/agent-economics-otel-arize.json
	@cmp /tmp/agent-economics-otel-arize.json examples/otel-genai/arize-openinference-bundle.json
	@python3 -m agent_economics evaluate \
		--bundle /tmp/agent-economics-otel-arize.json \
		--ci

public-case:
	@PYTHONPATH=. python3 examples/public-swebench/build_case.py \
		--source examples/public-swebench/runs.json \
		--output-dir /tmp/agent-economics-public-swebench
	@python3 -m agent_economics evaluate \
		--bundle /tmp/agent-economics-public-swebench/arms/candidate-opus.json
	@python3 -m agent_economics frontier \
		/tmp/agent-economics-public-swebench/manifest.json \
		--output-dir /tmp/agent-economics-public-swebench-rendered \
		--verify-dir examples/public-swebench/frontier \
		|| [ $$? -eq 3 ]

reproduce: test modularity lessons benchmark mutation-score sensitivity completion-vs-verdict evidence-ablation frontier claude-code claude-code-tree otel-genai public-case

lessons:
	@for lesson in lessons/*.py; do PYTHONPATH=. python3 "$$lesson"; done

test:
	python3 -m unittest discover -s tests -v
