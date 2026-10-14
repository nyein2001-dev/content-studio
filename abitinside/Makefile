SHELL := /bin/bash
.PHONY: test lint validate qa gate-showcase perf

test:
	source env.sh && "$$PY" -m pytest tests -q

lint:
	source env.sh && "$$PY" -m layout check lint

validate:
	source env.sh && "$$PY" -m layout validate

qa:
	source env.sh && "$$PY" -m layout qa --video examples/layout_showcase/video.yaml

gate-showcase:
	source env.sh && "$$PY" -m layout gate --showcase

perf:
	source env.sh && ABIT_LAYOUT_PERF=1 "$$PY" -m unittest tests.gates.test_perf -v
