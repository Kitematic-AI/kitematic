# Kitematic Testing Strategy

Testing pyramid, fixture architecture, mock strategy, and acceptance criteria for each service.

---

## 1. Testing Pyramid

```
         ╱╲
        ╱  ╲
       ╱ E2E╲           Few: Critical user journeys
      ╱──────╲
     ╱Integration╲      Some: Service boundaries, API contracts
    ╱────────────╲
   ╱   Unit Tests  ╲    Many: Business logic, state machines, policy evaluation
  ╱────────────────╲
```

### Distribution Targets
| Level | Coverage Target | Execution Time | CI Trigger |
|-------|----------------|---------------|------------|
| Unit | 90%+ | < 1 min | Every push |
| Integration | 70%+ | < 5 min | Every PR |
| E2E | 20% (critical paths) | < 15 min | Every merge to main |

---

## 2. Unit Testing Strategy

### What to Unit Test
- **Policy Engine:** Each policy rule type (ALLOW, DENY, REQUIRE_APPROVAL), CEL condition evaluation, priority sorting, edge cases (empty policies, overlapping rules)
- **Orchestrator:** State transitions (PENDING→RUNNING→PAUSED→RESUMED), checkpoint trigger logic, budget cap enforcement
- **Agent Registry:** Manifest validation, compatibility checking, version lifecycle (create, update, rollback)
- **Model Gateway:** Routing algorithm (privacy filter, cost filter, capability matching), fallback logic

### Test Structure (pytest)
```
services/orchestrator/tests/
├── unit/
│   ├── test_state_machine.py
│   ├── test_checkpoint_triggers.py
│   └── test_budget_enforcement.py
├── conftest.py         # Shared fixtures
└── helpers/
    └── factories.py    # Test data factories
```

### Fixture Architecture
```python
# conftest.py — Shared fixtures
@pytest.fixture
def mock_policy_engine():
    """Returns a MockPolicyEngine that allows everything."""
    return MockPolicyEngine(allowed=True)

@pytest.fixture
def sample_agent_manifest():
    return AgentManifest(
        agent_id="test-agent-1",
        framework="langgraph",
        allowed_tools=["salesforce.read"],
        max_tokens=50000
    )
```

---

## 3. Integration Testing Strategy

### What to Integration Test
- **Service Boundaries:** Does the API Gateway correctly route to the Agent Registry?
- **gRPC Contracts:** Does the Orchestrator correctly call the Policy Engine and get back a valid response?
- **Database Interactions:** Does the Agent Registry correctly store and retrieve agents with RLS?
- **Event Emission:** Does the Checkpoint Service emit `checkpoint.created` after saving?

### Test Environment
- One shared PostgreSQL test database (dropped and recreated per test run)
- One shared Redis instance (flushed per test run)
- Mock MCP Servers (local Flask/FastAPI apps that return canned responses)
- All external APIs (OpenAI, GitHub, etc.) are mocked — no real API calls in integration tests

### Test Structure
```
services/policy-engine/tests/
├── integration/
│   ├── test_evaluate_with_db.py
│   ├── test_audit_log_immutability.py
│   └── test_policy_crud.py
```

---

## 4. E2E Testing Strategy

### Critical Journeys to Test
1. **Happy Path:** Create template → Create instance → Start execution → Agent completes goal
2. **Tool Call:** Start execution → Agent requests tool → Tool executed via MCP → Agent receives result → Completes
3. **Policy Denial:** Start execution → Agent attempts blocked action → Execution paused → User notified
4. **Human Approval:** Start execution → Agent requires approval → ApprovalService creates request → Approver approves → Execution resumes → Completes
5. **Checkpoint Fork:** Start execution → Save checkpoint → Fork from checkpoint with new instruction → New execution follows fork path
6. **Budget Exceeded:** Start execution with $0.01 budget → Agent uses tokens → Budget exceeded → Execution paused

### E2E Test Requirements
- All services deployed (can be Docker Compose locally)
- Real PostgreSQL, Redis (no mocks)
- Mock MCP Server for tool execution
- Test user with known credentials

---

## 5. Mock Strategy

| Service/External | Mock Approach | When to Use |
|-----------------|---------------|-------------|
| Policy Engine | `MockPolicyEngine(allowed=True)` | Unit tests for other services |
| MCP Server | Local Flask app with canned endpoints | Integration tests |
| OpenAI / LLM | `responses` library (HTTP mock) | Tests that trigger model calls |
| Secret Manager | In-memory Vault mock | Tests that request secrets |
| Agent Worker | `MockWorker` that returns YIELD_COMPLETED | Orchestrator tests |

### Mock Policy Engine Implementation
```python
class MockPolicyEngine(PolicyEngineServicer):
    def __init__(self, allowed=True, decision="ALLOW"):
        self.allowed = allowed
        self.decision = decision
        self.evaluations = []  # Record all evaluations for assertions

    async def Evaluate(self, request, context):
        self.evaluations.append(request)
        return PolicyDecision(
            decision=self.decision,
            matched_rule="mock-rule",
            reason="Mock policy engine"
        )
```

---

## 6. Test Data Management

### Factories (using factory_boy)
```python
import factory

class AgentTemplateFactory(factory.Factory):
    class Meta:
        model = AgentTemplate

    id = factory.Faker("uuid4")
    name = factory.Sequence(lambda n: f"template-{n}")
    framework = "langgraph"
    manifest = {
        "runtime_contract_version": "1.0",
        "required_adapters": ["salesforce-mcp"],
        "max_tokens": 50000
    }
```

### Database Fixtures
- Seeds for base test data (admin user, workspace, basic policies)
- Loaded once per test session, not per test (to speed up integration tests)
- Tests that modify data use explicit inserts, not shared state

---

## 7. CI/CD Pipeline (Phase 6+)

```yaml
# .github/workflows/test.yml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - run: pytest services/*/tests/unit/ -v --cov

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: POSTGRES_PASSWORD=test
      redis:
        image: redis:7
    steps:
      - run: pytest services/*/tests/integration/ -v

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    steps:
      - run: docker compose -f docker-compose.test.yml up -d
      - run: pytest tests/e2e/ -v
```

---

## 8. Acceptance Criteria Checklist

Each service must pass these checks before being considered complete:

| Check | Description |
|-------|-------------|
| ✅ Unit tests | >90% line coverage, all state machine paths tested |
| ✅ Integration tests | gRPC contract tests pass |
| ✅ Database migrations | Alembic upgrade + downgrade works |
| ✅ RLS isolation | Tenant A cannot see Tenant B's data |
| ✅ Error handling | All error categories produce correct responses |
| ✅ Audit logging | Every mutating operation writes to audit_logs |
| ✅ Security scan | No hardcoded secrets, no SQL injection vectors |
