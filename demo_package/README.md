# MAPLE external demo package

This directory contains optional, local demonstrations of the MAPLE Python
runtime. It is not part of the core wheel or source distribution and its
output is not release, performance, compliance, or production-deployment
evidence.

## Requirements

From the repository root, install the package and development dependencies:

~~~bash
python -m pip install -e ".[dev]"
~~~

The demos target Python 3.8 or newer. Run them from this directory so their
relative assets and result paths resolve correctly.

## Run a demo

~~~bash
python launch_demos.py
python quick_demo.py
python complete_experience.py
~~~

The optional web dashboard is a local demonstration server:

~~~bash
python web_dashboard.py
~~~

The dashboard binds locally and prints its URL when it starts. Do not expose
it to an untrusted network without reviewing the code and adding the host's
authentication, authorization, TLS, and network controls.

## Contents

- launch_demos.py: guided menu for the available demonstrations.
- quick_demo.py: short feature walkthrough.
- complete_experience.py: longer walkthrough.
- maple_demo.py: legacy comprehensive demonstration.
- web_dashboard.py: local visualization helper.
- setup_demo.py: local setup helper.
- validate_package.py: demo-package validation helper.
- INSTALLATION.md and PACKAGE_SUMMARY.md: legacy companion notes.

The demo package shows messaging, resources, security, task management, and
selected autonomy features. It does not prove throughput, scalability,
regulatory compliance, hosted availability, or exactly-once external effects.
Use the core [README](../README.md), [API reference](../docs/api-reference.md),
and [parity ledger](../docs/agent-framework-parity.md) as the authoritative
technical documentation.

## Release boundary

The Python core release is MAPLE 2.0.0. This optional demo directory is not
published by the core release workflow. No registry upload, cloud deployment,
or website publication is implied by running a demo.

## License

The repository license is [AGPL-3.0-only](../LICENSE).
