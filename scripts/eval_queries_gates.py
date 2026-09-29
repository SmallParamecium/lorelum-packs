#!/usr/bin/env python3
"""Run-policy and gate records for retrieval evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunPolicy:
    formal: bool
    limit: int | None
    min_top3: float | None
    min_top3_source: str | None


@dataclass(frozen=True)
class GateFailure:
    gate: str
    message: str


def resolve_run_policy(args, fixture_doc: dict) -> RunPolicy:
    """Resolve complete-run gate policy without treating discipline as complete-run-only."""
    complete_gate_requested = bool(
        args.require_coverage
        or args.require_frozen
        or args.fail_on_baseline_regression
        or args.min_top3 is not None
    )
    if args.limit is not None:
        min_top3, min_top3_source = None, "partial-run"
    elif args.min_top3 is not None:
        min_top3, min_top3_source = args.min_top3, "flag"
    elif fixture_doc.get("min_top3") is not None:
        min_top3, min_top3_source = float(fixture_doc["min_top3"]), "fixture"
    else:
        min_top3, min_top3_source = None, None
    formal = args.limit is None and (complete_gate_requested or min_top3 is not None)
    return RunPolicy(formal=formal, limit=args.limit, min_top3=min_top3, min_top3_source=min_top3_source)


def limit_conflicts_with_formal_gates(args) -> bool:
    return args.limit is not None and bool(
        args.require_coverage
        or args.require_frozen
        or args.fail_on_baseline_regression
        or args.min_top3 is not None
    )
