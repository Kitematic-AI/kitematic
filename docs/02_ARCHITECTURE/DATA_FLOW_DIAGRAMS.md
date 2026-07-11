# Kitematic Data Flow Diagrams

Sequence diagrams for 5 core execution flows.

---

## 1. Agent Creation Flow

```
User / Dashboard                API Gateway              Agent Registry          Lifecycle Manager
     │                              │                        │                       │
     │  POST /v1/agents             │                        │                       │
     │  { template_id, config }     │                        │                       │
     │─────────────────────────────►│                        │                       │
     │                              │  Validate JWT          │                       │
     │                              │  Extract tenant_id     │                       │
     │                              │                        │                       │
     │                              │  CreateAgent(request)  │                       │
     │                              │───────────────────────►│                       │
     │                              │                        │                       │
     │                              │                        │  Validate manifest     │
     │                              │                        │  Check compat          │
     │                              │                        │  Store agent_instance  │
     │                              │                        │                       │
     │                              │  AgentCreated{id}      │                       │
     │                              │◄───────────────────────│                       │
     │                              │                        │                       │
     │  { agent_id, status: DRAFT } │                        │                       │
     │◄─────────────────────────────│                        │                       │
     │                              │                        │                       │
```

---

## 2. Step Execution Flow (Normal Path)

```
Orchestrator            Policy Engine           Worker              MCP Gateway        Checkpoint
     │                       │                    │                    │                  │
     │  ExecuteStep          │                    │                    │                  │
     │  { state, goal }      │                    │                    │                  │
     │──────────────────────►│                    │                    │                  │
     │                       │                    │                    │                  │
     │                       │  Evaluate(agent,   │                    │                  │
     │                       │  action, resource) │                    │                  │
     │                       │───────────────────►│                    │                  │
     │                       │                    │                    │                  │
     │                       │  ALLOW             │                    │                  │
     │                       │◄───────────────────│                    │                  │
     │                       │                    │                    │                  │
     │  SaveCheckpoint       │                    │                    │                  │
     │  (BEFORE_STEP)        │                    │                    │                  │
     │─────────────────────────────────────────────────────────────────►│                  │
     │                       │                    │                    │                  │
     │                       │                    │  ExecuteStep       │                  │
     │                       │                    │  { state }         │                  │
     │                       │                    │───────────────────►│                  │
     │                       │                    │                    │                  │
     │                       │                    │  Run LangGraph     │                  │
     │                       │                    │  step()            │                  │
     │                       │                    │◄───────────────────│                  │
     │                       │                    │                    │                  │
     │                       │                    │  COMPLETED         │                  │
     │                       │                    │  { result }        │                  │
     │                       │                    │───────────────────►│                  │
     │                       │                    │                    │                  │
     │  SaveCheckpoint       │                    │                    │                  │
     │  (AFTER_STEP)         │                    │                    │                  │
     │─────────────────────────────────────────────────────────────────►│                  │
     │                       │                    │                    │                  │
     │  UpdateBudget         │                    │                    │                  │
     │  CheckLoops           │                    │                    │                  │
     │                       │                    │                    │                  │
     │  Return result        │                    │                    │                  │
     │──────────────────────►│                    │                    │                  │
     │                       │                    │                    │                  │
```

---

## 3. Tool Call Flow (Agent requests a tool)

```
Agent Worker              Orchestrator           Policy Engine         MCP Gateway         External Tool
     │                        │                      │                     │                   │
     │  YIELD:TOOL_REQUEST    │                      │                     │                   │
     │  { mcp_server, tool,   │                      │                     │                   │
     │    params }            │                      │                     │                   │
     │───────────────────────►│                      │                     │                   │
     │                        │                      │                     │                   │
     │                        │  Evaluate(agent,     │                     │                   │
     │                        │  "mcp.github.read",  │                     │                   │
     │                        │  resource)           │                     │                   │
     │                        │─────────────────────►│                     │                   │
     │                        │                      │                     │                   │
     │                        │  ALLOW               │                     │                   │
     │                        │◄─────────────────────│                     │                   │
     │                        │                      │                     │                   │
     │                        │  ExecuteTool         │                     │                   │
     │                        │  { tool, params }    │                     │                   │
     │                        │──────────────────────────────────────────►│                   │
     │                        │                      │                     │                   │
     │                        │                      │                     │  HTTP POST /tool   │
     │                        │                      │                     │──────────────────►│
     │                        │                      │                     │                   │
     │                        │                      │                     │  { result }       │
     │                        │                      │                     │◄──────────────────│
     │                        │                      │                     │                   │
     │                        │  ToolResult          │                     │                   │
     │                        │  { result }          │                     │                   │
     │                        │◄──────────────────────────────────────────│                   │
     │                        │                      │                     │                   │
     │  Feed result to        │                      │                     │                   │
     │  LangGraph step()      │                      │                     │                   │
     │◄───────────────────────│                      │                     │                   │
     │                        │                      │                     │                   │
```

---

## 4. Human-in-the-Loop (Approval Flow)

```
Agent Worker            Orchestrator          Policy Engine        Approval Service          Approver
     │                       │                     │                     │                     │
     │  YIELD:TOOL_REQUEST   │                     │                     │                     │
     │  { send_mass_email }  │                     │                     │                     │
     │──────────────────────►│                     │                     │                     │
     │                       │                     │                     │                     │
     │                       │  Evaluate(...)      │                     │                     │
     │                       │────────────────────►│                     │                     │
     │                       │                     │                     │                     │
     │                       │  REQUIRE_APPROVAL   │                     │                     │
     │                       │◄────────────────────│                     │                     │
     │                       │                     │                     │                     │
     │                       │  RequestApproval    │                     │                     │
     │                       │  { action, risk:    │                     │                     │
     │                       │    HIGH, payload }  │                     │                     │
     │                       │─────────────────────────────────────────►│                     │
     │                       │                     │                     │                     │
     │  ExecutePause         │                     │                     │                     │
     │  SaveCheckpoint       │                     │                     │  Notify approver    │
     │                       │                     │                     │────────────────────►│
     │                       │                     │                     │                     │
     │                       │                     │                     │  Approve(review)    │
     │                       │                     │                     │◄────────────────────│
     │                       │                     │                     │                     │
     │                       │  ApprovalApproved   │                     │                     │
     │                       │◄─────────────────────────────────────────│                     │
     │                       │                     │                     │                     │
     │                       │  ResumeExecution    │                     │                     │
     │                       │  RestoreCheckpoint  │                     │                     │
     │                       │  Re-evaluate        │                     │                     │
     │──────────────────────►│                     │                     │                     │
     │                       │                     │                     │                     │
```

---

## 5. Checkpoint Fork (Time Travel / Debugging)

```
User / Dashboard            API Gateway            Checkpoint Service       Orchestrator          Worker
     │                          │                        │                     │                    │
     │  POST /checkpoints/{id}  │                        │                     │                    │
     │  /fork                   │                        │                     │                    │
     │  { new_instruction }     │                        │                     │                    │
     │─────────────────────────►│                        │                     │                    │
     │                          │                        │                     │                    │
     │                          │  ForkCheckpoint(cp_id, │                     │                    │
     │                          │  new_instruction)      │                     │                    │
     │                          │───────────────────────►│                     │                    │
     │                          │                        │                     │                    │
     │                          │                        │  Load checkpoint    │                    │
     │                          │                        │  Load agent_state   │                    │
     │                          │                        │  Create new exec    │                    │
     │                          │                        │  with parent = cp   │                    │
     │                          │                        │                     │                    │
     │                          │                        │  StartForkedExec    │                    │
     │                          │                        │───────────────────────────────────►      │
     │                          │                        │                     │                    │
     │                          │                        │                     │  Execute with      │
     │                          │                        │                     │  new_instruction   │
     │                          │                        │                     │──────────────────►│
     │                          │                        │                     │                    │
     │  { new_execution_id }    │                        │                     │                    │
     │◄─────────────────────────│                        │                     │                    │
     │                          │                        │                     │                    │
```
