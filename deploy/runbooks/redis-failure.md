# Runbook: Redis Failure

## Detection
- Alert: `RedisPublishErrors` or `ConsumerLagHigh`
- Symptom: Redis connection errors in runtime logs, consumer lag > threshold

## Severity Assessment
| Finding | Severity |
|---|---|
| Redis unreachable, no events published | P1 |
| Redis slow, consumer lag > 10k events | P2 |
| Redis degraded, latency > 100ms | P3 |

## Immediate Actions
1. Ping Redis: `redis-cli -u redis://redis-service:6379 ping`
2. If unreachable: restart Redis pod
   ```
   kubectl rollout restart statefulset kitematic-redis
   ```
3. If Redis will be down > 2 min: switch to memory backend
   ```
   kubectl patch configmap kitematic-config -p '{"data":{"KITEMATIC_EVENT_BACKEND":"memory"}}'
   kubectl rollout restart deployment kitematic-api
   ```
4. Restore from AOF/RDB backup if data loss detected

## Verification
- `redis-cli ping` returns `PONG`
- Runtime logs show "Connected to Redis"
- Event consumption resumes (consumer lag decreasing)

## Rollback
- Switch back to `redis_streams` backend:
  ```
  kubectl patch configmap kitematic-config -p '{"data":{"KITEMATIC_EVENT_BACKEND":"redis_streams"}}'
  kubectl rollout restart deployment kitematic-api
  ```

## Escalation
| Condition | Escalate To |
|---|---|
| Redis unreachable > 15 min | Infrastructure lead |
| Data loss suspected | Platform lead |
| AOF/RDB restoration needed | DevOps engineer |

## Recovery Criteria
- Redis responding to commands
- Event stream resuming (events visible via `XLEN`)
- Consumer lag < 100 events
- Memory backend no longer active
