# MAPLE n8n integration guide

This guide documents the local companion package in n8n-integration. It
contains TypeScript nodes, credentials, and sample workflows for connecting
n8n to a host that exposes MAPLE operations.

The package is separate from the Python package. It is not included in the
MAPLE 2.0.0 wheel or source distribution, and no npm publication is claimed.

## Requirements

- Node.js 16 or newer.
- npm 8 or newer.
- An n8n instance for installing and exercising the built nodes.
- A MAPLE host and credentials configured by the operator.

## Build and test

From this directory:

~~~bash
npm install
npm run validate
~~~

The individual commands are:

~~~bash
npm run lint
npm test
npm run build
~~~

The build emits the files referenced by package.json. The package test suite
is local integration coverage; it does not validate a hosted MAPLE deployment.

## Nodes

The package declares three nodes:

| Node | Purpose |
| --- | --- |
| MAPLE Agent | Submit an operation to a MAPLE endpoint. |
| MAPLE Coordinator | Coordinate workflow-level operations. |
| MAPLE Resource Manager | Expose resource-management actions. |

Implementation and credential boundaries:

- nodes/MAPLEAgent/MAPLEAgent.node.ts
- nodes/MAPLECoordinator/MAPLECoordinator.node.ts
- nodes/MAPLEResourceManager/MAPLEResourceManager.node.ts
- credentials/MAPLEApi.credentials.ts

After a successful build, install the package into the operator's n8n
environment according to n8n's community-node procedure. The repository does
not deploy n8n or create a hosted MAPLE service.

## Sample workflows

- [AI research assistant](../workflows/ai-research-assistant.json)
- [Content creation pipeline](../workflows/content-creation-pipeline.json)
- [Customer service bot](../workflows/customer-service-bot.json)

Import these files only into a test or operator-controlled n8n instance.
Review endpoints, credential fields, payloads, and data retention before
connecting real systems.

## Local launch helpers

The package contains local demo helpers:

~~~bash
npm run demo
npm run demo:quick
npm run demo:full
npm run launch
~~~

Commands named launch:production, deploy, publish:npm, and publish:github are
operational commands. They require a separate human review and authorization.
They are not part of the Python release workflow and were not run for MAPLE
2.0.0.

## Security and release boundaries

The n8n package is an integration surface, not an authorization or tenancy
boundary. The host remains responsible for authentication, authorization,
TLS, endpoint allowlisting, secret storage, auditing, rate limits, and
network exposure.

Example configuration and test tokens are placeholders. Do not copy them into
production. Do not report the demo performance text in legacy launch files as
a measured benchmark.

For the core runtime's capability and limitation matrix, see the [root
README](../../README.md), [API reference](../../docs/api-reference.md), and
[agent-framework parity ledger](../../docs/agent-framework-parity.md).

## Further reading

- [Integration README](../README.md)
- [Launch guide](../LAUNCH-GUIDE.md)
- [Core best practices](../../docs/best-practices.md)
- [External-phase plan](../../docs/plans/maple-publication-website-cloud-registry.md)
- [2.0.0 release checklist](../../docs/releases/v2.0.0.md)

## License

The integration is covered by [AGPL-3.0-only](../../LICENSE).
