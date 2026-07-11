# Ecosystem & SDK Architecture (Version 1.0)

## Kitematic Developer Platform

```
Kitematic Developer Platform
├── SDKs (Python, TypeScript)
├── CLI (kitematic)
├── Local Runtime (Kitematic Local)
├── Testing Framework
├── Simulator
├── Certification Tools
└── Documentation
```

## SDKs

### Adapter Builder SDK
- Decorators to convert functions into KAS-compatible tools.
- Automatic MCP Gateway registration.
- Automatic `manifest.json` generation.

### Agent Creator SDK
- `KitematicClient` for local development (mocks Control Plane).
- Handles YIELD and Checkpoint operations transparently.

### Enterprise Control SDK
- Policy-as-Code management.
- Tenant and approval workflow management via Management Plane APIs.

## CLI

```bash
kitematic init          # Initialize a new Agent project
kitematic test          # Run tests locally
kitematic scan          # Security scan the adapter
kitematic push          # Push to Marketplace / Private Hub
kitematic run           # Run locally
kitematic deploy        # Deploy to Kitematic Cloud/Enterprise
```

## Kitematic Agent Specification (KAS)

KAS is the packaging standard for Agents and Adapters:

```
my-sales-agent.kas/
├── manifest.json       (Identity, Version, Dependencies)
├── policy.yaml         (Required permissions, trust requirements)
├── runtime/            (Actual LangGraph/Python code or Adapter binary)
├── prompts/            (System prompts and instructions)
└── metadata/
    └── signature.pem   (Cryptographic signature for Trust Plane)
```

### KAS Versioning

```yaml
kas_version: 1.0
runtime:
  min_version: 1.2
security:
  required_trust_level: certified
dependencies:
  - langgraph >= 0.3
compatibility:
  kitematic:
    min: 1.0
```

## Marketplace

### Hub Types

| Hub | Description |
|-----|-------------|
| **Public Kitematic Hub** | Global marketplace — templates, adapters, models |
| **Enterprise Hub** | Organization-internal curated marketplace |
| **Private Hub** | Air-gapped, fully offline marketplace |

### Hub Federation

Enterprises can federate hubs:
```
Kitematic Global Hub
    |
    ├── Bank Hub (signed, T4 only)
    └── Government Hub (air-gapped, T4 only)
```

### Publishing Pipeline

```
Developer → KAS Validator → Trust Scanner → Compatibility Engine → Published
```

### Revenue Models

- Free (open source)
- Paid (commercial adapters)
- Enterprise License (SAP, Oracle, Banking Adapters)
- Usage Revenue (per-execution fee sharing)

## Trust Levels

| Level | Label | Description |
|-------|-------|-------------|
| T0 | Unknown | Unverified — restricted by default |
| T1 | Community Verified | Passed basic community review |
| T2 | Kitematic Tested | Passed automated Kitematic certification |
| T3 | Enterprise Approved | Approved by enterprise security team |
| T4 | Critical Infrastructure Certified | Government-grade certification |

## Agent Evaluation Framework

Before publishing, every Agent is scored:

```
Security:   95/100
Accuracy:   88/100
Cost:       92/100
Reliability: 96/100
Overall:    A+
```

## Local Development Environment

Kitematic Local includes:
- Local Control Plane (lightweight)
- Local MCP Gateway
- Local Memory Service (in-memory)
- Mock Policy Engine
- Test Sandbox

Developers build and test locally, then `kitematic push` to deploy.
