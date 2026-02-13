---
name: skill-analytics
description: Analyze skill usage patterns, effectiveness, and generate insights for workflow optimization
---

# Skill Analytics

Analyze skill usage patterns and effectiveness to optimize your development workflow.

## 🎯 What This Does

This skill provides comprehensive analytics on skill usage:

1. **Usage Patterns**: Which skills are used most frequently
2. **Effectiveness Metrics**: Completion rates, durations, success patterns
3. **Workflow Preferences**: Which workflow paths are chosen
4. **Follow-up Actions**: What users do after using skills
5. **Trend Analysis**: How usage changes over time
6. **Recommendations**: Optimization suggestions based on data

## 📋 Understanding Your Metrics

### Key Metrics Explained

**Completion Rate**
- What percentage of skill invocations complete successfully
- High completion (>80%): Skills are working well
- Low completion (<50%): Skills may be too complex or have issues
- Target: 70-90% (some abandonment is normal)

**Average Duration**
- How long users spend in a skill
- Fast skills (<30s): Quick reference, status checks
- Medium skills (1-3min): Guided workflows
- Slow skills (>5min): Comprehensive analysis, deep dives
- Use case: Match duration to user intent

**Workflow Path Preferences**
- Which options users choose (quick vs comprehensive, etc.)
- Reveals user priorities and time constraints
- Helps optimize default options

**Follow-up Actions**
- What users do after using a skill
- Shows skill effectiveness and integration
- Common patterns: commit, run tests, continue work

## 🚀 Interactive Analytics

### Step 1: Analysis Type

**What type of analysis do you need?**

1. **Quick Summary** (30 seconds)
   - Top 5 most used skills
   - Overall completion rate
   - Average durations
   - Quick insights

2. **Detailed Analysis** (2-3 minutes)
   - Everything in quick summary
   - Per-skill breakdowns
   - Workflow path analysis
   - Follow-up action patterns
   - Recommendations

3. **Trend Analysis** (1-2 minutes)
   - Usage over time
   - Changing patterns
   - Emerging behaviors
   - Seasonal variations

4. **Export Report** (1 minute)
   - Generate JSON export
   - Save to file
   - Share with team
   - External analysis

### Step 2: Scope Selection

**What data should be analyzed?**

**Time Range:**
- [ ] **All Time** - Complete historical data
- [ ] **Last 7 Days** - Recent patterns
- [ ] **Last 30 Days** - Medium-term trends
- [ ] **Custom Range** - Specific period

**Skill Filter:**
- [ ] **All Skills** - Complete picture
- [ ] **Crackerjack Skills** - Focus on quality workflow
- [ ] **Session Skills** - Focus on session management
- [ ] **Specific Skills** - Analyze selected skills

### Step 3: Actionable Insights

**What would you like to optimize?**

- [ ] **Reduce Skill Duration** - Identify slow skills
- [ ] **Improve Completion Rates** - Find abandoned skills
- [ ] **Optimize Workflow Paths** - Most popular options
- [ ] **Enhance Follow-up Actions** - Better integration
- [ ] **All of the Above** - Comprehensive optimization

## 💡 Common Analytics Workflows

### Workflow 1: Quick Health Check

**Best for**: Regular monitoring, quick insights

```python
# Get quick summary
from crackerjack.skills.metrics import get_tracker

tracker = get_tracker()
summary = tracker.get_summary()

print(f"""
Skill Usage Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Skills: {summary['total_skills']}
Total Invocations: {summary['total_invocations']}
Overall Completion Rate: {summary['overall_completion_rate']:.1f}%
Most Used Skill: {summary['most_used_skill']} ({summary['most_used_count']} uses)
Average Duration: {summary['avg_duration_seconds']:.1f}s
""")

# Example output:
Skill Usage Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Skills: 5
Total Invocations: 127
Overall Completion Rate: 87.3%
Most Used Skill: crackerjack-run (58 uses)
Average Duration: 2.4m

Quick Insights:
✅ High completion rate - skills working well
✅ Good diversity - all skills being used
💡 crackerjack-run is primary workflow driver
💡 Average duration suggests comprehensive usage
```

**Timeline**: <30 seconds

### Workflow 2: Detailed Skill Analysis

**Best for**: Understanding specific skill performance

```python
# Get detailed metrics per skill
from crackerjack.skills.metrics import get_tracker

tracker = get_tracker()
report = tracker.generate_report()

print(report)

# Example output:
===============================================================================
Skill Metrics Report
===============================================================================

Total Skills Tracked: 5
Total Invocations: 127
Overall Completion Rate: 87.3%
Average Duration: 143.5s

Most Used Skills:
  crackerjack-run: 58 invocations (89.7% complete, 165.3s avg)
  session-checkpoint: 31 invocations (93.5% complete, 42.1s avg)
  session-end: 22 invocations (77.3% complete, 198.7s avg)
  session-start: 12 invocations (100.0% complete, 28.4s avg)
  crackerjack-init: 4 invocations (75.0% complete, 45.2s avg)

Workflow Path Preferences:
  crackerjack-run:
    daily: 42 uses
    comprehensive: 12 uses
    debug: 4 uses

  session-checkpoint:
    quick: 18 uses
    comprehensive: 11 uses
    investigation: 2 uses

  session-end:
    clean: 15 uses
    comprehensive: 5 uses
    quick: 2 uses

Common Follow-up Actions:
  git commit: 47
  continue coding: 38
  run tests: 29
  review changes: 21
  take break: 12

===============================================================================
```

**Timeline**: 2-3 minutes

### Workflow 3: Optimization Recommendations

**Best for**: Improving workflow effectiveness

```python
# Generate optimization recommendations
from crackerjack.skills.metrics import get_tracker

tracker = get_tracker()
all_metrics = tracker.get_all_metrics()

recommendations = []

for skill_name, metrics in all_metrics.items():
    # Check completion rate
    if metrics.completion_rate() < 70:
        recommendations.append({
            "skill": skill_name,
            "issue": "Low completion rate",
            "metric": f"{metrics.completion_rate():.1f}%",
            "suggestion": "Skill may be too complex or have UX issues",
            "priority": "HIGH" if metrics.completion_rate() < 50 else "MEDIUM",
        })

    # Check duration
    avg_duration = metrics.avg_duration_seconds()
    if skill_name == "crackerjack-run":
        if avg_duration > 300:  # 5 minutes
            recommendations.append({
                "skill": skill_name,
                "issue": "Long duration",
                "metric": f"{avg_duration:.1f}s",
                "suggestion": "Consider 'quick' workflow option",
                "priority": "LOW",
            })
    elif skill_name in ["session-checkpoint", "session-start"]:
        if avg_duration > 60:  # 1 minute
            recommendations.append({
                "skill": skill_name,
                "issue": "Slower than expected",
                "metric": f"{avg_duration:.1f}s",
                "suggestion": "Optimize for faster execution",
                "priority": "MEDIUM",
            })

# Print recommendations
if recommendations:
    print("Optimization Recommendations:")
    print("═" * 60)

    for rec in sorted(recommendations, key=lambda x: x["priority"]):
        print(f"\n[{rec['priority']}] {rec['skill']}")
        print(f"  Issue: {rec['issue']}")
        print(f"  Metric: {rec['metric']}")
        print(f"  Suggestion: {rec['suggestion']}")
else:
    print("✅ No major issues detected!")
    print("   All skills performing within acceptable ranges.")
```

**Example output:**
```
Optimization Recommendations:
══════════════════════════════════════════════════════════════════════════

[HIGH] session-end
  Issue: Low completion rate
  Metric: 77.3%
  Suggestion: Skill may be too complex or have UX issues
  Details: Users abandoning comprehensive end, consider simplifying

[MEDIUM] session-checkpoint
  Issue: Slower than expected
  Metric: 42.1s
  Suggestion: Optimize for faster execution
  Details: Checkpoint should be <30s for frequent use

[LOW] crackerjack-run
  Issue: Long duration
  Metric: 165.3s
  Suggestion: Consider 'quick' workflow option
  Details: Users may benefit from faster quality checks
```

**Timeline**: 2-3 minutes

### Workflow 4: Trend Analysis

**Best for**: Understanding changing patterns over time

```python
# Analyze usage trends
from crackerjack.skills.metrics import get_tracker
from datetime import datetime, timedelta

tracker = get_tracker()

# Get recent invocations
cutoff = datetime.now() - timedelta(days=7)
recent_invocations = [
    inv for inv in tracker._invocations
    if datetime.fromisoformat(inv.invoked_at) > cutoff
]

# Analyze trends by skill
skill_usage_by_day = {}
for inv in recent_invocations:
    day = datetime.fromisoformat(inv.invoked_at).date()
    skill = inv.skill_name

    if skill not in skill_usage_by_day:
        skill_usage_by_day[skill] = {}

    if day not in skill_usage_by_day[skill]:
        skill_usage_by_day[skill][day] = 0

    skill_usage_by_day[skill][day] += 1

# Print trends
print("7-Day Usage Trends:")
print("═" * 60)

for skill, daily_counts in sorted(
    skill_usage_by_day.items(),
    key=lambda x: sum(x[1].values()),
    reverse=True
)[:5]:
    total = sum(daily_counts.values())
    avg = total / len(daily_counts)
    print(f"\n{skill}:")
    print(f"  Total (7 days): {total}")
    print(f"  Average per day: {avg:.1f}")

    # Show trend
    counts = list(daily_counts.values())
    if len(counts) >= 2:
        if counts[-1] > counts[-2]:
            print(f"  Trend: ↗️ Increasing")
        elif counts[-1] < counts[-2]:
            print(f"  Trend: ↘️ Decreasing")
        else:
            print(f"  Trend: → Stable")
```

**Example output:**
```
7-Day Usage Trends:
══════════════════════════════════════════════════════════════════════════

crackerjack-run:
  Total (7 days): 42
  Average per day: 6.0
  Trend: ↗️ Increasing

session-checkpoint:
  Total (7 days): 18
  Average per day: 2.6
  Trend: → Stable

session-end:
  Total (7 days): 12
  Average per day: 1.7
  Trend: ↘️ Decreasing

session-start:
  Total (7 days): 8
  Average per day: 1.1
  Trend: → Stable

crackerjack-init:
  Total (7 days): 2
  Average per day: 0.3
  Trend: → Stable
```

**Timeline**: 1-2 minutes

### Workflow 5: Export and Share

**Best for**: Team collaboration, external analysis

```python
# Export metrics for team review
from crackerjack.skills.metrics import get_tracker
from pathlib import Path

tracker = get_tracker()

# Export to JSON
output_file = Path("skill-metrics-export.json")
tracker.export_metrics(output_file)

print(f"✅ Metrics exported to {output_file}")
print(f"   File size: {output_file.stat().st_size / 1024:.1f} KB")
print(f"   Skills tracked: {len(tracker.get_all_metrics())}")
print(f"   Total invocations: {tracker.get_summary()['total_invocations']}")
```

**Usage**:
- Share with team for review
- Import into analytics tools
- Create custom dashboards
- Track progress over time

**Timeline**: <1 minute

## 🔍 Interpreting Your Data

### Completion Rate Analysis

**High Completion Rate (>80%)** ✅:
- Skills are well-designed
- Users find value
- Good UX and documentation
- **Action**: Keep as-is, monitor for changes

**Medium Completion Rate (60-80%)** ⚠️:
- Generally effective but some friction
- May have edge cases or confusion points
- **Action**: Review abandoned invocations, identify patterns

**Low Completion Rate (<60%)** ❌:
- Significant issues with skill design
- Too complex or unclear
- Mismatch with user needs
- **Action**: Major redesign needed

### Duration Analysis

**Fast Skills (<30s)**:
- Status checks, quick reference
- Should complete quickly
- **Target**: <10s for 90th percentile

**Medium Skills (30s-3min)**:
- Guided workflows, routine tasks
- Reasonable for interactive guidance
- **Target**: <2min average

**Slow Skills (>3min)**:
- Comprehensive analysis, deep dives
- Appropriate for complex tasks
- **Target**: <5min average

**Too Slow** (2x target):
- Consider breaking into smaller skills
- Add quick/comprehensive options
- Optimize common paths

### Workflow Path Preferences

**Imbalanced Preferences** (90/10 split):
- One path dominates, others rarely used
- **Action**: Consider removing unused paths
- Or improve unpopular paths

**Balanced Preferences** (40/40/20 split):
- Good diversity of use cases
- Users value different options
- **Action**: Continue supporting all paths

**Changing Preferences** (shifts over time):
- Users discovering new workflows
- **Action**: Adapt defaults to emerging patterns

### Follow-up Action Patterns

**Common Actions**:
- `git commit` → Skills integrate well with version control
- `continue coding` → Skills don't interrupt flow
- `run tests` → Skills trigger quality workflow

**Missing Actions**:
- No documentation updates
- No code review
- **Action**: Add reminders for best practices

## 🎨 Optimizing Based on Metrics

### Reducing Abandonment

**Identify Abandonment Patterns:**
```python
# Find abandoned invocations
abandoned = [
    inv for inv in tracker._invocations
    if not inv.completed
]

# Analyze by skill
abandon_by_skill = {}
for inv in abandoned:
    skill = inv.skill_name
    if skill not in abandon_by_skill:
        abandon_by_skill[skill] = 0
    abandon_by_skill[skill] += 1

# Print insights
for skill, count in sorted(
    abandon_by_skill.items(),
    key=lambda x: x[1],
    reverse=True
):
    metrics = tracker.get_skill_metrics(skill)
    rate = metrics.completion_rate() if metrics else 0
    print(f"{skill}: {count} abandoned ({rate:.1f}% complete)")
```

**Common Causes**:
- Skill too long/complex
- Unclear options or guidance
- Technical errors or failures
- User changed mind/need changed

**Solutions**:
- Add quick/comprehensive paths
- Improve documentation
- Fix technical issues
- Simplify common workflows

### Improving Integration

**Analyze Follow-up Actions**:
```python
# Find most common follow-up actions
all_actions = {}
for metrics in tracker.get_all_metrics().values():
    for action, count in metrics.follow_up_actions.items():
        all_actions[action] = all_actions.get(action, 0) + count

# Identify missing integrations
expected_actions = ["git commit", "run tests", "review changes"]
missing = [a for a in expected_actions if a not in all_actions]

if missing:
    print("⚠️  Consider adding reminders for:")
    for action in missing:
        print(f"   - {action}")
```

**Enhancement Ideas**:
- Add git commit reminders after `crackerjack-run`
- Suggest code review after completing features
- Recommend documentation updates
- Prompt for checkpoint after long work sessions

## 🔧 Configuration

### Metrics Storage

**Location**: `.session-buddy/skill_metrics.json`

**Format**:
```json
{
  "invocations": [
    {
      "skill_name": "crackerjack-run",
      "invoked_at": "2025-02-10T12:34:56",
      "workflow_path": "daily",
      "completed": true,
      "duration_seconds": 165.3,
      "follow_up_actions": ["git commit", "continue coding"],
      "error_type": null
    }
  ],
  "skills": {
    "crackerjack-run": {
      "skill_name": "crackerjack-run",
      "total_invocations": 58,
      "completed_invocations": 52,
      "abandoned_invocations": 6,
      "total_duration_seconds": 8595.6,
      "workflow_paths": {
        "daily": 42,
        "comprehensive": 12,
        "debug": 4
      },
      "common_errors": {},
      "follow_up_actions": {
        "git commit": 38,
        "continue coding": 22,
        "run tests": 18
      },
      "first_invoked": "2025-02-01T10:00:00",
      "last_invoked": "2025-02-10T12:34:56"
    }
  },
  "last_updated": "2025-02-10T12:34:56"
}
```

### Privacy Settings

**Opt-Out**:
```python
# Disable metrics tracking
import os
os.environ["SKILL_METRICS_ENABLED"] = "false"
```

**Clear History**:
```python
from crackerjack.skills.metrics import get_tracker
from pathlib import Path

# Remove metrics file
metrics_file = Path(".session-buddy/skill_metrics.json")
if metrics_file.exists():
    metrics_file.unlink()
    print("✅ Metrics history cleared")
```

## 🎯 Best Practices

### DO ✅

- **Review metrics regularly** - Weekly or monthly reviews
- **Act on insights** - Use data to drive improvements
- **Respect privacy** - All data local, no PII
- **Share with team** - Collaborate on workflow optimization
- **Track trends** - Look for changes over time

### DON'T ❌

- **Don't obsess over single data points** - Look for patterns
- **Don't make changes based on small samples** - Wait for significant data
- **Don't ignore completion rates** - Key effectiveness metric
- **Don't forget user context** - Metrics tell what, not why
- **Don't collect unnecessary data** - Privacy-first approach

## 📚 Related Skills

- All tracked skills - Use them to generate metrics data!
- `session-checkpoint` - Mid-session workflow analysis
- `session-end` - Session metrics summary

## 🔗 Further Reading

- **Metrics System**: `crackerjack/skills/metrics.py`
- **Analytics Guide**: `docs/skill-analytics.md`
- **Privacy Policy**: See local storage only, no data transmission
