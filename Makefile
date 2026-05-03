.PHONY: install test json-check hash-check public-index reproduce ci clean

PYTHON ?= python3
RUN_DIR ?= runs/local-deep-hardening-v3

install:
	$(PYTHON) -m pip install -r requirements-lock.txt
	$(PYTHON) -m pip install --no-deps -e .

test:
	$(PYTHON) -m unittest discover -s tests -v

json-check:
	$(PYTHON) -m json.tool reports/node-alpha/report-index.json >/dev/null
	$(PYTHON) -m json.tool reports/node-alpha/deep-hardening-v3-20260502/deep-hardening-v3-report.json >/dev/null
	$(PYTHON) -m json.tool reports/node-alpha/deep-hardening-v3-20260502/virtual-sparameter-acceptance-report.json >/dev/null
	$(PYTHON) -m json.tool reports/node-alpha/qc-path/sparameter-audit.json >/dev/null
	$(PYTHON) -m json.tool docs/evidence-ledger.json >/dev/null

hash-check:
	@if command -v sha256sum >/dev/null 2>&1; then \
		sha256sum -c ARTIFACTS.sha256; \
	else \
		shasum -a 256 -c ARTIFACTS.sha256; \
	fi

public-index:
	$(PYTHON) tools/update_public_index.py

reproduce:
	rm -rf $(RUN_DIR)
	$(PYTHON) -m oqp.cli performance-upgrade hardware/Heralded_Reset_Mesh_Blueprint.yaml \
		--artifact-root reports/node-alpha \
		--out-dir $(RUN_DIR) \
		--focused-max-runs 768
	$(PYTHON) -m json.tool $(RUN_DIR)/deep-hardening-v3-report.json >/dev/null

ci: test json-check hash-check reproduce

clean:
	rm -rf runs build dist *.egg-info oqp/__pycache__ tests/__pycache__ .pytest_cache .mypy_cache .ruff_cache
