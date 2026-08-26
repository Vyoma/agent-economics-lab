PYTHON ?= python3

.PHONY: demo falsegreen coverage-drift evidence-ablation frontier modularity \
	claude-code claude-code-tree otel-genai public-case benchmark reproduce \
	lessons test lint coverage check-python mutation real-trace sensitivity

# The package declares requires-python >= 3.10, but `make` cannot enforce that the
# way pip does. Without this guard a contributor whose default python3 is older
# gets obscure syntax and zip(strict=) errors instead of a usable message.
check-python:
	@$(PYTHON) -c 'import sys; sys.version_info >= (3, 10) or sys.exit("agent-economics-lab requires Python 3.10 or newer; %d.%d found. Retry with: make PYTHON=python3.12 <target>" % sys.version_info[:2])'

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

mutation:
	@$(PYTHON) mutation_score.py

real-trace:
	@$(PYTHON) real_trace_verdict.py

sensitivity:
	@$(PYTHON) sensitivity_sweep.py

lint:
	@$(PYTHON) -m ruff check .

# The CHANGELOG cites coverage figures; this is what reproduces them.
coverage:
	@$(PYTHON) -m coverage run --source=agent_economics -m unittest discover -s tests
	@$(PYTHON) -m coverage report

evidence-ablation:
	@$(PYTHON) evidence_ablation.py \
		--verify-dir research/results/evidence-ablation

frontier:
	@$(PYTHON) -m agent_economics frontier \
		examples/compute-frontier/manifest.json \
		--output-dir /tmp/agent-economics-frontier \
		--verify-dir research/results/frontier

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

reproduce: check-python test modularity lessons benchmark mutation real-trace \
	sensitivity evidence-ablation frontier claude-code claude-code-tree otel-genai \
	public-case

lessons:
# Without set -e the loop reports only the LAST lesson's exit status, so a
# failing lesson 00-03 is masked whenever 04 succeeds. A check that can
# silently not run is the exact failure this repository exists to refuse.
	@set -e; for lesson in lessons/*.py; do PYTHONPATH=. $(PYTHON) "$$lesson"; done

test: check-python
	$(PYTHON) -m unittest discover -s tests -v
