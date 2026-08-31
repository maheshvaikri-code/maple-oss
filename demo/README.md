# MAPLE demonstrations

This directory contains focused, local demonstrations for adapter and
integration behavior. It is separate from the core package release artifact.

## Contents

- adapters_demo/: adapter-focused examples and comparison helpers.
- autogen/: an AutoGen interoperability example.
- gpt_oss/: an example using a GPT-compatible host setup.

Run demonstrations from the repository root after installing the package:

~~~bash
python -m pip install -e ".[dev,llm,adapters]"
python demo/adapters_demo/performance_comparison_demo.py
~~~

Examples may require optional provider SDKs or host configuration. They do not
claim benchmark equivalence, hosted availability, or production readiness.
See the [root README](../README.md) and [API reference](../docs/api-reference.md)
for authoritative behavior and limitations.
