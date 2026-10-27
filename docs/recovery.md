# SENTRIX Recovery Procedures & Runbooks

## 1. Overview & Purpose

This document gives step-by-step recovery procedures for SENTRIX. Each runbook is repeatable and covers one type of problem: incidents, unclear system state, service outages, and emergency disable.

---

## 2. Incident Runbooks

### Runbook 1: Recovery from Emergency Disable

**Scenario:** An operator turned on the Emergency Disable switch because of strange alerts or too many false positives.

1. **Find the root cause**
   - Check the recent audit log: `GET /api/v1/audit?limit=25`
   - Review active alerts and threshold settings to see why mitigations were requested.
2. **Review or adjust thresholds**
   - If strict thresholds caused false positives, change them with `PATCH /api/v1/config/thresholds`.
3. **Turn off Emergency Disable**
   ```powershell
   curl -X POST -H "Authorization: Bearer dev-only-change-me" "http://127.0.0.1:8000/api/v1/mitigations/disable?enable=true"
   ```
4. **Confirm system status**
   - Call `GET /api/v1/health` and check for `status: "ok"` and `mitigation_mode: "simulation"`.
   - Check that the audit log has the event `mitigation_reenabled`.

---

### Runbook 2: Process Crash & Database Restart Reconciliation

**Scenario:** The backend was killed or stopped suddenly while mitigations were active.

1. **Restart the backend**
   ```powershell
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```
2. **Automatic expiry**
   - In simulation mode, every mitigation has a time limit (max 300s).
   - When queried, any mitigation past its `expires_at` time is marked as expired automatically.
3. **Check data integrity**
   - Call `GET /api/v1/mitigations?status=simulated` to see active simulated mitigations.
   - Run the storage tests to confirm the database schema is fine:
     ```powershell
     python -m pytest backend/tests/storage -v
     ```
4. **Confirm host isolation**
   - Make sure the host firewall was not changed:
     ```powershell
     netsh advfirewall show allprofiles
     ```

---

### Runbook 3: Missing or Corrupt Model Artifact Recovery

**Scenario:** The ingestion or analyze endpoint returns `500 INTERNAL_ERROR`, or the audit log shows `pipeline_failure: inference_failed`, because the model file is missing or corrupt.

1. **Check the model path**
   - Check `MODEL_PATH` in `.env`.
   - Check that `models/approved_model.joblib` exists:
     ```powershell
     Test-Path models/approved_model.joblib
     ```
2. **Re-export the approved model**
   - If the file is deleted or corrupt, export it again from the Phase 2 training pipeline:
     ```powershell
     python ml/export_model.py
     ```
3. **Check that the model loads**
   - Run the loader test to confirm schema `1.0.0` works:
     ```powershell
     python -m pytest backend/tests/unit/test_detection.py -v
     ```

---

### Runbook 4: Database Corruption & Fresh Reset

**Scenario:** The SQLite database `sentrix.db` is corrupt and cannot be repaired.

1. **Stop services**
   - Stop the running backend and frontend.
2. **Archive the corrupt database**
   ```powershell
   Rename-Item -Path sentrix.db -NewName "sentrix.db.corrupt.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
   ```
3. **Run initial setup**
   - Restarting the backend runs `init_db()` automatically. It creates the schema and default threshold records. You can also run it by hand:
     ```powershell
     python -c "from app.storage.database import init_db; init_db()"
     ```
4. **Verify the schema**
   - Run the storage tests: `python -m pytest backend/tests/storage -v`
   - Add demo traffic again with `scripts/send_test_traffic.py --scenario normal`.

---

### Runbook 5: Simulator Restart & Interrupted Run Recovery

**Scenario:** The backend process restarted while a simulation run or simulated mitigation was in-flight (TC-10 / TC-12).

1. **Automatic State Reconciliation:**
   - On backend startup, the system scans for in-flight actions where virtual expiry timestamp has elapsed.
   - Expired actions are transitioned to `status: expired` and an audit event (`restart_reconciliation_expired`) is recorded.
2. **Interrupted Simulation Runs:**
   - Active simulation runs that cannot resume from their last committed tick are transitioned to `interrupted`.
   - The simulator never silently restarts an interrupted run from tick zero.
3. **Manual Operator Re-enable (If Emergency Disable Triggered):**
   - If emergency disable was triggered, re-enable via:
   ```bash
   curl -X POST -H "Authorization: Bearer <API_TOKEN>" \
     "http://127.0.0.1:8000/api/v1/mitigations/disable?enable=true"
   ```

---

## 3. Post-Recovery Verification Checklist

- [ ] `GET /api/v1/health` returns `200 OK`.
- [ ] `GET /api/v1/models` shows `approved_model` as active and loaded.
- [ ] `GET /api/v1/config/thresholds` returns the expected active values.
- [ ] Emergency disable is in the expected state (`is_emergency_disabled() == False`).
- [ ] The audit log records the recovery event and the admin actor.
- [ ] No privileged OS commands or unwanted firewall rules exist.