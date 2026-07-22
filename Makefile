.PHONY: demo frontier modularity benchmark reproduce lessons test

demo:
	@python3 -m agent_economics evaluate \
		--traces examples/support_trace.csv \
		--outcomes examples/outcomes.csv \
		--rates examples/rates.json \
		--baseline examples/baseline.json \
		--policy examples/policy.json

modularity:
	PYTHONPATH=. python3 examples/modularity_demo.py

benchmark:
	PYTHONPATH=. python3 research/false_green_benchmark.py \
		--verify research/results/false_green_results.csv

frontier:
	@python3 -m agent_economics frontier \
		examples/compute-frontier/manifest.json \
		--output-dir /tmp/agent-economics-frontier \
		--verify-dir research/results/frontier

reproduce: test modularity lessons benchmark frontier

lessons:
	@for lesson in lessons/*.py; do PYTHONPATH=. python3 "$$lesson"; done

test:
	python3 -m unittest discover -s tests -v
