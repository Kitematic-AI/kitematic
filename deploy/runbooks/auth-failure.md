# Runbook: Authentication Failure

## Detection
- Alert: `security.auth.failed` rate spike
- Symptom: Users reporting 401 errors, spike in auth failure logs

## Severity Assessment
| Finding | Severity |
|---|---|
| All auth failing (100% failure) | P1 |
| Auth failing for specific key/tenant | P2 |
| Occasional auth failures (< 1%) | P3 |

## Immediate Actions
1. Check `APIKeyAuthProvider` fingerprint store
2. Verify key rotation status — was a rotation done recently?
3. Check for expired keys or configuration drift
4. If key store corrupted:
   - Restore from backup key store
   - Or regenerate keys for affected tenants
5. Test with a known-valid key:
   ```bash
   curl -H "X-API-Key: <test-key>" http://localhost:8000/api/v1/health
   ```

## Verification
- Auth success rate > 99.9%
- No 401 errors from valid keys
- Audit log shows auth.success events for affected tenants

## Rollback
- If caused by key rotation: re-add old key temporarily
  ```python
  provider.add_key("old-key", AuthContext(tenant_id="...", agent_id="..."))
  ```

## Escalation
| Condition | Escalate To |
|---|---|
| All tenants affected | Security team lead |
| Key store corrupted | Platform lead |
| Cannot revert rotation | Engineering director |

## Recovery Criteria
- Auth success rate > 99.9%
- No 401 errors from valid keys
- Affected tenants can authenticate
