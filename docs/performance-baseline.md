# Crackerjack Performance Baseline Report

**Generated**: 2025-11-05 13:53:13

## Summary

| Mode | Runs | Mean | Median (P50) | P95 | P99 | Success Rate |
|------|------|------|--------------|-----|-----|--------------|
| `default` | 20 | 206.89s | 195.48s | 300.06s | 300.06s | 0% |
| `fast` | 20 | 63.91s | 52.94s | 136.05s | 136.27s | 100% |
| `comp` | 20 | 253.38s | 268.59s | 300.07s | 300.07s | 0% |

## Detailed Statistics

### Mode: `default`

- **Runs**: 20
- **Mean**: 206.89s
- **Median (P50)**: 195.48s
- **P95**: 300.06s
- **P99**: 300.06s
- **Min**: 156.74s
- **Max**: 300.06s
- **Std Dev**: 43.24s
- **Success Rate**: 0%

### Mode: `fast`

- **Runs**: 20
- **Mean**: 63.91s
- **Median (P50)**: 52.94s
- **P95**: 136.05s
- **P99**: 136.27s
- **Min**: 41.76s
- **Max**: 136.27s
- **Std Dev**: 28.20s
- **Success Rate**: 100%

### Mode: `comp`

- **Runs**: 20
- **Mean**: 253.38s
- **Median (P50)**: 268.59s
- **P95**: 300.07s
- **P99**: 300.07s
- **Min**: 161.91s
- **Max**: 300.07s
- **Std Dev**: 45.72s
- **Success Rate**: 0%

## ACB Migration Abort Criteria

Based on these baseline measurements:

- **default mode**: Abort if median > 215.02s (10% slower than 195.48s)
- **fast mode**: Abort if median > 58.24s (10% slower than 52.94s)
- **comp mode**: Abort if median > 295.45s (10% slower than 268.59s)
