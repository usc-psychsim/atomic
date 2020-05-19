# simple makefile to simplify repetitive build env management tasks under posix
# this is adopted from the sklearn Makefile

# caution: testing won't work on windows

PYTHON ?= python

.PHONY: clean develop test

# clean:
	# $(PYTHON) setup.py clean
	# rm -rf dist
	# rm -rf build

doc-requirements:
	$(PYTHON) -m pip install -r cicd_utils/doc_reqs.txt

env-requirements:
	$(PYTHON) -m pip install -e "git+https://github.com/usc-psychsim/atomic.git#egg=psychsim"

# test-unit: test-requirements
	# $(PYTHON) -m pytest -v --durations=20 --cov-config .coveragerc --cov gh_doc_automation
