SHELL := /bin/bash
.PHONY: test lint gate-showcase gate-sample perf

test:
	source env.sh && "$$PY" -m unittest discover -s tests

lint:
	source env.sh && "$$PY" -m layout check lint

gate-showcase:
	source env.sh && "$$PY" -m layout gate --showcase

# The sample episode is the negative fixture. A zero exit from the gate is a failure.
gate-sample:
	source env.sh && "$$PY" -m layout gate --sample; test $$? -ne 0

perf:
	source env.sh && ABIT_LAYOUT_PERF=1 "$$PY" -m unittest tests.layout.test_perf -v
