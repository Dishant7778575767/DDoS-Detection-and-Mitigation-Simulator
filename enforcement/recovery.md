# SENTRIX Linux Lab Enforcement Recovery & Troubleshooting Runbook

This runbook defines the operational procedures for investigating and resolving enforcement failures in the isolated Linux lab, addressing **TC-10 (Cleanup Failure)** and **TC-12 (Service Restart Reconciliation)** as mandated by PRD Section 8.3, 8.4, and 10.2.

---

## 1. Safety Invariant: Fail-Closed Lockdown

When any uncertainty, state mismatch, or cleanup verification failure occurs:
1. **Emergency Disable is automatically engaged** (`_emergency_disable_active = True`).
2. All subsequent mitigation requests are rejected with `HTTP 400 Bad Request`.
3. An audit record is written to SQLite (`cleanup_failure` or `lab_reconciliation_mismatch`).
4. The system remains in lockdown until an operator manually verifies network state and restores health.

---

## 2. TC-10: Cleanup Failure Handling & Recovery Procedure

### Scenario
A rule TTL expires or an operator requests cancellation, but the kernel rule removal fails or `verify_rule_removed()` fails to confirm deletion.

### Diagnostic Steps
1. **Check Audit Logs:**
   Query the audit log endpoint or SQLite database for the failed action:
   ```bash
   # Via API (authenticated)
   curl -H "Authorization: Bearer <API_TOKEN>" \
     "http://localhost:8000/api/v1/audit?event_type=cleanup_failure"
   ```
2. **Inspect Kernel `nftables` State:**
   In the isolated lab namespace, list all rules and handles in the SENTRIX table:
   ```bash
   sudo ip netns exec sentrix_ns nft -a list table inet sentrix_mitigation
   ```
   *Look for lines ending with `# handle <N>` containing the target `action_id` comment.*

### Manual Remediation Steps
1. **Delete Specific Orphaned Handle:**
   Delete the unverified rule specifically by its handle number `<handle_id>`:
   ```bash
   sudo ip netns exec sentrix_ns nft delete rule inet sentrix_mitigation forward handle <handle_id>
   ```
2. **Or Flush Dedicated SENTRIX Table (if multiple rules are stale):**
   > [!IMPORTANT]
   > `sentrix_mitigation` is an isolated dedicated table. Deleting it does NOT affect system or host firewall tables.
   ```bash
   sudo ip netns exec sentrix_ns nft delete table inet sentrix_mitigation
   sudo ip netns exec sentrix_ns nft add table inet sentrix_mitigation
   sudo ip netns exec sentrix_ns nft add chain inet sentrix_mitigation forward '{ type filter hook forward priority -100 ; policy accept ; }'
   ```
3. **Verify Clean Removal:**
   Confirm that no rules matching `sentrix:*` remain:
   ```bash
   sudo ip netns exec sentrix_ns nft list table inet sentrix_mitigation
   ```
4. **Transition Action to Recovered:**
   Use the Python recovery helper or management CLI:
   ```python
   from app.mitigation.reconcile import recover_failed_action
   recover_failed_action(session, agent, action_id="<action_id>")
   ```
5. **Clear Emergency Disable:**
   Once verified, re-enable the safety gate:
   ```bash
   curl -X POST -H "Authorization: Bearer <API_TOKEN>" \
     "http://localhost:8000/api/v1/mitigations/disable?enable=true"
   ```

---

## 3. TC-12: Service Restart Reconciliation & Mismatch Resolution

### Scenario
The SENTRIX backend service restarts (e.g., following a reboot, crash, or deployment). Upon boot, `reconcile_lab_enforcement()` runs before accepting traffic.

### Invariant Rules
- **Orphaned Rules (In Kernel, not in DB):**
  The reconciler automatically deletes the orphaned rule from `nftables` and logs `orphaned_rule_cleaned`.
- **Missing Rules (DB says applied, Kernel has no rule):**
  This indicates external tampering or kernel table wipe. The reconciler flags the action as `failed`, logs `lab_reconciliation_mismatch`, and engages emergency disable immediately.
- **Expired Rules:**
  Rules whose TTL elapsed during downtime are deleted from `nftables` and marked `expired`. If deletion fails, marked `failed`.

### Manual Recovery Steps for Restart Discrepancies
1. **Review Reconciliation Status:**
   Review application startup logs for `TC-12 Mismatch` messages:
   ```bash
   grep "TC-12" /var/log/sentrix/backend.log
   ```
2. **Resynchronize Database State:**
   For any action marked `failed` due to missing kernel state:
   - If the rule is indeed gone and no longer required, recover it using `recover_failed_action()`.
   - If an ongoing threat requires mitigation, allow a new policy pipeline run to propose and apply a fresh, bounded rule.
3. **Re-run Lab Reconciliation:**
   ```python
   from app.mitigation.reconcile import reconcile_lab_enforcement
   result = reconcile_lab_enforcement(session, agent)
   assert result["healthy"] is True
   ```
4. **Restore Safety Gate:**
   Re-enable mitigations via `POST /api/v1/mitigations/disable?enable=true`.
