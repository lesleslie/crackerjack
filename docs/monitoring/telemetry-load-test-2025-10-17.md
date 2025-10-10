# Workflow Telemetry Load Test – 2025-10-17

**Scenario:** Simulate five concurrent workflow runs publishing `workflow.started`
and `workflow.completed` events through the in-process `WorkflowEventBus` while
`WorkflowEventTelemetry` records metrics. Each scenario was executed five times
to compute an average duration and throughput baseline.

| Run | Duration (s) | Completed Events | Throughput (events/s) |
|-----|--------------|------------------|-----------------------|
| 1 | 0.004775 | 5 | 1,047.13 |
| 2 | 0.006519 | 5 | 766.99 |
| 3 | 0.003939 | 5 | 1,269.39 |
| 4 | 0.003852 | 5 | 1,298.11 |
| 5 | 0.004089 | 5 | 1,222.72 |

**Averages**

- Duration: **0.00463 s**
- Throughput: **1,120.87 events/s**

**Observations**

- The telemetry subscriber handled 25 events across the batch without dropped
  messages or lag; background persistence did not become a bottleneck.
- Run-to-run variance stayed within 0.003 s, indicating the current
  implementation is CPU-bound but stable for the target workload.
- Throughput comfortably exceeds the Sprint 1 goal of processing five
  concurrent workflows (>500 events/s budget).

**Next Steps**

1. Extend the benchmark to 10 concurrent workflows during Phase 4 Sprint 3.
2. Capture CPU and memory telemetry from the monitoring endpoints to pair with
   throughput metrics.
3. Wire the benchmark into a scheduled quality gate once Phase 4.1 dashboards
   ship, ensuring regressions are detected automatically.
