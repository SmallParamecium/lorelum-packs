#!/usr/bin/env python3
"""Candidate ProjectContext loading and source verification."""

from __future__ import annotations

import os

import yaml

from eval_queries_lore import run_lore


def _read_practice_frontmatter(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    return yaml.safe_load(text[3:end]) or {}


def _candidate_pack_root(project_root: str, pack_name: str) -> str:
    return os.path.join(project_root, ".lorelum", "packs", pack_name)


def _candidate_practice_files(project_root: str, pack_name: str) -> list:
    base = os.path.join(_candidate_pack_root(project_root, pack_name), "practices")
    out = []
    for dirpath, _dirs, files in os.walk(base):
        for fn in files:
            if fn.endswith(".md"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def _lore_failure(action: str, res: dict) -> str:
    err = res.get("error") or {}
    return f"error: lore {action} failed: {err.get('code')}: {err.get('message')}"


def _validate_candidate_pack(lore: str, pack_root: str, store_root: str | None) -> None:
    res = run_lore(lore, ["validate", pack_root], store_root, 120)
    if not res["ok"]:
        raise SystemExit(_lore_failure("validate candidate Pack", res))
    data = res.get("data") or {}
    pack = data.get("pack") or {}
    diagnostics = pack.get("diagnostics") or []
    errors = [d for d in diagnostics if str(d.get("level", "")).lower() == "error"]
    if pack.get("valid") is not True or errors:
        detail = "; ".join(
            f"{d.get('code', 'unknown')}: {d.get('message', '')}" for d in (errors or diagnostics)
        ) or "Pack validation returned valid=false"
        raise SystemExit(f"error: candidate Pack validation failed: {detail}")


def _read_active_candidate_practice(
    lore: str,
    practice_id: str,
    pack_name: str,
    project_root: str,
    store_root: str | None,
) -> dict:
    res = run_lore(lore, ["get", practice_id], store_root, 120, project_root)
    if not res["ok"]:
        raise SystemExit(_lore_failure(f"get {practice_id}", res))
    data = res.get("data") or {}
    practice = data.get("practice") or {}
    if practice.get("id") != practice_id:
        raise SystemExit(
            f"error: lore get {practice_id} returned Practice '{practice.get('id', '')}'"
        )
    project_sources = [
        src for src in (data.get("sources") or [])
        if str(src.get("packName", "")) == pack_name
        and str(src.get("packRoot", "")).startswith("project-layer-")
    ]
    if not project_sources:
        observed = "; ".join(
            f"{src.get('packName')}/{src.get('packRoot')}" for src in (data.get("sources") or [])
        ) or "(no sources)"
        raise SystemExit(
            f"error: lore get {practice_id} did not resolve to the candidate project source; observed: {observed}"
        )
    return {
        "id": practice_id,
        "title": practice.get("title", ""),
        "applies_when": practice.get("applies_when", ""),
    }


def project_pack_details(lore: str, project_root: str, pack_name: str, store_root: str | None) -> dict:
    """Validate and discover a candidate Pack from a ProjectContext.

    Candidate mode proves the source in layers: Pack validation, active project context,
    Practice-set agreement, and one ``lore get`` read for every active Practice. The returned
    shape matches ``installed_pack_details()`` so downstream coverage/discipline/report code
    stays source-agnostic.
    """
    pack_root = _candidate_pack_root(project_root, pack_name)
    pack_yaml = os.path.join(pack_root, "pack.yaml")
    try:
        with open(pack_yaml, encoding="utf-8") as fh:
            pack_meta = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise SystemExit(f"error: cannot read candidate Pack metadata {pack_yaml}: {exc}")
    if str(pack_meta.get("name", "")) != pack_name:
        raise SystemExit(
            f"error: candidate Pack metadata names '{pack_meta.get('name', '')}', expected '{pack_name}'"
        )
    version = str(pack_meta.get("version", ""))

    _validate_candidate_pack(lore, pack_root, store_root)

    res = run_lore(lore, ["context", "status"], store_root, 120, project_root)
    if not res["ok"]:
        raise SystemExit(_lore_failure("context status", res))
    data = res.get("data") or {}
    state = data.get("state")
    if state != "ready":
        raise SystemExit(f"error: candidate ProjectContext is not ready (state: {state or 'missing'})")
    if data.get("base") != "none":
        raise SystemExit(
            f"error: candidate ProjectContext base must be 'none', got '{data.get('base', 'missing')}'"
        )
    warnings = data.get("warnings") or []
    if warnings:
        codes = ", ".join(str(w.get("code", "unknown")) for w in warnings)
        raise SystemExit(f"error: candidate ProjectContext reported warnings: {codes}")

    sources = data.get("sources") or []
    active_sources = [
        src for src in sources
        if str(src.get("scope", "")) == "project"
        and str(src.get("status", "")) == "active"
        and str(src.get("packName", "")) == pack_name
    ]
    if not active_sources:
        observed = "; ".join(
            f"{src.get('scope')}/{src.get('status')}/{src.get('packName')}" for src in sources
        ) or "(no sources)"
        raise SystemExit(
            f"error: no active project source for Pack '{pack_name}'; observed sources: {observed}"
        )

    practices = []
    seen_ids = set()
    for path in _candidate_practice_files(project_root, pack_name):
        fm = _read_practice_frontmatter(path)
        pid = fm.get("id")
        if not pid or not str(pid).startswith(pack_name + "."):
            continue
        pid = str(pid)
        if pid in seen_ids:
            raise SystemExit(f"error: duplicate candidate Practice ID: {pid}")
        seen_ids.add(pid)
        practices.append(pid)
    if not practices:
        raise SystemExit(f"error: no candidate Practices found under {pack_root}")

    file_ids = set(practices)
    active_ids = {
        str(src.get("practiceId"))
        for src in active_sources
        if src.get("practiceId")
    }
    if active_ids:
        if file_ids != active_ids:
            ignored = sorted(file_ids - active_ids)
            unexpected = sorted(active_ids - file_ids)
            parts = []
            if ignored:
                parts.append(f"{len(ignored)} candidate practice file(s) are not active: {', '.join(ignored)}")
            if unexpected:
                parts.append(f"{len(unexpected)} active practice(s) were not found in candidate files: {', '.join(unexpected)}")
            raise SystemExit(
                "error: candidate practice set does not match the active ProjectContext source: " + "; ".join(parts)
            )
    else:
        declared = data.get("practiceCount")
        try:
            declared_count = int(declared)
        except (TypeError, ValueError):
            declared_count = None
        if declared_count != len(file_ids):
            raise SystemExit(
                f"error: context status practiceCount {declared!r} does not match "
                f"{len(file_ids)} candidate Practice files under {pack_root}"
            )
        active_ids = file_ids

    runtime_practices = [
        _read_active_candidate_practice(lore, pid, pack_name, project_root, store_root)
        for pid in sorted(active_ids)
    ]
    return {
        "name": pack_name,
        "version": version,
        "practice_ids": sorted(p["id"] for p in runtime_practices),
        "practices": runtime_practices,
        "candidate_checks": {
            "pack_validated": True,
            "context_state": state,
            "context_base": data.get("base"),
            "practice_files": len(file_ids),
            "practice_get_verified": len(runtime_practices),
        },
    }
