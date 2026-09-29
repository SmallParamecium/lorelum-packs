#!/usr/bin/env python3
"""Subprocess boundary for the lore CLI used by retrieval evaluation."""

from __future__ import annotations

import json
import subprocess


def run_lore(lore: str, args: list, store_root: str | None, timeout: float, project_root: str | None = None) -> dict:
    """Run one lore CLI invocation and return ``{"ok", "data"/"error", ...}``."""
    cmd = [lore, "--json"]
    if store_root:
        cmd += ["--store-root", store_root]
    if project_root:
        cmd += ["--project-root", project_root]
    cmd += args
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": {"code": "harness.timeout", "message": f"lore {' '.join(args[0:2])} timed out"}, "exit": -1, "raw": ""}
    except OSError as exc:
        return {"ok": False, "error": {"code": "harness.exec-failed", "message": str(exc)}, "exit": -1, "raw": ""}
    payload = None
    start = proc.stdout.find("{")
    if start >= 0:
        try:
            payload = json.loads(proc.stdout[start:])
        except json.JSONDecodeError:
            payload = None
    if payload is None:
        return {
            "ok": False,
            "error": {"code": "harness.no-json", "message": (proc.stderr or proc.stdout).strip()[:400]},
            "exit": proc.returncode,
            "raw": proc.stdout,
        }
    payload.setdefault("ok", False)
    return {
        "ok": bool(payload.get("ok")),
        "data": payload.get("data"),
        "error": payload.get("error"),
        "exit": proc.returncode,
        "raw": proc.stdout,
    }
