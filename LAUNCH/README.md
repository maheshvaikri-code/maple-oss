# MAPLE launch helpers

This directory contains local demo and launch-control helpers. It is not a
release publisher and is not the source of truth for product claims.

## Available local checks

Run from this directory:

~~~bash
python quick_test.py
python test_demo.py
python final_test.py
~~~

The scripts may inspect or start local demo components. Review any command
before exposing a service or using it with real credentials.

## Publication boundary

LAUNCH_PACKAGE.md contains historical launch-copy material and placeholders.
It is retained as a draft reference, not as an approved announcement. It must
not be treated as evidence for benchmarks, production deployments, customer
stories, compliance, or release authorization.

For current technical capability and release status, use the [root
README](../README.md), [changelog](../CHANGELOG.md), and [2.0.0 release
checklist](../docs/releases/v2.0.0.md). Website, cloud, registry, tag, and
external publication actions remain in standing under the
[external-phase plan](../docs/plans/maple-publication-website-cloud-registry.md).
