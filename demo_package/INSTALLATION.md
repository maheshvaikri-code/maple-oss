# Demo package installation

The demo package is optional and is not part of the MAPLE 2.0.0 Python wheel or
source distribution. Use the package README as the current installation and
execution guide.

From the repository root:

~~~bash
python -m pip install -e ".[dev]"
cd demo_package
python launch_demos.py
~~~

Run demos only in a local or operator-controlled environment. They are
demonstrations, not evidence of throughput, scalability, compliance, hosted
availability, or exactly-once effects.

- [Current demo README](README.md)
- [Core MAPLE README](../README.md)
- [Core getting started guide](../docs/getting-started.md)
- [Release checklist](../docs/releases/v2.0.0.md)

No registry, cloud, website, or publication action is performed by installing
or running these demos.

License: [AGPL-3.0-only](../LICENSE).
