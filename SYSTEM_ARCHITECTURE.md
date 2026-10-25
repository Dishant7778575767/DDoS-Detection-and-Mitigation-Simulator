# SENTRIX DDoS Defense Platform: Diagrams

## 1. System architecture

```mermaid
flowchart TB
    TS["Traffic sources"]
    DASH["Next.js dashboard<br/>Polls REST API"]

    subgraph API["FastAPI modular monolith"]
        ING["Ingestion<br/>Pydantic validation"]
        FEAT["Feature pipeline<br/>Versioned window stats"]
        ML["ML detection<br/>RF / Isolation Forest"]
        POL["Policy engine<br/>ML + thresholds"]
        GATE["Safety gate<br/>Auth required, bounds, mode"]
        ADP["Mitigation adapter<br/>Simulation by default"]

        ING --> FEAT --> ML --> POL --> GATE --> ADP
    end

    DB[("SQLite store: sentrix.db<br/>Alerts, audit, configs")]
    TRAIN["Offline training<br/>Datasets to model files"]
    ENF["Enforcement agent<br/>Privileged, lab only"]

    TS --> ING
    DASH <--> API
    API <--> DB
    TRAIN -->|"versioned model artifact"| API
    ADP -.->|"validated policy object"| ENF

    classDef core fill:#E1F5EE,stroke:#0F6E56,color:#085041;
    classDef lab fill:#FAECE7,stroke:#993C1D,color:#712B13;
    classDef neutral fill:#F1EFE8,stroke:#5F5E5A,color:#444441;

    class ING,FEAT,ML,POL,GATE,ADP core;
    class ENF lab;
    class TS,DASH,DB,TRAIN neutral;
```

## 2. Detection and policy workflow

```mermaid
flowchart TD
    V["Validate input"]
    REJ["Reject, 422"]
    F["Build features"]
    S["Score with model"]
    E["Detection event"]
    P{"Policy engine<br/>ML signal + threshold signal"}
    N["No signal<br/>Keep monitoring"]
    A["One signal only<br/>Alert, gather evidence"]
    R["Both signals<br/>Request bounded rate limit"]
    G["Safety gate<br/>Auth required, target, bounds, mode"]
    SIM["Simulated action<br/>Logged only"]
    ENF["Lab enforcement agent<br/>Only after lab gate"]
    X["Expire, verify, audit<br/>Cooldown, recovery path"]

    V -->|invalid| REJ
    V -->|valid| F --> S --> E --> P
    P -->|none| N
    P -->|one| A
    P -->|both| R
    A -.->|"emergency criteria only"| G
    R --> G
    G -->|"simulation mode"| SIM
    G -->|"lab mode"| ENF
    SIM --> X
    ENF --> X

    classDef core fill:#E1F5EE,stroke:#0F6E56,color:#085041;
    classDef warn fill:#FAEEDA,stroke:#854F0B,color:#633806;
    classDef bad fill:#FCEBEB,stroke:#A32D2D,color:#791F1F;
    classDef lab fill:#FAECE7,stroke:#993C1D,color:#712B13;
    classDef neutral fill:#F1EFE8,stroke:#5F5E5A,color:#444441;

    class F,S,E,P,R,G,SIM core;
    class A warn;
    class REJ bad;
    class ENF lab;
    class V,N,X neutral;
```

## Notes

- Dashed arrows mean "lab phase only" or "emergency criteria only".
- These render natively on GitHub, GitLab, VS Code (Markdown Preview Mermaid Support extension), Obsidian, and at https://mermaid.live.

## Target API and configuration contract (PRD v1.1)

The FastAPI service is planned to expose the following versioned endpoints:

- `GET /api/v1/health` — service health.
- `GET /api/v1/models` and `GET /api/v1/models/metrics` — model versions and evaluation metrics.
- `POST /api/v1/traffic/flows` and `GET /api/v1/traffic/summary` — submit observations and retrieve traffic summaries.
- `POST /api/v1/detection/analyze` — analyze features and return a model-specific result.
- `GET /api/v1/alerts` — retrieve filtered, paginated alerts.
- `GET /api/v1/mitigations` — retrieve mitigation history and status.
- `POST /api/v1/mitigations/simulate` — evaluate and record a simulated action.
- `POST /api/v1/mitigations/{id}/cancel` — cancel an authorized mitigation.
- `POST /api/v1/mitigations/disable` — disable mitigation actions through an authorized operator control.
- `GET /api/v1/audit` — retrieve authorized audit records; optional `format=json|csv` export, defaulting to JSON.
- `GET /api/v1/config/thresholds` and `PATCH /api/v1/config/thresholds` — read and update threshold configuration.

API authentication is required by default. Local development may use the
placeholder token in `.env.example`; replace it outside local development
and never commit a real token. Mitigation defaults to `simulation`, and
the SQLite database filename is `sentrix.db`. These are target contracts;
implementation is tracked by phase in `IMPLEMENTATION_PLAN.md`.