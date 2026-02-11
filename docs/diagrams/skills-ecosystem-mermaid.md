# Skills Metrics Ecosystem Architecture

## System Overview

```mermaid
graph TB
    subgraph "User Layer"
        U[User]
        Q[Query: "Fix type errors"]
    end

    subgraph "Session-Buddy Layer - Core Tracking"
        SB[Session Manager]
        ST[Skills Tracker]
        SS[Skills Storage - Dhruva]
        AS[Semantic Search - Akosha]
        SC[Skills Correlator]
    end

    subgraph "Crackerjack Layer - Quality Workflows"
        CW[Oneiric Workflows]
        WE[Workflow Events]
        SK[Skills Content - .claude/skills/*.md]
    end

    subgraph "Mahavishnu Layer - Cross-Project Analytics"
        MA[Skills Aggregator]
        MP[Multi-Project Database]
        MI[Insights & Recommendations]
    end

    U -->|Start Session| SB
    SB --> ST
    ST --> SS

    U -->|Semantic Query| AS
    AS -->|Index| SK
    AS -->|Recommend| ST

    U -->|Select Skill| ST
    ST -->|Track Usage| SS
    SS -->|ACID Storage| DH[(Dhruva Database)]

    U -->|Run Workflow| CW
    CW -->|Emit Events| WE
    WE -->|Tag: session_id| SC

    ST -->|session_id| SC
    SC -->|Correlate| CR[(Correlation Reports)]

    MA -->|Collect| MP
    MP -->|Aggregates| MI
    MI -->|Cross-Project Insights| U

    style SB fill:#e1f5fe
    style ST fill:#e1f5fe
    style SS fill:#e1f5fe
    style AS fill:#e1f5fe
    style SC fill:#e1f5fe
    style CW fill:#f3e5f5
    style WE fill:#f3e5f5
    style MA fill:#fff3e0
    style MP fill:#fff3e0
    style MI fill:#fff3e0
```

## Data Flow

```mermaid
sequenceDiagram
    participant U as User
    participant SB as Session-Buddy
    participant AS as Akosha Search
    participant ST as Skills Tracker
    participant SS as Dhruva Storage
    participant CW as Crackerjack
    participant SC as Skills Correlator
    participant MA as Mahavishnu

    U->>SB: Start session
    SB-->>U: session_id = "abc123"

    U->>AS: "Help me fix type errors"
    AS->>AS: Semantic search
    AS-->>U: Recommend: crackerjack-run (debug)

    U->>ST: Use skill: crackerjack-run
    ST->>SS: Create invocation record
    Note over SS: ACID transaction

    U->>CW: Run workflow
    CW->>SC: Emit workflow events
    Note over SC: Tagged with session_id

    U->>ST: Mark skill complete
    ST->>SS: Update invocation record
    Note over SS: Atomic update

    U->>SB: End session
    SB->>SC: Correlate skills + workflows
    SC-->>U: Correlation report

    MA->>SS: Collect metrics (periodic)
    MA->>MA: Aggregate cross-project
    MA-->>U: Insights & recommendations
```

## Storage Architecture

```mermaid
graph LR
    subgraph "Session-Buddy Dhruva Database"
        INV[skill_invocation<br/>Immutable event log]
        MET[skill_metrics<br/>Aggregated metrics]
        SES[session_skills<br/>Junction table]
    end

    subgraph "Mahavishnu Analytics"
        AGG[cross_project_metrics<br/>Aggregated data]
    end

    INV -->|Triggers update| MET
    INV -->|Session join| SES
    SES -->|Collection| AGG

    style INV fill:#c8e6c9
    style MET fill:#c8e6c9
    style SES fill:#c8e6c9
    style AGG fill:#fff9c4
```

## Integration Points

```mermaid
graph TB
    subgraph "Skills Lifecycle"
        A[1. Discover] --> AS[Akosha Semantic Search]
        B[2. Use] --> ST[Session-Buddy Tracker]
        C[3. Execute] --> CW[Crackerjack Workflow]
        D[4. Complete] --> SS[Dhruva Storage]
        E[5. Correlate] --> SC[Correlator]
        F[6. Aggregate] --> MA[Mahavishnu]
    end

    AS -.->|session_id| ST
    ST -.->|session_id| SC
    CW -.->|session_id| SC
    SC -.->|project metrics| MA
    SS -.->|raw data| MA

    style AS fill:#fff9c4
    style ST fill:#e1f5fe
    style CW fill:#f3e5f5
    style SS fill:#c8e6c9
    style SC fill:#e1f5fe
    style MA fill:#fff3e0
```
