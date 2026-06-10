.PHONY: test test-unit test-integration test-all

test: test-unit

test-unit:
	pytest

test-integration:
	pytest \
	  -o addopts="" \
	  -m integration \
	  -q --strict-markers --strict-config \
	  --junitxml=reports/junit-integration.xml \
	  --cov=app --cov-branch \
	  --cov-report=term-missing \
	  --cov-report=xml:reports/coverage-integration.xml

test-all:
	$(MAKE) test-unit
	$(MAKE) test-integration
