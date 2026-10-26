# SENTRIX Isolated Linux Lab Enforcement Guide

## 1. Overview & Operational Scope

Phase 6 implements restricted network enforcement using Linux `nftables` and `tc` (Traffic Control). In accordance with PRD Section 8.4 and Section 11 (Environment C), enforcement is **strictly limited to a designated isolated Linux lab environment**.

> [!CAUTION]
> Enforcement must **never** be executed on production networks, public infrastructure, or general-purpose host interfaces. Simulation mode remains the default across all other environments.

---

## 2. Lab Network Architecture & Isolation Boundary

The isolated lab consists of an isolated Linux network namespace or dedicated hypervisor VM connected via host-only virtual Ethernet (`veth`) pairs:

```
+-------------------------------------------------------------------+
|                        Linux Lab Host                             |
|                                                                   |
|   +-----------------------+           +-----------------------+   |
|   |   FastAPI Backend     |           |   Privileged Agent    |   |
|   |   (Unprivileged)      |  IPC/UDS  |   (Root / CAP_NET_*)  |   |
|   |   Port 8000           |<--------->|   enforcement/agent.py|   |
|   +-----------------------+           +-----------------------+   |
|                                                   |               |
|                                        nftables / tc rules        |
|                                                   v               |
|   +-----------------------------------------------------------+   |
|   | Designated Interface: sentrix0 (veth_lab)                |   |
|   | Permitted Subnet:     10.200.0.0/24                       |   |
|   | Target Range:         10.200.0.10 - 10.200.0.250          |   |
|   +-----------------------------------------------------------+   |
+-------------------------------------------------------------------+
```

### Strict Isolation Rules
1. **Designated Interface Only**: Enforcement commands target exclusively `sentrix0` (or `veth_lab`).
2. **Designated Subnet Only**: Mitigation targets are strictly validated against `10.200.0.0/24`. Any IP outside this subnet (including public IP space, RFC 1918 LANs `192.168.0.0/16`, `10.0.0.0/8`, loopback, or gateways) is denied by the Safety Gate.
3. **No External Routing**: The lab namespace has no default gateway or NAT forwarding to external physical adapters. Lab traffic cannot reach public networks or third parties.

---

## 3. Threat Model & Safeguards

### Threat Vectors & Mitigations
| Threat Vector | Mitigation Strategy |
| :--- | :--- |
| **Command Injection** | No raw shell commands (`shell=True`) are accepted. The privileged agent accepts only strongly-typed, schema-validated policy objects. |
| **Privilege Escalation** | FastAPI runs as an unprivileged service (`sentrix-app`). Only the standalone `enforcement/agent.py` daemon holds `CAP_NET_ADMIN` privileges. |
| **Collateral Firewall Damage** | All SENTRIX rules reside in a dedicated, isolated nftables table: `table inet sentrix_mitigation`. Default system chains (`filter`, `mangle`, `nat`) are never flushed or modified. |
| **Rule Abandonment / Leakage** | Every applied rule has a hardware TTL. An automated expiry daemon (`enforcement/expiry.py`) verifies rule removal. If removal fails, the system fails closed (TC-10). |
| **Restart State Desynchronization** | On startup, `reconcile_lab_enforcement()` audits in-kernel nftables state against the SQLite database. Any discrepancy keeps enforcement locked in disabled mode (TC-12). |

---

## 4. Required Authorization & Lab Enablement Gate

Lab enforcement cannot be activated unless **all** of the following conditions are met:
1. `APP_ENV=lab` and `MITIGATION_MODE=lab` are explicitly configured in the environment.
2. A valid, unexpired approval manifest exists at `enforcement/approval.json` signed by the designated security authority.
3. All Phase 5 simulation gate tests have passed.
4. Restart state reconciliation confirms zero unmanaged or orphaned rules.
