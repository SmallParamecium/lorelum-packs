#!/usr/bin/env python3
"""Baseline compatibility validation and regression comparison."""

from __future__ import annotations



def compare_baseline(current: list, baseline_results: list, top_k: int, fixture_queries: dict) -> dict:
    baseline_ids = {r["id"] for r in baseline_results if r.get("id")}
    base = {r["id"]: r for r in baseline_results if not r.get("error") and r.get("id")}
    regressions, improvements = [], []
    migrations, migration_failures, mismatches = [], [], []
    common = 0
    for r in current:
        b = base.get(r["id"])
        if not b or r["error"]:
            continue
        common += 1
        q = fixture_queries.get(r["id"], {})
        if b.get("text") and b.get("text") != r.get("text"):
            mismatches.append({
                "id": r["id"],
                "reason": "Query text changed while reusing the baseline Query ID; retire the old Query and add a new ID",
            })
            continue
        expected_changed = b.get("expect") != r.get("expect")
        if expected_changed:
            valid_migration = (
                q.get("previous_expect") == b.get("expect")
                and q.get("expect") == r.get("expect")
            )
            if not valid_migration:
                mismatches.append({
                    "id": r["id"],
                    "baseline_expect": b.get("expect"),
                    "current_expect": r.get("expect"),
                    "reason": "expected Practice changed without matching previous_expect migration metadata",
                })
                continue
            now_hit = r["hit_rank"] is not None and r["hit_rank"] <= top_k
            row = {
                "id": r["id"],
                "previous_expect": b.get("expect"),
                "expect": r.get("expect"),
                "baseline_rank": b.get("hit_rank"),
                "now_rank": r.get("hit_rank"),
                "migration_kind": q.get("migration_kind"),
            }
            migrations.append(row)
            if not now_hit:
                migration_failures.append(row)
            continue
        was_hit = b.get("hit_rank") is not None and b["hit_rank"] <= top_k
        now_hit = r["hit_rank"] is not None and r["hit_rank"] <= top_k
        if was_hit and not now_hit:
            regressions.append({"id": r["id"], "baseline_rank": b["hit_rank"], "now": r["hits"][:top_k]})
        elif now_hit and not was_hit:
            improvements.append({"id": r["id"], "now_rank": r["hit_rank"]})
    retired_ids = {
        q["id"] for q in fixture_queries.values()
        if q.get("status", "frozen") == "retired"
    }
    baseline_only = sorted(baseline_ids - set(fixture_queries))
    return {
        "common_queries": common,
        "regressions": regressions,
        "improvements": improvements,
        "migrations": migrations,
        "migration_failures": migration_failures,
        "expect_mismatches": mismatches,
        "retired_queries": sorted(set(base) & retired_ids),
        "unaccounted_baseline_queries": baseline_only,
    }



def baseline_compatibility_errors(baseline: dict, pack_name: str, fixture_set: str, top_k: int, modes: list) -> list:
    """Reject absent or incompatible evidence rather than treating it as zero regressions."""
    if not isinstance(baseline, dict):
        return ["baseline must be a JSON object"]
    errors = []
    pack = baseline.get("pack")
    if not isinstance(pack, dict) or pack.get("name") != pack_name:
        errors.append(f"baseline Pack must be {pack_name}")
    if baseline.get("fixture_set") != fixture_set:
        errors.append(f"baseline fixture_set must be {fixture_set}")
    if baseline.get("top_k") != top_k:
        errors.append(f"baseline top_k must be {top_k}")
    totals = baseline.get("totals")
    runnable = totals.get("runnable") if isinstance(totals, dict) else None
    if not isinstance(runnable, int) or isinstance(runnable, bool) or runnable <= 0:
        errors.append("baseline totals.runnable must be a positive integer")
        runnable = None
    if baseline.get("partial_run") is True or baseline.get("limit") is not None:
        errors.append("baseline must be a complete run")
    sections = baseline.get("modes")
    if not isinstance(sections, dict):
        return errors + ["baseline modes must be an object"]
    for mode in modes:
        section = sections.get(mode)
        rows = section.get("results") if isinstance(section, dict) else None
        if not isinstance(rows, list) or not rows:
            errors.append(f"baseline {mode} mode needs non-empty results")
            continue
        if runnable is not None and len(rows) != runnable:
            errors.append(f"baseline {mode} has {len(rows)} results, expected {runnable} runnable Queries")
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                errors.append(f"baseline {mode} has a non-object result")
                continue
            qid = row.get("id")
            required = ("id", "expect", "text", "hit_rank", "hits", "error")
            missing = [field for field in required if field not in row or (field in ("id", "expect", "text") and not row[field])]
            if missing:
                errors.append(f"baseline {mode} result {qid or '(missing id)'} missing {', '.join(missing)}")
            if any(not isinstance(row.get(field), str) or not row[field].strip() for field in ("id", "expect", "text")):
                errors.append(f"baseline {mode} has an invalid Query identity, expectation or text")
                continue
            if qid in seen:
                errors.append(f"baseline {mode} has duplicate Query ID {qid}")
            seen.add(qid)
            if row.get("error"):
                errors.append(f"baseline {mode} result {qid} has a Query error")
            if "hits" in row and not isinstance(row["hits"], list):
                errors.append(f"baseline {mode} result {qid} has invalid hits")
            rank = row.get("hit_rank")
            if rank is not None and (not isinstance(rank, int) or isinstance(rank, bool) or rank < 1):
                errors.append(f"baseline {mode} result {qid} has invalid hit_rank")
    return errors
