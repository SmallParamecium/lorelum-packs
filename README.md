# Lorelum Knowledge Packs

This repository is the official public catalog for installable Lorelum Knowledge Packs. Each directory under `packs/` is a self-contained Pack root using the public `pack.yaml + practices/**/*.md + decisions.yaml?` format. A Pack may also include on-demand `references/`, `assets/`, and `scripts/` resources when its Practices route a reader to them with a `resource:` Markdown link.

## Catalog

- `issue-pr-etiquette@0.1.0` — 12 repository-neutral Practices for filing issues, opening pull requests, and taking part in reviews: single-problem convergence with testable acceptance criteria, cited evidence, gate classification, single declared scope, conventional titles, cold-reviewer PR bodies, diff hygiene, review discipline, and honest AI-assistance disclosure. Bundles issue and PR skeleton templates as `assets/` resources.
  - [简体中文本地化](./packs/issue-pr-etiquette/i18n/zh-CN/README.md) is available as non-runtime companion content.
- `pack-creator@0.2.0` — published release with 27 domain-neutral Practices for defining, designing, authoring, reviewing, evaluating, localizing, and releasing Packs, including repository-local project layers. The official Registry resolves the immutable `pack-creator-v0.2.0` ref.
  - [简体中文本地化](./packs/pack-creator/i18n/zh-CN/README.md) is available as non-runtime companion content.
- `react-web-craft@0.1.0` — 24 Practices for React web application design and performance across component state, async data flow, code loading, rendering, and component composition.
  - [简体中文本地化](./packs/react-web-craft/i18n/zh-CN/README.md) is available as non-runtime companion content.
- `agentic-coding@0.5.1` — published release with 34 decision-focused Practices rewritten as step-style decision procedures with severity tiers (critical/warn/info); 0.5.1 retunes the catalog description to name the planning-calibration moments. The official Registry resolves the immutable `agentic-coding-v0.5.1` ref.
  - [简体中文本地化](./packs/agentic-coding/i18n/zh-CN/README.md) is available as non-runtime companion content.

## Use Packs

Pack commands use the user-level LocalStore by default. Use `--store-root <path>` only when a
worktree, test, or other isolated environment needs its own Pack and derived-index data; it does not
select a model, Backend address, or runtime directory.

### Browse installed Packs and Practices

```sh
# List installed Packs, or include their descriptions and applicability metadata.
lore pack list
lore pack list --details

# List one Pack's Practice catalog, then read one exact Practice in full.
lore pack list agentic-coding
lore get agentic-coding.testing.classify-failure-before-changing-test
```

`lore pack list <pack>` returns compact Practice summaries (`id`, `title`, and `applies_when`).
`lore get <practice-id>` reads the selected Practice's complete guidance, anti-patterns, and source
metadata.

### Install or update

```sh
# Install the latest stable release into a Store where the Pack is not yet installed.
lore pack install agentic-coding

# Use `@version` to select an exact release.
lore pack install <pack>
lore pack install <pack>@<version>
lore pack install agentic-coding@0.5.1
lore pack update <pack>
lore pack update <pack>@<version>
lore pack update agentic-coding@0.5.1
```

Omit `@version` to resolve the Registry's latest stable release. `install` is for a new Pack; use
`update` when replacing a Pack that is already installed. The Lorelum CLI contains the official
Registry repository name, not the Pack content: it reads the Registry descriptor, resolves the
release, validates the Pack, and writes it to the selected LocalStore.

### Remove a Pack

```sh
lore pack remove agentic-coding
```

### Use a different public Registry or an isolated Store

Another public GitHub repository can expose the same layout and be selected explicitly:

```sh
lore pack install agentic-coding@0.5.0 --registry owner/repository
lore pack update agentic-coding --registry owner/repository

# The global --store-root option can appear before or after the Pack command.
lore --store-root ./tmp/lore-store pack install agentic-coding
lore pack list --store-root ./tmp/lore-store
```

Custom registries must expose `.lorelum/registry.yaml` from a supported public GitHub repository.

## Evaluation fixtures and scripts

`fixtures/<pack>/` holds `evaluation_only` hypotheses, never runtime input: `practice-catalog.yaml` (per-Practice retrieval and behavior contrasts) and `workflows.yaml` (cross-Practice scenarios). `fixtures/agentic-coding/queries.yaml` additionally holds a retrieval query set — at least 1 positive query per active Practice (currently 106 positive and 70 neighbor queries), written as situations (automatic restatement checks cover only titles and `applies_when`) — whose expected selections are declared before any run. Query entries use `status: frozen` for formal CI; over-broad historical entries may be `status: retired` with replacement references, and explicit Practice migrations record the previous target and reason. `fixtures/agentic-coding/baselines/` stores recorded runs. Fixtures state hypotheses, not proof of retrieval or downstream quality.

`scripts/eval-queries` evaluates a query set against a Pack by looping the public `lore` CLI (Python 3.9+ with PyYAML; no CLI changes). It supports `--mode keyword|semantic|both`; when the semantic index cannot build on a machine (for example the known `embedding.deadline-exceeded` on some Windows x64 hosts), the run is marked degraded with the failure code instead of failing. It reports per-query hits, positive top-k hit rates, the neighbor confusion matrix, and `--baseline` regression diffs. `--top-k` controls metrics and baseline-regression thresholds, while `--min-top3` is always a fixed positive Top-3 gate. `--project-root <dir>` switches to candidate mode and evaluates the Pack under `<dir>/.lorelum/packs/agentic-coding` via ProjectContext instead of an installed release; `--fail-on-baseline-regression` makes any lost hit exit non-zero. Any gate failure still writes the `--out` JSON and `--report` Markdown artifacts with a `gate_failures` section.

```sh
# Isolated-store run against a registry release, writing a JSON artifact and Markdown report.
python scripts/eval-queries --mode both --ensure-install agentic-coding@0.5.1 \
  --store-root tmp/eval-store --out run.json --report run.md

# Compare a later run (for example a rewritten Practice set) against a recorded baseline.
python scripts/eval-queries --mode keyword --baseline fixtures/agentic-coding/baselines/<baseline>.json

# Promotion gate for a future release: every installed Practice must have fixture queries,
# and the positive top-3 hit rate must clear the team's bar. Exits non-zero otherwise.
python scripts/eval-queries --mode keyword --require-coverage --min-top3 0.90 \
  --require-frozen \
  --ensure-install agentic-coding@0.5.1 --store-root tmp/eval-store \
  --baseline fixtures/agentic-coding/baselines/<previous-release>.json
```

### Updating the query set

The query set is a maintained fixture, not a generated one: it grows with the catalog through the promotion flow, and the gates make skipping a step visible.

- **A change that adds a Practice adds its queries in the same change**: at least 1 positive query in `fixtures/agentic-coding/queries.yaml`. Add neighbor queries for the boundary distinctions the change depends on, and keep neighbor expectations aligned with the practice-catalog `nearest_neighbor` map — update the catalog first if the new Practice changes which neighbor is nearest for an existing one. `--require-coverage` fails any run against a Pack containing a Practice with no positive queries.
- **Queries must be written in situation wording, not the Practice's own words.** Check every change with `python scripts/eval-queries --check-discipline --mode keyword --limit 1` — it fails on any 4+-word run shared with an installed Practice's title or `applies_when`, because such a query matches the keyword index by quotation and proves nothing about retrieval.
- **When Practices are refined, merged, or removed, record an explicit Query migration.** A migration must list its affected `query_ids`; each linked Query must either declare `previous_expect` or be retired. A migrated Query no longer counts as coverage for its previous Practice. If that Practice remains active, add an independent positive and an old-vs-new neighbor Query; if it is retired, record the Practice migration instead of inventing coverage. Over-broad Queries are split into new IDs or retired rather than using multi-valid expectations.
- **The team gate is recorded in the fixture** (`min_top3`); every complete run enforces it by default. CI additionally pins `--min-top3 0.90` so removing the fixture field cannot silently disable the gate. An exploratory `--limit N` run never evaluates or passes the Top-3 gate, even when the fixture defines a minimum; it cannot be combined with `--require-coverage`, `--require-frozen`, `--fail-on-baseline-regression`, or an explicit `--min-top3`. Formal gates require explicit `status: frozen` for every active Query, fail on missing targets and Query execution errors, and count errors as misses in the Top-3 denominator. A degraded semantic mode is reported as not evaluated rather than silently passing.
- **Baseline regression gates require compatible evidence**: `--fail-on-baseline-regression` requires `--baseline` with the same Pack, fixture set and Top-k, and complete, valid results for each requested mode (result count must match `totals.runnable`; partial runs are rejected). Deleting an old Query ID requires a retained `status: retired` entry with a reason; changing its text requires retirement and a new ID. Practice migration records must link Queries that actually belonged to the old Practice.

```sh
# Preflight for a change that touches Practices or queries.
python scripts/eval-queries --mode keyword --require-coverage --check-discipline \
  --require-frozen \
  --ensure-install agentic-coding@0.5.1 --store-root tmp/eval-store \
  --baseline fixtures/agentic-coding/baselines/<previous-release>.json
```

Existing queries double as canaries: re-running them against a new release with `--baseline` reports whether newly added Practices steal hits meant for existing ones.

### Candidate mode and CI gate

The PR workflow `.github/workflows/agentic-coding-retrieval.yml` runs when `packs/agentic-coding/**`, `fixtures/agentic-coding/**`, `scripts/eval-queries`, or the workflow itself changes. It builds a temporary ProjectContext from the PR's `packs/agentic-coding`, then runs the keyword gate in candidate mode:

```sh
python scripts/eval-queries --project-root "$PROJECT_ROOT" \
  --fixtures fixtures/agentic-coding/queries.yaml --mode keyword \
  --min-top3 0.90 --require-coverage --require-frozen --check-discipline \
  --baseline fixtures/agentic-coding/baselines/agentic-coding-0.5.1-keyword-2026-09-28.json \
  --fail-on-baseline-regression
```

`--project-root` and `--ensure-install` are mutually exclusive. The workflow also runs the evaluator unit tests before retrieval. Candidate mode reads the Pack version from `$PROJECT_ROOT/.lorelum/packs/agentic-coding/pack.yaml`, validates the candidate Pack, requires a ready ProjectContext with `base: none`, checks the active Practice set, and reads each active Practice through `lore get --json` before running keyword queries against the same ProjectContext. JSON and Markdown evidence are uploaded when produced; bootstrap or candidate-validation failures may occur before the evaluator can create artifacts. Scope, gate decisions, and deferred Query/body checks are recorded in [Issue #26 design decisions](docs/issue-26-query-source-decision.md).

### Decision probes (lightweight behavior check)

Retrieval evaluation proves a Practice is findable and distinguishable, not that it steers decisions well; the benchmark repository owns real-task behavioral proof. `scripts/eval-decisions` fills the gap with a per-change smoke test that reuses fixtures already required by the promotion flow — no new authoring:

```sh
# 1. Emit probes (practice-catalog entries or workflow phases) into tmp/probes.
#    Injection content is the real top-1 lore query hit, so retrieval is exercised too.
python scripts/eval-decisions --emit-dir tmp/probes --store-root tmp/eval-store \
  [--fixtures fixtures/agentic-coding/practice-catalog.yaml] [--only <substr,substr>] [--limit N]

# 2. A fresh answering session follows tmp/probes/protocol.md: answer all blind prompts
#    first (no pack access), then all injected prompts, then score against the manifest
#    rubric and write tmp/probes/answers/<id>.verdict.yaml with quoted evidence.

# 3. Aggregate into a run artifact (record worthwhile runs under fixtures/.../baselines/).
python scripts/eval-decisions --report-from tmp/probes \
  --out tmp/probe-run.json --report tmp/probe-run.md [--fail-on-harmful]
```

Each probe is scored `moved-toward` (injection moved the decision toward the fixture's `expected_behavior` without triggering `forbidden_behavior`), `no-change` (blind answer already correct, or injection did not materially change it), or `harmful`. Probes are a directional smoke test, not behavioral proof: they cover single decisions, not multi-turn tasks, and scoring is judgment with quoted evidence rather than measurement. Benchmark runs stay reserved for release-level validation.

To compare two pack versions, emit the same fixtures twice (one `--store-root` per version) and have one fresh answering session answer the blind prompts once, then each version's injected prompts, then score both — blind prompts are byte-identical, so the responder drops out of the comparison. Recorded example: `fixtures/agentic-coding/baselines/agentic-coding-probes-paired-delta-2026-09-18.md`. Two calibrations from that run: advisory-mode `0 harmful` is weak evidence (a responder with a correct blind answer rejects even corrupted injections — verify sensitivity with a corrupted-body control), and re-asking with "a team practice you have decided to follow" (compliance framing) scores the content directly; a corrupted body comes out `harmful` only under that framing.

### Evaluating unreleased working-tree content (project-local layer)

Installed Stores verify pack directories against the artifact digest recorded at install time, so copying a Store and inserting Practices (files or database rows) fails with `store.recovery-required`. To evaluate content that has no Registry release yet, build a project-local layer instead — `lore` discovers `.lorelum/packs/<pack>` from the working directory, and the layer is self-contained (`base: none`) rather than merged with the user Store:

```sh
# One-time setup: copies packs/agentic-coding into the layer and writes a
# lore-json wrapper (lore 0.1.0-alpha.3+ required for project layers + --json).
python scripts/eval-project-layer --pack agentic-coding --dir tmp/probe-project

# Decision probes run unchanged from the layer directory (--store-root omitted:
# lore resolves the layer from the current working directory).
cd tmp/probe-project
python ../../scripts/eval-decisions --lore lore-json.cmd \
  --fixtures fixtures/agentic-coding/practice-catalog.yaml \
  --emit-dir ../../tmp/probes --retrieval-mode keyword
```

Boundaries: `eval-decisions` needs only `lore query`/`lore get`, both layer-aware. `eval-queries` additionally calls `pack list`, which reads the user Store and does not see the layer — measure layer retrieval with direct `lore query` loops (top-k hits against declared expectations) until that harness grows layer support.

## Repository layout

```text
.lorelum/registry.yaml
fixtures/
  agentic-coding/
    practice-catalog.yaml
    workflows.yaml
    queries.yaml
    baselines/
scripts/
  eval-queries
packs/
  agentic-coding/
    pack.yaml
    README.md
    SOURCES.md
    practices/
    i18n/
  issue-pr-etiquette/
    pack.yaml
    README.md
    SOURCES.md
    practices/
    assets/
    i18n/
  pack-creator/
    pack.yaml
    README.md
    SOURCES.md
    practices/
    references/
    assets/
    scripts/
    i18n/
  react-web-craft/
    pack.yaml
    README.md
    SOURCES.md
    practices/
    i18n/
```

The `packs/<name>` path is this catalog's organization convention. A project-authored Pack may instead live at `.lorelum/packs/<name>` in its own project; the Pack root format itself is unchanged.
