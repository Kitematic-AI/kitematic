# Technical Architecture Document

## Kitematic — High-Level Architecture

**Version:** 1.0

## Architecture Philosophy

Kitematic follows a **6-Plane Architecture**, separating concerns into independent layers:

```
                 KITEMATIC PLATFORM
================================================
              Management Plane
================================================
              Control Plane
================================================
              Runtime Plane
================================================
           Infrastructure Plane
================================================
             Ecosystem Plane
================================================
              Trust Plane
================================================
```

### 1. Management Plane
- Billing, metering, licensing
- Tenant lifecycle management
- Updates and marketplace registry
- Compliance and contracts management

### 2. Control Plane (The Brain)
- **Agent Registry Service** — Agent definitions, versioning, templates, compatibility
- **Agent Lifecycle Manager** — Start, stop, pause, resume, scale, upgrade
- **Orchestrator Engine** — State machine, step coordination, checkpoint triggers
- **Policy Engine** — Authorization evaluation, compliance enforcement
- **MCP Gateway** — Tool discovery, capability negotiation, permission enforcement
- **Model Gateway** — LLM routing, cost control, fallback, privacy routing
- **Memory Service** — Short-term, long-term, RAG memory management
- **Checkpoint Service** — Snapshot, restore, replay, fork
- **Human Approval Service** — HITL (Human-in-the-Loop) request management

### 3. Runtime Plane (The Execution)
- **Agent Workers** — Isolated containers running Agent frameworks (LangGraph, CrewAI, Custom)
- **Tool Workers** — Sandboxed environments for tool execution
- **Sandbox Workers** — Secure code execution, browser automation

### 4. Infrastructure Plane
- **Kubernetes / Docker / Bare Metal** — Abstracted infrastructure layer
- **GPU Scheduling** — Model-specific compute allocation
- **Network Policies** — Zero-trust network segmentation
- **Storage** — PostgreSQL, Vector DB, Redis, Object Storage

### 5. Ecosystem Plane
- **Marketplace** — Public and private hubs for adapters, templates, models
- **SDK** — Adapter Builder, Agent Creator, Enterprise Control SDKs
- **CLI** — `kitematic` command-line tool
- **KAS** — Kitematic Agent Specification (packaging standard)

### 6. Trust Plane
- **Security Scanning** — Adapter vulnerability analysis
- **Signature Verification** — Cryptographic trust for publishers
- **Compliance Framework** — SOC2, HIPAA, ISO27001 mapping
- **Audit System** — Immutable action logging

## Communication Protocol

| Interface | Protocol | Use Case |
|-----------|----------|----------|
| External API | REST/HTTPS | Dashboard, CLI, User actions |
| Internal Services | gRPC | Control Plane ↔ Workers |
| Events | Redis Streams (MVP) → Kafka (Enterprise) | Async event distribution |
| Tool Execution | MCP Protocol | Agent ↔ MCP Gateway ↔ Tools |

## Deployment Topologies

| Tier | Isolation Mode | Suitable For |
|------|---------------|--------------|
| 1 | Shared Kubernetes Namespace | Free, Developer, Indie |
| 2 | Dedicated Namespace + RBAC | Teams, Pro, Business |
| 3 | vCluster / Dedicated Cluster | Enterprise |
| 4 | Air-Gapped / Private Cloud | Government, Defense, Banking |
