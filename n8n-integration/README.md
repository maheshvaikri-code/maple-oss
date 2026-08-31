# MAPLE n8n integration

This directory is a companion n8n community-node project. It provides
TypeScript nodes and sample workflow JSON for connecting n8n to a MAPLE host.
It is separate from the Python package and is not included in the MAPLE 2.0.0
wheel or source distribution.

- Status: local integration source; npm publication has not been performed.
- Runtime: Node.js 16 or newer and npm 8 or newer.
- Package metadata: independently maintained in package.json.

## Nodes

The package declares three n8n nodes:

- MAPLE Agent: submit work to a MAPLE endpoint.
- MAPLE Coordinator: coordinate workflow-level operations.
- MAPLE Resource Manager: expose resource-management actions.

The exact node behavior and credential fields are defined in:

- nodes/MAPLEAgent/MAPLEAgent.node.ts
- nodes/MAPLECoordinator/MAPLECoordinator.node.ts
- nodes/MAPLEResourceManager/MAPLEResourceManager.node.ts
- credentials/MAPLEApi.credentials.ts

## Local development

~~~bash
cd n8n-integration
npm install
npm run validate
~~~

The build and test scripts are also available separately:

~~~bash
npm run build
npm test
npm run lint
~~~

The package includes local demo and launch helpers. Treat commands named
launch:production, deploy, and publish:* as operational commands that require
a separate human review and authorization; they are not run by the MAPLE Python
release workflow.

## Sample workflows

- [AI research assistant](workflows/ai-research-assistant.json)
- [Content creation pipeline](workflows/content-creation-pipeline.json)
- [Customer service bot](workflows/customer-service-bot.json)

These JSON files are examples. They do not provide a hosted MAPLE service,
credential management, or a security boundary by themselves.

## Documentation

- [Detailed integration guide](docs/README-DETAILED.md)
- [Launch guide](LAUNCH-GUIDE.md)
- [Core MAPLE README](../README.md)
- [Core API reference](../docs/api-reference.md)
- [Core best practices](../docs/best-practices.md)
- [External-phase plan](../docs/plans/maple-publication-website-cloud-registry.md)

The core runtime's authentication, authorization, TLS, tenancy, auditing, and
network exposure remain host responsibilities. Placeholder values in example
configuration and tests are not production credentials.

## Release boundary

The core release is MAPLE 2.0.0. The n8n companion package has its own npm
metadata and release process. No npm registry write, GitHub release, cloud
action, or website deployment is claimed by this repository state.

## License

The integration is covered by [AGPL-3.0-only](../LICENSE).
