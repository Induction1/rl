PYTHON ?= python3
OUT    ?= figures

.PHONY: bundle docs sites spec corpus test box run grade figures clean check-test-set

bundle: docs spec

docs:
	node harness/make_docs.js
	$(PYTHON) harness/rng_table.py

sites: check-test-set
	node harness/rng_sites.js "$(POKEVAL_TEST_SET)" 1000 > rng_sites.json.tmp && mv rng_sites.json.tmp rng_sites.json

spec: check-test-set
	$(PYTHON) -m pytest -q tests/test_choice_rules.py
	$(PYTHON) harness/grammar.py "$(POKEVAL_TEST_SET)"

corpus:
	node harness/mint.js --n 1000 --cap 100 --out ps_test.jsonl

test:
	$(PYTHON) -m pytest -q tests

box:
	cd sandbox && docker compose down -v && docker compose up -d --build

run:
	runner/run.sh $(NAME) $(ARGS)

grade:
	sandbox/grade_container.sh $(NAME)

figures:
	$(PYTHON) analysis/plots.py $(OUT)

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache

check-test-set:
	@test -n "$(POKEVAL_TEST_SET)" || { echo "set POKEVAL_TEST_SET to the path of the test set"; exit 1; }
