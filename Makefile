.PHONY: demo falsegreen coverage-drift evidence-ablation frontier modularity claude-code otel-genai public-case benchmark reproduce lessons test

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

reproduce: test modularity lessons benchmark evidence-ablation frontier claude-code otel-genai public-case

lessons:
	@for lesson in lessons/*.py; do PYTHONPATH=. python3 "$$lesson"; done

test:
	python3 -m unittest discover -s tests -v
