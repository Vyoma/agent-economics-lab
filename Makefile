.PHONY: demo falsegreen coverage-drift evidence-ablation frontier modularity benchmark reproduce lessons test

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

reproduce: test modularity lessons benchmark evidence-ablation frontier

lessons:
	@for lesson in lessons/*.py; do PYTHONPATH=. python3 "$$lesson"; done

test:
	python3 -m unittest discover -s tests -v
