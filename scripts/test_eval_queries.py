#!/usr/bin/env python3
"""Unit tests for scripts/eval-queries.

Loads the extension-less script with importlib and monkeypatches its CLI boundary
so candidate loading, migration policy, and baseline gating can be tested without
requiring a real lore CLI installation.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "eval-queries")


def _load_module():
    loader = importlib.machinery.SourceFileLoader("eval_queries_under_test", SCRIPT)
    spec = importlib.util.spec_from_loader("eval_queries_under_test", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


MOD = _load_module()
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import eval_queries_candidate
import eval_queries_lore


class _Proc:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _make_candidate_project(root, version="0.6.0", extra_practices=()):
    root_pack = os.path.join(root, ".lorelum", "packs", "agentic-coding")
    _write(os.path.join(root_pack, "pack.yaml"), f"name: agentic-coding\nversion: {version}\n")
    practices = [("foo", "Foo Practice Title", "when you need a foo decision"), *extra_practices]
    for slug, title, applies in practices:
        _write(
            os.path.join(root_pack, "practices", "context", f"{slug}.md"),
            f"---\nid: agentic-coding.context.{slug}\ntitle: {title}\napplies_when: {applies}\n---\nbody text\n",
        )


def _validation(valid=True):
    return {"ok": True, "data": {"pack": {"valid": valid, "diagnostics": []}}}


def _context_status(sources, state="ready", base="none", warnings=None):
    return {
        "ok": True,
        "data": {
            "state": state,
            "base": base,
            "practiceCount": len([s for s in sources if s.get("practiceId")]),
            "sources": sources,
            "warnings": warnings or [],
        },
    }


def _get_practice(practice_id, pack_name="agentic-coding", pack_root="project-layer-1"):
    return {
        "ok": True,
        "data": {
            "practice": {
                "id": practice_id,
                "title": "Foo Practice Title",
                "applies_when": "when you need a foo decision",
                "body": "body text",
            },
            "contentDigest": "digest",
            "sources": [{"packName": pack_name, "sourcePath": "practice.md", "packRoot": pack_root}],
        },
    }


def _candidate_sources(ids=("agentic-coding.context.foo",)):
    return [
        {"scope": "project", "status": "active", "packName": "agentic-coding", "practiceId": pid}
        for pid in ids
    ]


class RunLoreTests(unittest.TestCase):
    def test_json_and_project_root_are_forwarded(self):
        with mock.patch.object(eval_queries_lore.subprocess, "run", return_value=_Proc('{"ok": true, "data": {}}')) as run:
            eval_queries_lore.run_lore("lore", ["query", "x"], None, 60)
            self.assertEqual(run.call_args[0][0], ["lore", "--json", "query", "x"])
        with mock.patch.object(eval_queries_lore.subprocess, "run", return_value=_Proc('{"ok": true, "data": {}}')) as run:
            eval_queries_lore.run_lore("lore", ["query", "x"], "/store", 60, "/proj")
            self.assertEqual(run.call_args[0][0], ["lore", "--json", "--store-root", "/store", "--project-root", "/proj", "query", "x"])


class ProjectPackDetailsTests(unittest.TestCase):
    def _run_valid(self, root, sources=None, get_result=None, validation=None):
        sources = sources or _candidate_sources()
        get_result = get_result or _get_practice("agentic-coding.context.foo")
        validation = validation or _validation()

        def fake_run(lore, args, store_root, timeout, project_root=None):
            if args and args[0] == "validate":
                return validation
            if args == ["context", "status"]:
                return _context_status(sources)
            if args[:1] == ["get"]:
                return get_result
            raise AssertionError(f"unexpected lore args: {args}")

        with mock.patch.object(eval_queries_candidate, "run_lore", side_effect=fake_run):
            return MOD.project_pack_details("lore", root, "agentic-coding", "/store")

    def test_filters_active_project_source_and_reads_version(self):
        with tempfile.TemporaryDirectory() as root:
            _make_candidate_project(root)
            pack = self._run_valid(root, sources=[
                {"scope": "store", "status": "active", "packName": "agentic-coding"},
                *_candidate_sources(),
                {"scope": "project", "status": "inactive", "packName": "agentic-coding"},
            ])
            self.assertEqual(pack["version"], "0.6.0")
            self.assertEqual(pack["practice_ids"], ["agentic-coding.context.foo"])
            self.assertEqual(pack["candidate_checks"]["practice_get_verified"], 1)

    def test_fails_when_candidate_validation_is_invalid(self):
        with tempfile.TemporaryDirectory() as root:
            _make_candidate_project(root)
            with self.assertRaisesRegex(SystemExit, "validation failed"):
                self._run_valid(root, validation=_validation(False))

    def test_fails_when_context_is_degraded(self):
        with tempfile.TemporaryDirectory() as root:
            _make_candidate_project(root)
            def fake_run(lore, args, store_root, timeout, project_root=None):
                if args[0] == "validate":
                    return _validation()
                return _context_status(_candidate_sources(), state="degraded")
            with mock.patch.object(eval_queries_candidate, "run_lore", side_effect=fake_run):
                with self.assertRaisesRegex(SystemExit, "not ready"):
                    MOD.project_pack_details("lore", root, "agentic-coding", "/store")

    def test_fails_when_get_resolves_to_store_source(self):
        with tempfile.TemporaryDirectory() as root:
            _make_candidate_project(root)
            with self.assertRaisesRegex(SystemExit, "did not resolve"):
                self._run_valid(root, get_result=_get_practice("agentic-coding.context.foo", pack_root="store"))

    def test_fails_when_no_active_project_source(self):
        with tempfile.TemporaryDirectory() as root:
            _make_candidate_project(root)
            with self.assertRaisesRegex(SystemExit, "no active project source"):
                self._run_valid(root, sources=[{"scope": "store", "status": "active", "packName": "agentic-coding"}])

    def test_fails_when_active_practice_set_mismatches_files(self):
        with tempfile.TemporaryDirectory() as root:
            _make_candidate_project(root)
            with self.assertRaisesRegex(SystemExit, "does not match"):
                self._run_valid(root, sources=_candidate_sources(("agentic-coding.context.other",)))


class MainArgTests(unittest.TestCase):
    def test_project_root_and_ensure_install_are_mutually_exclusive(self):
        with mock.patch.object(sys, "argv", ["eval-queries", "--project-root", "/x", "--ensure-install", "agentic-coding@0.4.0"]):
            with self.assertRaises(SystemExit) as cm:
                MOD.main()
        self.assertEqual(cm.exception.code, 2)


class MetricsTests(unittest.TestCase):
    def test_query_errors_count_as_misses_in_metric_denominator(self):
        results = [
            {"id": "hit", "kind": "positive", "expect": "p", "hits": ["p"], "hit_rank": 1, "error": None},
            {"id": "error", "kind": "positive", "expect": "p", "hits": [], "hit_rank": None, "error": "query.failed: boom"},
        ]
        metrics = MOD.compute_metrics(results, 3)
        self.assertEqual(metrics["positive"]["n"], 2)
        self.assertEqual(metrics["positive"]["top1_rate"], 0.5)
        self.assertEqual(metrics["positive"]["top3_rate"], 0.5)
        self.assertEqual(metrics["errored_queries"], ["error"])

    def test_confusion_uses_each_neighbor_expected_target(self):
        results = [
            {
                "id": "first",
                "kind": "neighbor",
                "expect": "target-a",
                "resembles": "shared-trap",
                "hits": ["target-b"],
                "hit_rank": None,
                "error": None,
            },
            {
                "id": "second",
                "kind": "neighbor",
                "expect": "target-b",
                "resembles": "shared-trap",
                "hits": ["target-b"],
                "hit_rank": 1,
                "error": None,
            },
        ]
        metrics = MOD.compute_metrics(results, 3)
        self.assertEqual(metrics["confusion_matrix"]["shared-trap"]["target-b"], 2)
        self.assertEqual(metrics["worst_confused_pairs"], [{
            "resembles": "shared-trap", "actual_top1": "target-b", "count": 1
        }])


class DisciplineTests(unittest.TestCase):
    def test_retired_query_is_excluded_from_discipline_gate(self):
        doc = {"queries": [{
            "id": "retired",
            "kind": "positive",
            "status": "retired",
            "expect": "p",
            "retired_reason": "replaced",
            "text": "must preserve the frozen query baseline",
        }]}
        practices = [{
            "id": "p",
            "title": "P",
            "applies_when": "must preserve the frozen query baseline",
        }]
        self.assertEqual(MOD.discipline_violations(MOD._active_queries(doc), practices), [])
        self.assertTrue(MOD.discipline_violations(doc["queries"], practices))


class BaselineRegressionTests(unittest.TestCase):
    def _make_fixture(self, root, status="frozen", expect="agentic-coding.context.foo"):
        path = os.path.join(root, "queries.yaml")
        _write(path, "fixture_set: t\ntarget_pack: agentic-coding@0.5.0\nqueries:\n"
                "  - id: q1\n    kind: positive\n    status: " + status + "\n"
                "    expect: " + expect + "\n    text: what should i do for a foo decision\n")
        return path

    def _make_baseline(self, root):
        path = os.path.join(root, "baseline.json")
        baseline = {"fixture_set": "t", "top_k": 3, "pack": {"name": "agentic-coding", "version": "0.5.0"},
                    "totals": {"runnable": 1, "skipped": 0}, "modes": {"keyword": {"results": [{
            "id": "q1", "kind": "positive", "expect": "agentic-coding.context.foo", "text": "what should i do for a foo decision",
            "hits": ["agentic-coding.context.foo"], "hit_rank": 1, "error": None,
        }]}}}
        _write(path, json.dumps(baseline))
        return path

    def _run(self, proj, fixture, baseline, fail, extra=(), query_result=None):
        argv = ["eval-queries", "--lore", "lore", "--project-root", proj, "--fixtures", fixture, "--mode", "keyword", "--baseline", baseline, *extra]
        if fail:
            argv.append("--fail-on-baseline-regression")
        def fake_run(lore, args, store_root, timeout, project_root=None):
            if args == ["--version"]:
                return {"ok": True, "data": {"toolVersion": "0.1.0-alpha.3"}}
            if args[0] == "validate":
                return _validation()
            if args == ["context", "status"]:
                return _context_status(_candidate_sources())
            if args[:1] == ["get"]:
                return _get_practice(args[1])
            if args[0] == "query":
                return query_result or {"ok": True, "data": {"results": []}}
            raise AssertionError(f"unexpected lore args: {args}")
        with mock.patch.object(sys, "argv", argv), mock.patch.object(eval_queries_candidate, "run_lore", side_effect=fake_run), mock.patch.object(MOD, "run_lore", side_effect=fake_run):
            return MOD.main()

    def test_fail_on_regression_returns_one(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            self.assertEqual(self._run(proj, self._make_fixture(root), self._make_baseline(root), True), 1)

    def test_without_flag_returns_zero(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            self.assertEqual(self._run(proj, self._make_fixture(root), self._make_baseline(root), False), 0)

    def test_formal_gate_rejects_missing_query_target(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            fixture = self._make_fixture(root, expect="agentic-coding.context.missing")
            self.assertEqual(self._run(proj, fixture, self._make_baseline(root), False, ("--require-frozen",)), 1)

    def test_formal_gate_rejects_query_execution_error(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            error = {"ok": False, "error": {"code": "query.failed", "message": "boom"}}
            self.assertEqual(self._run(proj, self._make_fixture(root), self._make_baseline(root), False, ("--require-frozen",), error), 1)

    def test_require_frozen_rejects_missing_status(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            fixture = self._make_fixture(root)
            with open(fixture, encoding="utf-8") as fh:
                text = fh.read().replace("    status: frozen\n", "")
            _write(fixture, text)
            self.assertEqual(self._run(proj, fixture, self._make_baseline(root), False, ("--require-frozen",)), 1)


    def test_formal_gate_uses_error_in_top3_denominator_and_fails(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            fixture = self._make_fixture(root)
            with open(fixture, encoding="utf-8") as fh:
                text = fh.read()
            _write(fixture, text + "  - id: q2\n    kind: positive\n    status: frozen\n"
                   "    expect: agentic-coding.context.foo\n    text: another foo decision\n")
            out = os.path.join(root, "run.json")
            count = 0
            def fake_query(lore, args, store_root, timeout, project_root=None):
                nonlocal count
                count += 1
                if count == 1:
                    return {"ok": True, "data": {"results": [{"practiceId": "agentic-coding.context.foo"}]}}
                return {"ok": False, "error": {"code": "query.failed", "message": "boom"}}
            # Use the same candidate test harness, but a distinct result per Query.
            def fake_run(lore, args, store_root, timeout, project_root=None):
                if args == ["--version"]: return {"ok": True, "data": {"toolVersion": "test"}}
                if args[0] == "validate": return _validation()
                if args == ["context", "status"]: return _context_status(_candidate_sources())
                if args[0] == "get": return _get_practice(args[1])
                if args[0] == "query": return fake_query(lore, args, store_root, timeout, project_root)
                raise AssertionError(args)
            argv = ["eval-queries", "--project-root", proj, "--fixtures", fixture, "--mode", "keyword",
                    "--min-top3", "0.75", "--require-frozen", "--out", out]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(eval_queries_candidate, "run_lore", side_effect=fake_run), mock.patch.object(MOD, "run_lore", side_effect=fake_run):
                self.assertEqual(MOD.main(), 1)
            with open(out, encoding="utf-8") as fh: run = json.load(fh)
            self.assertEqual(run["modes"]["keyword"]["metrics"]["positive"]["top3_rate"], 0.5)
            self.assertEqual(run["modes"]["keyword"]["gate"]["observed"], 0.5)
            self.assertEqual({f["gate"] for f in run["gate_failures"]}, {"min-top3", "query-errors"})

    def test_top3_gate_stays_top3_when_metric_top_k_is_five(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            out = os.path.join(root, "run.json")
            result = {"ok": True, "data": {"results": [
                {"practiceId": f"other.{i}"} for i in range(3)
            ] + [{"practiceId": "agentic-coding.context.foo"}]}}
            self.assertEqual(self._run(
                proj, self._make_fixture(root), self._make_baseline(root), False,
                ("--top-k", "5", "--min-top3", "0.90", "--out", out), result,
            ), 1)
            with open(out, encoding="utf-8") as fh:
                run = json.load(fh)
            section = run["modes"]["keyword"]
            self.assertEqual(section["metrics"]["positive"]["top5_rate"], 1.0)
            self.assertEqual(section["gate"]["observed"], 0.0)
            self.assertFalse(section["gate"]["passed"])

    def test_partial_run_never_claims_fixture_gate_pass(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            fixture = self._make_fixture(root)
            with open(fixture, encoding="utf-8") as fh: text = fh.read()
            _write(fixture, text.replace("queries:\n", "min_top3: 0.90\nqueries:\n", 1))
            out, report = os.path.join(root, "run.json"), os.path.join(root, "run.md")
            self.assertEqual(self._run(proj, fixture, self._make_baseline(root), False,
                                       ("--limit", "1", "--check-discipline", "--out", out, "--report", report)), 0)
            with open(out, encoding="utf-8") as fh: run = json.load(fh)
            with open(report, encoding="utf-8") as fh: text = fh.read()
            self.assertTrue(run["partial_run"])
            self.assertEqual(run["min_top3"], {"value": None, "source": "partial-run"})
            self.assertNotIn("gate", run["modes"]["keyword"])
            self.assertIn("NOT EVALUATED", text)
            self.assertNotIn("gate PASSED", text)

    def test_limit_conflicts_with_formal_flags(self):
        for flag in (("--require-coverage",), ("--require-frozen",),
                     ("--fail-on-baseline-regression",), ("--min-top3", "0.9")):
            with self.subTest(flag=flag), mock.patch.object(sys, "argv", ["eval-queries", "--limit", "1", "--baseline", "baseline.json", *flag]):
                self.assertEqual(MOD.main(), 2)

    def test_formal_gate_rejects_candidate_and_reviewed_status(self):
        for status in ("candidate", "reviewed"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as root:
                proj = os.path.join(root, "proj"); _make_candidate_project(proj)
                self.assertEqual(self._run(proj, self._make_fixture(root, status=status),
                                           self._make_baseline(root), False, ("--require-frozen",)), 1)

    def test_strict_baseline_needs_compatible_evidence(self):
        changes = {
            "missing-mode": lambda b: b["modes"].pop("keyword"),
            "empty-mode": lambda b: b["modes"]["keyword"].update(results=[]),
            "truncated-mode": lambda b: b["totals"].update(runnable=2),
            "missing-totals": lambda b: b.pop("totals"),
            "partial-run": lambda b: b.update(partial_run=True),
            "wrong-pack": lambda b: b["pack"].update(name="other"),
            "wrong-fixture": lambda b: b.update(fixture_set="other"),
            "wrong-top-k": lambda b: b.update(top_k=5),
            "errored-result": lambda b: b["modes"]["keyword"]["results"][0].update(error="boom"),
        }
        for name, change in changes.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as root:
                proj = os.path.join(root, "proj"); _make_candidate_project(proj)
                baseline = self._make_baseline(root)
                with open(baseline, encoding="utf-8") as fh: data = json.load(fh)
                change(data); _write(baseline, json.dumps(data))
                self.assertEqual(self._run(proj, self._make_fixture(root), baseline, True), 1)

    def test_truncated_baseline_reports_schema_failure(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            baseline = self._make_baseline(root)
            with open(baseline, encoding="utf-8") as fh: data = json.load(fh)
            data["totals"]["runnable"] = 2  # A recorded second result was dropped.
            _write(baseline, json.dumps(data))
            out = os.path.join(root, "run.json")
            self.assertEqual(self._run(proj, self._make_fixture(root), baseline, True, ("--out", out)), 1)
            with open(out, encoding="utf-8") as fh: run = json.load(fh)
            self.assertIn("baseline-schema", [f["gate"] for f in run["gate_failures"]])
            self.assertIn("expected 2 runnable Queries", run["gate_failures"][0]["message"])

    def test_baseline_query_retirement_is_recorded_not_silently_removed(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            baseline = self._make_baseline(root)
            fixture = self._make_fixture(root)
            with open(fixture, encoding="utf-8") as fh: original = fh.read()
            replacement = ("  - id: q2\n    kind: positive\n    status: frozen\n"
                           "    expect: agentic-coding.context.foo\n    text: a new narrow foo scenario\n")
            _write(fixture, original.replace("status: frozen", "status: retired\n    retired_reason: over-broad", 1) + replacement)
            out = os.path.join(root, "run.json")
            self.assertEqual(self._run(proj, fixture, baseline, True, ("--out", out,)), 0)
            with open(out, encoding="utf-8") as fh: run = json.load(fh)
            self.assertIn("q1", run["modes"]["keyword"]["regression"]["retired_queries"])
            _write(fixture, original.replace("  - id: q1", "  - id: q2")
                   .replace("what should i do for a foo decision", "a new narrow foo scenario"))
            self.assertEqual(self._run(proj, fixture, baseline, True), 1)

    def test_strict_baseline_rejects_same_id_rewording(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            fixture = self._make_fixture(root)
            with open(fixture, encoding="utf-8") as fh: original = fh.read()
            _write(fixture, original.replace("what should i do for a foo decision", "new semantic decision"))
            self.assertEqual(self._run(proj, fixture, self._make_baseline(root), True), 1)

    def test_fixture_top3_alone_rejects_skipped_query_before_retrieval(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            fixture = self._make_fixture(root, expect="agentic-coding.context.missing")
            with open(fixture, encoding="utf-8") as fh: original = fh.read()
            _write(fixture, original.replace("queries:\n", "min_top3: 0.90\nqueries:\n", 1))
            out = os.path.join(root, "run.json")
            self.assertEqual(self._run(proj, fixture, self._make_baseline(root), False, ("--out", out,)), 1)
            with open(out, encoding="utf-8") as fh: run = json.load(fh)
            self.assertEqual(run["modes"], {})
            self.assertIn("missing-query-target", [f["gate"] for f in run["gate_failures"]])

    def test_strict_baseline_rejects_removed_query_even_with_prior_error(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj"); _make_candidate_project(proj)
            baseline = self._make_baseline(root)
            with open(baseline, encoding="utf-8") as fh: data = json.load(fh)
            removed = dict(data["modes"]["keyword"]["results"][0], id="old", error="boom")
            data["modes"]["keyword"]["results"].append(removed)
            _write(baseline, json.dumps(data))
            self.assertIn("old", MOD.compare_baseline([], data["modes"]["keyword"]["results"], 3,
                                                       {"q1": {}})["unaccounted_baseline_queries"])
            self.assertEqual(self._run(proj, self._make_fixture(root), baseline, True), 1)


class MigrationPolicyTests(unittest.TestCase):
    def test_migrated_query_requires_independent_old_coverage_and_boundary(self):
        doc = {"queries": [{"id": "q", "kind": "positive", "expect": "new", "previous_expect": "old", "migration_kind": "reassign", "migration_reason": "specific", "text": "specific", "status": "frozen"}], "practice_migrations": []}
        failures = MOD.validate_migration_coverage(doc, {"old", "new"})
        self.assertEqual(len(failures), 2)

    def test_migrated_query_passes_with_old_positive_and_boundary(self):
        doc = {"queries": [
            {"id": "m", "kind": "positive", "expect": "new", "previous_expect": "old", "migration_kind": "reassign", "migration_reason": "specific", "text": "specific", "status": "frozen"},
            {"id": "o", "kind": "positive", "expect": "old", "text": "old only", "status": "frozen"},
            {"id": "n", "kind": "neighbor", "expect": "old", "resembles": "new", "text": "boundary", "status": "frozen"},
        ], "practice_migrations": []}
        self.assertEqual(MOD.validate_migration_coverage(doc, {"old", "new"}), [])

    def test_inactive_old_practice_requires_pack_migration_record(self):
        q = {"id": "m", "kind": "positive", "expect": "new", "previous_expect": "old", "migration_kind": "reassign", "migration_reason": "replace", "text": "specific", "status": "frozen"}
        doc = {"queries": [q], "practice_migrations": []}
        self.assertEqual(len(MOD.validate_migration_coverage(doc, {"new"})), 1)
        doc["practice_migrations"] = [{"old_practice": "old", "new_practice": "new", "kind": "replace", "reason": "replaced", "query_ids": ["m"]}]
        self.assertEqual(MOD.validate_migration_coverage(doc, {"new"}), [])

    def test_inactive_old_migration_checks_each_query_id_in_same_pair(self):
        queries = [
            {"id": qid, "kind": "positive", "status": "frozen", "expect": "new",
             "previous_expect": "old", "migration_kind": "merge", "migration_reason": "merged",
             "text": f"query {qid}"}
            for qid in ("q1", "q2")
        ]
        migration = {"old_practice": "old", "new_practice": "new", "kind": "merge",
                     "reason": "merged", "query_ids": ["q1"]}
        doc = {"queries": queries, "practice_migrations": [migration]}
        failures = MOD.validate_migration_coverage(doc, {"new"})
        self.assertEqual([f["query"] for f in failures], ["q2"])
        migration["query_ids"].append("q2")
        self.assertEqual(MOD.validate_migration_coverage(doc, {"new"}), [])

    def test_active_old_boundary_failures_are_reported_once_per_pair(self):
        doc = {"queries": [
            {"id": qid, "kind": "positive", "status": "frozen", "expect": "new",
             "previous_expect": "old", "text": f"query {qid}"}
            for qid in ("q1", "q2")
        ], "practice_migrations": []}
        failures = MOD.validate_migration_coverage(doc, {"old", "new"})
        self.assertEqual(len(failures), 2)
        self.assertEqual({f["query"] for f in failures}, {"q1"})

    def test_retired_migration_still_requires_active_old_coverage(self):
        doc = {"queries": [{"id": "m", "kind": "positive", "expect": "new", "previous_expect": "old", "migration_kind": "merge", "migration_reason": "replace", "text": "specific", "status": "retired", "retired_reason": "replaced"}], "practice_migrations": []}
        self.assertEqual(len(MOD.validate_migration_coverage(doc, {"old", "new"})), 2)

    def test_retired_migration_must_belong_to_old_practice(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "queries.yaml")
            _write(path, "fixture_set: t\npractice_migrations:\n  - old_practice: old\n"
                         "    new_practice: new\n    kind: merge\n    reason: consolidated\n"
                         "    query_ids: [q]\nqueries:\n  - id: q\n    kind: positive\n"
                         "    expect: unrelated\n    status: retired\n    retired_reason: over-broad\n"
                         "    text: broad query\n")
            with self.assertRaisesRegex(ValueError, "belong to old Practice"):
                MOD.load_fixtures(path)

    def test_over_broad_split_references_active_new_ids(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "queries.yaml")
            fixture = ("fixture_set: t\nqueries:\n  - id: old\n    kind: positive\n"
                       "    expect: old-practice\n    status: retired\n    retired_reason: over-broad\n"
                       "    replacement_queries: [new-a, new-b]\n    text: broad old query\n"
                       "  - id: new-a\n    kind: positive\n    status: frozen\n"
                       "    expect: old-practice\n    text: narrow old decision\n"
                       "  - id: new-b\n    kind: positive\n    status: frozen\n"
                       "    expect: new-practice\n    text: narrow new decision\n")
            _write(path, fixture)
            doc = MOD.load_fixtures(path)
            self.assertEqual(MOD.validate_migration_coverage(doc, {"old-practice", "new-practice"}), [])
            _write(path, fixture.replace("[new-a, new-b]", "[new-a, missing]"))
            doc = MOD.load_fixtures(path)
            self.assertIn("missing", MOD.validate_migration_coverage(doc, {"old-practice", "new-practice"})[0]["reason"])

    def test_baseline_accepts_explicit_migration(self):
        fixture = {"q": {"id": "q", "expect": "new", "previous_expect": "old", "migration_kind": "reassign"}}
        current = [{"id": "q", "expect": "new", "text": "same", "hit_rank": 1, "hits": ["new"], "error": None}]
        baseline = [{"id": "q", "expect": "old", "text": "same", "hit_rank": 1, "hits": ["old"], "error": None}]
        result = MOD.compare_baseline(current, baseline, 3, fixture)
        self.assertEqual(len(result["migrations"]), 1); self.assertEqual(result["migration_failures"], [])

    def test_baseline_requires_query_text(self):
        current = [{"id": "q", "expect": "old", "text": "same", "hit_rank": 1, "hits": ["old"], "error": None}]
        baseline = [{"id": "q", "expect": "old", "hit_rank": 1, "hits": ["old"], "error": None}]
        result = MOD.compare_baseline(current, baseline, 3, {"q": {}})
        self.assertEqual(result["baseline_schema_errors"][0]["missing"], ["text"])

    def test_baseline_rejects_unrecorded_expect_change(self):
        current = [{"id": "q", "expect": "new", "text": "same", "hit_rank": 1, "hits": ["new"], "error": None}]
        baseline = [{"id": "q", "expect": "old", "text": "same", "hit_rank": 1, "hits": ["old"], "error": None}]
        self.assertEqual(len(MOD.compare_baseline(current, baseline, 3, {"q": {}})["expect_mismatches"]), 1)

    def test_baseline_rejects_query_text_change_under_same_id(self):
        current = [{"id": "q", "expect": "old", "text": "new wording", "hit_rank": 1, "hits": ["old"], "error": None}]
        baseline = [{"id": "q", "expect": "old", "text": "old wording", "hit_rank": 1, "hits": ["old"], "error": None}]
        result = MOD.compare_baseline(current, baseline, 3, {"q": {}})
        self.assertIn("retire the old Query", result["expect_mismatches"][0]["reason"])

    def test_fixture_requires_migration_query_ids(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "queries.yaml")
            _write(path, "fixture_set: t\npractice_migrations:\n  - old_practice: old\n    new_practice: new\n    kind: merge\n    reason: moved\nqueries:\n  - id: q\n    kind: positive\n    previous_expect: old\n    migration_kind: merge\n    migration_reason: moved\n    expect: new\n    text: a query\n")
            with self.assertRaisesRegex(ValueError, "query_ids"):
                MOD.load_fixtures(path)

    def test_fixture_rejects_unknown_migration_query_id(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "queries.yaml")
            _write(path, "fixture_set: t\npractice_migrations:\n  - old_practice: old\n    new_practice: new\n    kind: merge\n    reason: moved\n    query_ids: [missing]\nqueries:\n  - id: q\n    kind: positive\n    previous_expect: old\n    migration_kind: merge\n    migration_reason: moved\n    expect: new\n    text: a query\n")
            with self.assertRaisesRegex(ValueError, "unknown Query IDs"):
                MOD.load_fixtures(path)

    def test_fixture_rejects_migration_query_expect_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "queries.yaml")
            _write(path, "fixture_set: t\npractice_migrations:\n  - old_practice: old\n    new_practice: new\n    kind: merge\n    reason: moved\n    query_ids: [q]\nqueries:\n  - id: q\n    kind: positive\n    previous_expect: old\n    migration_kind: merge\n    migration_reason: moved\n    expect: other\n    text: a query\n")
            with self.assertRaisesRegex(ValueError, "expect must be"):
                MOD.load_fixtures(path)

    def test_fixture_rejects_multi_valid_expectations(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "queries.yaml")
            _write(path, "fixture_set: t\nqueries:\n  - id: q\n    kind: positive\n    expect: old\n    acceptable: [old, new]\n    text: a query\n")
            with self.assertRaises(ValueError):
                MOD.load_fixtures(path)

    def test_retirement_migration_may_have_no_successor(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "queries.yaml")
            _write(path, "fixture_set: t\npractice_migrations:\n  - old_practice: old\n    kind: retire\n    reason: no independent decision remains\n    query_ids: [q]\nqueries:\n  - id: q\n    kind: positive\n    expect: old\n    status: retired\n    retired_reason: replaced\n    text: old query\n")
            MOD.load_fixtures(path)

    def test_retired_query_is_not_runnable(self):
        doc = {"queries": [{"id": "old", "kind": "positive", "expect": "old", "status": "retired", "retired_reason": "over-broad", "replacement_queries": ["new"], "text": "broad"}, {"id": "new", "kind": "positive", "expect": "new", "status": "frozen", "text": "narrow"}]}
        runnable, skipped = MOD.partition_queries(MOD._active_queries(doc), {"new"})
        self.assertEqual([q["id"] for q in runnable], ["new"]); self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
