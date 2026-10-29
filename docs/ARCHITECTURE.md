# SENTRIX — System Architecture & Design Specification

**System Name:** SENTRIX (Secure Enterprise Network Telemetry & Real-Time Incident X-Defend)  
**Architecture Version:** 2.0.0  
**Target Environment:** Real-World Web Infrastructures, Cloud Environments, and Cyber Ranges  

---

## 1. High-Level Architecture Overview

SENTRIX is an autonomous, real-time DDoS detection, monitoring, and defensive mitigation platform. It combines live HTTP telemetry streaming, adaptive statistical anomaly baselining (EWMA), explainable multi-tier threat classification, and staged defensive mitigation enforcement to safeguard web applications from malicious denial-of-service campaigns without harming legitimate visitors.

```mermaid
flowchart TD
    subgraph Traffic_Layer["1. Ingress & Telemetry Ingestion Tier"]
        Clients["Web Visitors / Attackers"]
        ReverseProxy["Reverse Proxy (Nginx / Caddy / Cloudflare)"]
        ASGIMiddleware["Sentrix ASGI Middleware (FastAPI / Starlette)"]
        IngressAPI["Telemetry Ingress API (/api/v1/telemetry/ingress)"]
        LogParser["Log Parser (Combined, CLF, JSON)"]
        PrivacyMasker["GDPR / Subnet Privacy Masker (/24, /48)"]

        Clients --> ReverseProxy
        ReverseProxy --> IngressAPI
        ASGIMiddleware --> IngressAPI
        IngressAPI --> LogParser
        LogParser --> PrivacyMasker
    end

    subgraph Feature_Layer["2. Sliding-Window Aggregation & Feature Engine"]
        CircBuffer["Circular Buffer (60s Retention)"]
        PercentileCalc["Percentile Engine (p50, p90, p99 Latencies)"]
        EntropyCalc["Shannon Entropy Calculator H(X) & Entropy Ratio η"]
        Aggregator["TelemetryAggregator (Thread-Safe Deque)"]

        PrivacyMasker --> Aggregator
        Aggregator --> CircBuffer
        CircBuffer --> PercentileCalc
        CircBuffer --> EntropyCalc
    end

    subgraph Detection_Layer["3. Multi-Tier Threat Detection Engine"]
        EWMA["Adaptive Baseline Tracker (EWMA Mean μ_t, Moving Variance σ_t^2)"]
        ZScore["Velocity Shift Engine (Z_rps, Z_err, Z_lat, Z_bps)"]
        ThreatClassifier["Explainable Threat Classifier"]
        FlashCrowdDiff{"Flash Crowd Differentiator"}

        Aggregator --> EWMA
        EWMA --> ZScore
        ZScore --> ThreatClassifier
        ThreatClassifier --> FlashCrowdDiff
    end

    subgraph Defense_Layer["4. Defensive Mitigation & Policy Engine"]
        DryRunEngine["Staged Dry-Run Mitigation Engine"]
        RateLimiter["Leaky Bucket Rate Limiter"]
        AllowlistGuard["Protected Infrastructure Allowlist Guard"]
        TTLPruner["Automatic Rule TTL Pruning"]
        ConfigExporter["Config Exporters (Nginx / Caddy / Cloudflare)"]

        FlashCrowdDiff -- "ATTACK DETECTED" --> DryRunEngine
        FlashCrowdDiff -- "FLASH CROWD" --> AllowlistGuard
        DryRunEngine --> RateLimiter
        DryRunEngine --> TTLPruner
        DryRunEngine --> ConfigExporter
    end

    subgraph Persistence_Layer["5. Relational Persistence & Audit Trail"]
        DB[(SQLite / PostgreSQL Engine)]
        AlertModel["AlertModel (Incidents)"]
        AuditModel["AuditEventModel (Audit Trail)"]
        RuleModel["MitigationRuleModel (Active Rules)"]

        FlashCrowdDiff --> AlertModel
        DryRunEngine --> RuleModel
        DryRunEngine --> AuditModel
        AlertModel --> DB
        AuditModel --> DB
        RuleModel --> DB
    end

    subgraph Presentation_Layer["6. Next.js 16 Unified SOC Dashboard Tier"]
        SOC_Overview["/overview (Live Traffic Pulse)"]
        SOC_Telemetry["/telemetry (Live HTTP Telemetry)"]
        SOC_Threats["/threats (Threat Center & Z-Scores)"]
        SOC_Alerts["/alerts (Persistent Incidents)"]
        SOC_Mitigation["/mitigation (Defensive Rules & Exporter)"]
        SOC_Simulator["/simulator (Isolated Cyber Range Lab)"]
        SOC_History["/history (Regulatory Audit Ledger)"]
        SOC_Settings["/settings (Policy Matrix)"]

        DB --> SOC_Alerts
        DB --> SOC_History
        DB --> SOC_Mitigation
        EWMA --> SOC_Threats
        Aggregator --> SOC_Telemetry
        DryRunEngine --> SOC_Mitigation
    end
```

---

## 2. Ingestion & Sliding-Window Feature Pipeline

The telemetry ingress pipeline accepts both pre-aggregated metric objects and raw server logs. 

```mermaid
sequenceDiagram
    autonumber
    actor Proxy as Nginx / Caddy / App
    participant API as Ingress API (/ingress)
    participant Parser as Log Parser & Masker
    participant Agg as TelemetryAggregator
    participant Deque as Thread-Safe Circular Deque

    Proxy->>API: POST /api/v1/telemetry/ingress (Batch or Logs)
    API->>Parser: Parse lines (Combined / CLF / JSON)
    Parser->>Parser: Mask IP (/24 IPv4, /48 IPv6)
    Parser-->>API: List[RequestTelemetryItem]
    API->>Agg: record_batch(items)
    Agg->>Deque: Acquire Lock & Append Items
    Agg->>Deque: Evict items older than (now - 60s)
    Agg->>Agg: Compute RPS, Throughput, Error Rates
    Agg->>Agg: Compute Latency Percentiles (p50, p90, p99)
    Agg->>Agg: Compute Shannon Entropy H(X) & Ratio η
    Agg-->>API: Summary Cache Updated
    API-->>Proxy: HTTP 202 Accepted {ingested: N}
```

### Mathematical Definitions:
1. **Shannon Entropy of Client Distribution:**
   $$H(X) = -\sum_{i=1}^{n} P(x_i) \log_2 P(x_i)$$
   Where $P(x_i) = \frac{\text{requests from IP } i}{\text{total requests in window}}$.
2. **Normalized Entropy Ratio:**
   $$\eta = \frac{H(X)}{\log_2(n)} \quad (\text{for } n > 1)$$
   - $\eta \approx 0$: Concentrated traffic (single attacker or small cluster).
   - $\eta \approx 1$: Uniformly dispersed traffic across diverse IP space (Flash Crowd or Distributed Botnet).

---

## 3. Statistical Baseline & Multi-Tier Detection Engine

SENTRIX decouples anomaly detection from fixed static thresholds by tracking dynamic baseline behavior.

```mermaid
flowchart LR
    Telemetry["Live Sliding-Window Metrics"] --> Tracker["Adaptive EWMA Tracker"]
    
    subgraph EWMA_Math["EWMA Mathematical State"]
        Mean["Running Mean: μ_t = α·x_t + (1-α)·μ_{t-1}"]
        Variance["Moving Variance: σ_t^2 = (1-α)·(σ_{t-1}^2 + α·(x_t - μ_{t-1})^2)"]
        ZScore["Velocity Z-Scores: Z = (x - μ) / max(σ, ε)"]
        Mean --> ZScore
        Variance --> ZScore
    end

    Tracker --> EWMA_Math
    ZScore --> Classifier["Explainable Threat Classifier"]

    subgraph Classifier_Rules["Threat Evaluation Matrix"]
        R1["Z_rps ≥ 3.0 & η ≤ 0.40 & Err ≥ 15% ➔ VOLUMETRIC_HTTP_FLOOD"]
        R2["Z_lat ≥ 3.0 & Low RPS ➔ SLOWLORIS_EXHAUSTION"]
        R3["Z_err ≥ 3.0 on /login ➔ CREDENTIAL_STUFFING"]
        R4["Z_rps ≥ 2.0 & η ≥ 0.75 & Err < 10% ➔ FLASH_CROWD (ALLOW)"]
    end

    Classifier --> Classifier_Rules
    Classifier_Rules --> Persistence["Persistent Incident & Audit Logging"]
```

### Flash Crowd Differentiator:
When traffic surges ($Z_{rps} \ge 2.0$), legacy systems often trigger blanket rate limits, damaging legitimate marketing spikes. SENTRIX differentiates flash crowds through:
- **Entropy Ratio ($\eta \ge 0.75$):** Real humans arrive from varied geographic/ISP IP pools.
- **Client Count ($n \ge 5$):** Multi-source traffic distribution.
- **Error Rate ($< 10\%$):** Real users successfully access content with 200 OK responses.
- **Action:** Tagged as `FLASH_CROWD`, action `ALLOW`, zero collateral damage.

---

## 4. Defensive Mitigation Engine & Lifecycle

Defensive rules follow a strict safety lifecycle to prevent operator error or self-inflicted outages.

```mermaid
stateDiagram-v2
    [*] --> Proposed: Threat Detected / Analyst Proposal
    
    state Proposed {
        [*] --> CheckAllowlist: Verify Target IP/CIDR
        CheckAllowlist --> Reject: Target is Protected (127.0.0.1, 10.0.0.0/8)
        CheckAllowlist --> StagedDryRun: Target is External
    }

    state StagedDryRun {
        [*] --> SimulateEnforcement
        SimulateEnforcement: Traffic is ALLOWED
        SimulateEnforcement: simulated_blocked_count++
        SimulateEnforcement: Measure potential false positives
    }

    StagedDryRun --> Active: SOC Operator Approves Rule
    StagedDryRun --> Revoked: SOC Operator Dismisses Rule
    StagedDryRun --> Expired: Rule TTL Expires (auto-pruned)

    state Active {
        [*] --> EnforceLeakyBucket
        EnforceLeakyBucket: Traffic is BLOCKED or RATE-LIMITED
        EnforceLeakyBucket: active_blocked_count++
    }

    Active --> Revoked: SOC Operator Revokes Rule
    Active --> Expired: Rule TTL Expires (auto-pruned)
    Active --> StagedDryRun: Emergency Kill-Switch Engaged

    Revoked --> [*]
    Expired --> [*]
```

---

## 5. Security & Safety Invariants

1. **Allowlist Invariant:** Critical infrastructure (`127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, and healthcheck probes) can never be blocked. The engine enforces an immutable whitelist validation gate.
2. **Dry-Run by Default:** Newly proposed rules start in `DRY_RUN` mode. No traffic is actively dropped until an authenticated SOC operator explicitly approves the rule.
3. **Mandatory Rule TTL:** Every rule has an enforced expiration timestamp (default 300s). Expired rules are automatically purged by background cleanup to prevent indefinite blacklisting.
4. **Emergency Kill-Switch:** A global emergency switch (`set_emergency_disabled(True)`) bypasses all active mitigations in sub-millisecond execution time.
5. **Privacy by Default:** Raw IP addresses ingested into the telemetry pipeline are automatically masked to `/24` or `/48` subnets before storage or aggregation, ensuring compliance with privacy regulations.
6. **Immutable Audit Ledger:** Every rule proposal, approval, revocation, and automated threat alert writes an append-only record to `AuditEventModel`.
