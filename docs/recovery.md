# SENTRIX Recovery Procedures & Runbooks

## 1. Overview & Purpose

This document outlines standard operating recovery procedures for SENTRIX. It provides deterministic, reproducible runbooks for resolving operational incidents, state uncertainties, service disruptions, and emergency disable conditions.

---

## 2. Incident Runbooks

### Runbook 1: Recovery from Emergency Disable
**Scenario**: An operator activated the Emergency Disable kill switch in response to anomalous alerting or high false positives.

1. **Verify Root Cause**:
   - Inspect the recent audit trail: `GET /api/v1/audit?limit=25`
   - Review active alerts and threshold configs to verify why mitigations were requested.
2. **Review/Adjust Thresholds**:
   - If false positives were caused by restrictive thresholds, adjust them via `PATCH /api/v1/config/thresholds`.
3. **Deactivate Emergency Disable**:
   ```powershell
   curl -X POST -H "Authorization: Bearer dev-only-change-me" "http://127.0.0.1:8000/api/v1/mitigations/disable?enable=true"
   ```
4. **Confirm System Status**:
   - Check `GET /api/v1/health` to confirm the service reports `status: "ok"` and `mitigation_mode: "simulation"`.
   - Verify audit log recorded event `mitigation_reenabled`.

---

### Runbook 2: Process Crash & Database Restart Reconciliation
**Scenario**: The backend process was killed or unexpectedly terminated while mitigations were active.

1. **Restart Backend Service**:
   ```powershell
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```
2. **Automatic Lifecycle Expiry**:
   - In simulation mode, active mitigations have a bounded duration (max 300s).
   - On query, any mitigations past their `expires_at` timestamp are automatically identified as expired.
3. **Verify Data Integrity**:
   - Query `GET /api/v1/mitigations?status=simulated` to inspect active simulated counts.
   - Run test suite verification to confirm database schema consistency:
     ```powershell
     python -m pytest backend/tests/storage -v
     ```
4. **Assert Host Isolation**:
   - Confirm host firewall state remains untouched:
     ```powershell
     netsh advfirewall show allprofiles
     ```

---

### Runbook 3: Missing or Corrupt Model Artifact Recovery
**Scenario**: Ingestion or analyze endpoint returns `500 INTERNAL_ERROR` or audit logs report `pipeline_failure: inference_failed` due to a missing or corrupted model file.

1. **Diagnose Artifact Path**:
   - Check configured path in `.env` (`MODEL_PATH`).
   - Check if `models/approved_model.joblib` exists:
     ```powershell
     Test-Path models/approved_model.joblib
     ```
2. **Re-export Approved Model**:
   - If the runtime artifact was deleted or corrupted, re-export from the Phase 2 training pipeline:
     ```powershell
     python ml/export_model.py
     ```
3. **Verify Runtime Loading**:
   - Run model loader test to ensure schema `1.0.0` compatibility:
     ```powershell
     python -m pytest backend/tests/unit/test_detection.py -v
     ```

---

### Runbook 4: Database Corruption & Fresh Reset
**Scenario**: Unrecoverable corruption of `sentrix.db` SQLite database.

1. **Stop Services**: Terminate the running backend and frontend processes.
2. **Archive Corrupted Database**:
   ```powershell
   Rename-Item -Path sentrix.db -NewName "sentrix.db.corrupt.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
   ```
3. **Run Initial Migrations**:
   - Restarting the backend server automatically runs `init_db()` and applies initial schema and default threshold records:
     ```powershell
     python -c "from app.storage.database import init_db; init_db()"
     ```
4. **Verify Schema**:
   - Run storage tests: `python -m pytest backend/tests/storage -v`
   - Re-populate demonstration traffic using `scripts/send_test_traffic.py --scenario normal`.

---

### Runbook 5: Linux Lab Enforcement Cleanup (Phase 6 Preparedness)
**Scenario**: Future restricted Linux lab enforcement (`nftables`/`tc`) left orphaned rules after a hard reset.

> [!IMPORTANT]
> SENTRIX in Phase 3–5 operates strictly in **Simulation Mode**. Zero host changes ever occur. The following procedure applies only if isolated Linux lab enforcement is approved and enabled in Phase 6.

1. **Identify SENTRIX-Owned Tables**:
   - Only rules created within the dedicated `sentrix` table/set may be purged. Never flush default chains.
2. **Flush Owned Ruleset**:
   ```bash
   sudo nft delete table inet sentrix_mitigation 2>/dev/null || true
   sudo tc qdisc del dev eth0 root 2>/dev/null || true
   ```
3. **Reset Mode**:
   - Set `MITIGATION_MODE=simulation` in `.env`.
   - Restart the daemon.

---

## 3. Post-Recovery Verification Checklist

- [ ] `GET /api/v1/health` returns status `200 OK`.
- [ ] `GET /api/v1/models` reports `approved_model` as active and loaded.
- [ ] `GET /api/v1/config/thresholds` returns expected active values.
- [ ] Emergency disable switch is in the expected state (`is_emergency_disabled() == False`).
- [ ] Audit log records the recovery event and administrative actor.
- [ ] Zero privileged OS commands or unwanted firewall rules exist.
