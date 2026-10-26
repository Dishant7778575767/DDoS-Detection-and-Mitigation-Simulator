"""Privileged Linux enforcement agent executing safe, bounded nftables operations."""

from __future__ import annotations

import logging
import subprocess
import time
from typing import Any

from enforcement.rules import (
    NFTABLES_TABLE_NAME,
    build_nftables_apply_commands,
    build_nftables_delete_rule_command,
    build_nftables_flush_table_command,
    build_nftables_init_commands,
    parse_nftables_rules_output,
    validate_enforcement_bounds,
    validate_lab_target,
)

logger = logging.getLogger("sentrix.enforcement.agent")


class EnforcementExecutionError(RuntimeError):
    """Raised when an nftables system command fails."""


class CleanupVerificationError(RuntimeError):
    """Raised when a rule removal operation cannot be verified (TC-10)."""


class LinuxEnforcementAgent:
    """Privileged agent executing restricted nftables commands in the isolated lab namespace."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._in_memory_rules: list[dict[str, Any]] = []

    def _run_cmd(self, cmd: list[str]) -> str:
        """Execute a single parameterized command without invoking a shell."""
        logger.debug("Executing enforcement command: %s", " ".join(cmd))
        if self.dry_run:
            return ""

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=5.0,
            )
            if res.returncode != 0:
                raise EnforcementExecutionError(
                    f"Command '{' '.join(cmd)}' failed with code {res.returncode}: {res.stderr.strip()}"
                )
            return res.stdout
        except subprocess.TimeoutExpired as exc:
            raise EnforcementExecutionError(f"Command '{' '.join(cmd)}' timed out") from exc
        except FileNotFoundError as exc:
            raise EnforcementExecutionError(
                f"Binary '{cmd[0]}' not found. Ensure nftables is installed."
            ) from exc

    def initialize(self) -> None:
        """Initialize the dedicated SENTRIX table and forward hook chain."""
        for cmd in build_nftables_init_commands():
            try:
                self._run_cmd(cmd)
            except EnforcementExecutionError as exc:
                # If table already exists, continue gracefully
                if "exists" in str(exc).lower():
                    continue
                raise

    def apply_rate_limit(
        self,
        action_id: str,
        target_ip: str,
        rate_limit_pps: int,
        duration_seconds: int,
    ) -> dict[str, Any]:
        """Apply a bounded rate-limiting rule to the lab interface."""
        # 1. Enforce strict isolation and bounds
        validated_ip = validate_lab_target(target_ip)
        validate_enforcement_bounds(rate_limit_pps, duration_seconds)

        # 2. Execute commands
        cmds = build_nftables_apply_commands(action_id, validated_ip, rate_limit_pps)
        for cmd in cmds:
            self._run_cmd(cmd)

        now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result = {
            "action_id": action_id,
            "target_ip": validated_ip,
            "rate_limit_pps": rate_limit_pps,
            "duration_seconds": duration_seconds,
            "mode": "lab",
            "host_networking_modified": True,
            "status": "applied",
            "applied_at": now_utc,
            "handle": len(self._in_memory_rules) + 1,
        }

        self._in_memory_rules.append(result)
        return result

    def list_active_rules(self) -> list[dict[str, Any]]:
        """Query kernel nftables state for active SENTRIX rules."""
        if self.dry_run:
            return list(self._in_memory_rules)

        list_cmd = ["nft", "-a", "list", "table", "inet", NFTABLES_TABLE_NAME]
        try:
            output = self._run_cmd(list_cmd)
            return parse_nftables_rules_output(output)
        except EnforcementExecutionError:
            return []

    def verify_rule_removed(self, action_id: str) -> bool:
        """Verify that all rules tagged with sentrix:{action_id} are deleted."""
        active = self.list_active_rules()
        for r in active:
            if r.get("action_id") == action_id:
                return False
        return True

    def cancel_rate_limit(self, action_id: str, target_ip: str) -> dict[str, Any]:
        """Cancel an applied rule and verify that it was removed (TC-10 safeguard)."""
        active = self.list_active_rules()
        matching_rules = [r for r in active if r.get("action_id") == action_id]

        # Delete each matching rule by its handle
        for r in matching_rules:
            handle = r.get("handle", 1)
            del_cmd = build_nftables_delete_rule_command(handle)
            self._run_cmd(del_cmd)

        if self.dry_run:
            self._in_memory_rules = [
                r for r in self._in_memory_rules if r.get("action_id") != action_id
            ]

        # Verify removal
        if not self.verify_rule_removed(action_id):
            raise CleanupVerificationError(
                f"Cleanup verification failed: rule for action '{action_id}' still present in nftables."
            )

        now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return {
            "action_id": action_id,
            "target_ip": target_ip,
            "mode": "lab",
            "host_networking_modified": True,
            "status": "cancelled",
            "cancelled_at": now_utc,
        }

    def flush_sentrix_table(self) -> None:
        """Delete only the dedicated SENTRIX nftables table (preserves all unrelated firewall rules)."""
        cmd = build_nftables_flush_table_command()
        try:
            self._run_cmd(cmd)
        except EnforcementExecutionError as exc:
            if "no such" in str(exc).lower():
                return
            raise
        self._in_memory_rules.clear()
