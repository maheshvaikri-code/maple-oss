# One-command truth (skills/repo-devops.md): same entry points local and CI.
# No make on Windows? Same thing: python tools/doctrine_verify.py
.PHONY: test lint ruff verify

test:
	python -m unittest discover -s tests

lint:
	python tools/doctrine_lint.py

ruff:
	python -m ruff check tools tests

verify:
	python tools/doctrine_verify.py
