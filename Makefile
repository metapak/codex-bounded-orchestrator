
.PHONY: validate test check release

validate:
	python3 scripts/validate.py

test:
	python3 -m unittest discover -s tests -v

check: validate test
	python3 -m py_compile .codex/tools/candidate.py scripts/install.py scripts/validate.py scripts/build_release.py
	sh -n scripts/install.sh
	sh -n setup.command

release: check
	python3 scripts/build_release.py --output-dir dist
