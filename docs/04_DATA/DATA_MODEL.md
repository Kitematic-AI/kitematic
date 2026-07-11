# Kitematic Data Model (Version 3)

**Status:** Approved

## 1. Identity & Compliance

### `tenants`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR(255) | Tenant name |
| plan | VARCHAR(50) | FREE, PRO, TEAM, ENTERPRISE |
| isolation_mode | VARCHAR(50) | SHARED, DEDICATED_DB, PRIVATE_CLUSTER, AIR_GAPPED |
| created_at | TIMESTAMP | |

### `workspaces`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK → tenants |
| name | VARCHAR(255) | Workspace name |

### `users`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK → tenants |
| email | VARCHAR(255) | UNIQUE |
| role | VARCHAR(50) | ADMIN, DEVELOPER, VIEWER |

### `compliance_profiles`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR(100) | SOC2, HIPAA, GDPR |
| framework | VARCHAR(100) | |
| rules | JSONB | Policy constraint mapping |

## 2. The Adapter Ecosystem

### `adapters`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR(255) | Adapter name |
| type | VARCHAR(50) | FRAMEWORK, MODEL, TOOL, MCP, MEMORY |
| provider | VARCHAR(255) | |
| version | VARCHAR(50) | |
| trust_level | VARCHAR(50) | CERTIFIED, COMMUNITY, UNVERIFIED |
| manifest | JSONB | |
| status | VARCHAR(50) | |

### `adapter_capabilities`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| adapter_id | UUID | FK → adapters |
| capability | VARCHAR(255) | e.g. "state_machine", "vision" |

### `adapter_dependencies`
| Column | Type | Description |
|--------|------|-------------|
| adapter_id | UUID | FK → adapters |
| dependency_id | UUID | FK → adapters |
| is_required | BOOLEAN | DEFAULT TRUE |

### `adapter_security_scans`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| adapter_id | UUID | FK → adapters |
| scanner | VARCHAR(100) | |
| scan_status | VARCHAR(50) | |
| vulnerabilities | JSONB | |
| risk_score | DECIMAL | |
| created_at | TIMESTAMP | |

### `mcp_servers`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | Null = Global Hub |
| name | VARCHAR(255) | |
| url | VARCHAR(500) | |
| status | VARCHAR(50) | |

### `tools`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| mcp_server_id | UUID | FK → mcp_servers |
| name | VARCHAR(255) | |
| schema | JSONB | Input parameters |

### `llm_providers`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR(255) | |
| type | VARCHAR(50) | CLOUD, PRIVATE, LOCAL |
| capabilities | JSONB | |
| privacy_level | VARCHAR(50) | |

## 3. Agent Hierarchy

### `agent_templates`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR(255) | |
| description | TEXT | |
| creator_type | VARCHAR(50) | SYSTEM, COMMUNITY, TENANT |
| manifest | JSONB | |
| security_rating | VARCHAR(50) | |

### `agent_instances`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK → tenants |
| template_id | UUID | FK → agent_templates |
| name | VARCHAR(255) | |
| status | VARCHAR(50) | ACTIVE, ARCHIVED |
| deployment_config | JSONB | |

### `agent_manifests`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| agent_id | UUID | FK → agent_instances |
| version | VARCHAR(50) | |
| runtime_framework | VARCHAR(100) | |
| policy_profile_id | UUID | |
| capabilities | JSONB | |
| constraints | JSONB | |
| created_at | TIMESTAMP | |

## 4. Execution & Time Travel

### `executions`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK → tenants |
| instance_id | UUID | FK → agent_instances |
| status | VARCHAR(50) | PENDING, RUNNING, PAUSED, COMPLETED, FAILED |
| started_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |

### `checkpoints`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| execution_id | UUID | FK → executions |
| schema_version | VARCHAR(20) | |
| checkpoint_hash | VARCHAR(255) | UNIQUE — Git-like integrity |
| parent_checkpoint_id | UUID | Self-ref FK — Forking |
| agent_state | JSONB | |
| created_at | TIMESTAMP | |

### `execution_events`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| execution_id | UUID | FK → executions |
| event_type | VARCHAR(100) | |
| payload | JSONB | |
| timestamp | TIMESTAMP | |

## 5. Governance & Human-in-the-Loop

### `policies`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK → tenants |
| name | VARCHAR(255) | |
| target | VARCHAR(255) | e.g. "mcp.database.*" |
| effect | VARCHAR(50) | ALLOW, DENY, REQUIRE_APPROVAL |
| condition | TEXT | CEL Expression |

### `approval_requests`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| execution_id | UUID | FK → executions |
| agent_instance_id | UUID | FK → agent_instances |
| action | VARCHAR(255) | |
| risk_level | VARCHAR(50) | LOW, MEDIUM, HIGH, CRITICAL |
| status | VARCHAR(50) | PENDING, APPROVED, REJECTED |
| approved_by | UUID | FK → users |
| expires_at | TIMESTAMP | |

### `audit_logs`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK → tenants |
| execution_id | UUID | FK → executions |
| action | VARCHAR(255) | |
| resource | VARCHAR(255) | |
| decision | VARCHAR(50) | ALLOWED, DENIED |
| timestamp | TIMESTAMP | |

## 6. Memory

### `memory_items`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK → tenants |
| instance_id | UUID | FK → agent_instances |
| type | VARCHAR(50) | FACT, PREFERENCE, SUMMARY, EXPERIENCE |
| content | TEXT | |
| confidence_score | DECIMAL(3,2) | |
| source | VARCHAR(255) | |
| expires_at | TIMESTAMP | |

## 7. Builder System (Meta-Data)

### `builder_agents`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR(255) | |
| trust_level | VARCHAR(20) | |
| permissions | JSONB | |
| created_at | TIMESTAMP | |

### `architecture_decisions`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| decision_key | VARCHAR(100) | e.g. "ADR-001" |
| title | VARCHAR(255) | |
| status | VARCHAR(50) | ACCEPTED, REJECTED, DEPRECATED |
| context | TEXT | |
| decision | TEXT | |
| consequences | TEXT | |
| created_at | TIMESTAMP | |

### `project_knowledge`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| category | VARCHAR(50) | DECISION, RULE, ARCHITECTURE, BUG, LESSON |
| title | VARCHAR(255) | |
| content | TEXT | |
| source_document | VARCHAR(255) | |
| confidence_score | DECIMAL(3,2) | |
| created_at | TIMESTAMP | |

## 8. Marketplace

### `marketplace_packages`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| package_type | VARCHAR(50) | |
| adapter_id | UUID | FK → adapters |
| publisher | VARCHAR(255) | |
| verification_status | VARCHAR(50) | |
| downloads | BIGINT | |
