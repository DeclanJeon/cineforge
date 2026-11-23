# Skill Pack Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One CineForge installation consumes either of two compatible installed packs without an engine rebuild or changes to production authority, and existing projects retain their original binding.

**Architecture:** The pack publishes a declarative CineForge adapter in its existing `manifest.json`, with a companion file inventory. CineForge validates the adapter, binds it per project, and uses the same resolved view for status, handoffs and delivery while leaving the state machine, execution scope, and evidence checks under engine control.

**Tech Stack:** Python 3.10+, JSON and JSON Schema, SHA-256, existing pack installer, pytest, existing CineForge CLI/wheel.

**Spec:** [2026-11-24-skill-pack-integration-design.md](../specs/2026-11-24-skill-pack-integration-design.md)

## Global constraints

- Two repos: `cineforge` and `contents-production-skills`. Extend the existing installer; do not modify globally installed skills, publish, deploy, or make provider calls for verification.
- Preserve dirty, unrelated work. In particular `cineforge/cli.py` and `cineforge/pipeline.py` already have goal-driver changes in the current checkout. Start on clean bases in isolated worktrees or obtain explicit agreement about another workspace. Copy this approved spec and plan to the CineForge implementation workspace, not other dirty changes.
- V1 is declarative and recognizes only `cut_revision`, `code_motion`, `realtime_3d`. Routing hints must not affect authority, execution envelopes, output contracts, or gate decisions.
- Data roots: repository/standalone `manifest.json`, or copied `video-production-assets/support/manifest.json`. Inventory location is relative to the manifest; inventory members are relative to the pack root. An explicit root does not fall back. Test unsafe paths and outside-root links offline.
- Preserve the lock-file and JSON shapes specified in the design. Record legacy/missing mock state explicitly for newly created projects, distinguish it from old projects with no binding, and never infer successful use from an installed file.
- Keep existing CLI behavior for legacy projects, including legacy handoff format. For new projects, missing or invalid explicit paths must not silently select legacy mode or fallback. Non-destructive read commands must still work if an already-bound pack is absent.

## Review focus

| Risk | Required test |
|---|---|
| Changing only the skill installation still changes new handoffs and UI | Same built CLI runs A/B for equivalent requests; compare routing and unchanged core fields |
| The common installer copies the descriptor but not its inventory, or hashes copied bytes differently | Build installer plan from the real pack checkout and use a temp destination, then run `cineforge skills --root` there |
| A revoked or replaced pack is still used through a mutation path other than `run` | Tamper with a pinned file; exercise the shared check from manual handoffs/completion, paid-envelope/results, local motion and delivery |
| Missing optional `jsonschema` makes undeclared security-sensitive properties acceptable | Reject extra keys, incorrect types, and unsafe path values under the default wheel dependency set |
| Same pack on a different path, or multiple installs with identical bytes | Move/clone A and resume; distinguish two locations of A from conflicting identities A and B |

## Task 1 — Pack adapter and copy-installation

**Files in the pack:** `manifest.json`, `integrations/cineforge/files.json`, new inventory builder/validator under `scripts/`, `scripts/install_package.py` and its tests, `creative-production/references/skill-map.md`.

- [x] Start with an installer test using a source fixture containing `integrations.cineforge.inventory`; assert a copied installation includes the exact same inventory bytes adjacent to the support manifest at the declared relative path. Add tests for missing inventory, outside-manifest paths, and preexisting derived support collisions; see `scripts/test_install_package.py`. Run red first.
- [x] Add the adapter and inventory copy entry using existing installer preflight/atomic-copy logic. Keep legacy pack installation working. During inventory generation include stable regular files under registered skill directories, excluding generated caches, worktrees, and installer-reserved support snapshots; record paths in sorted order with SHA-256. Generate and commit the inventory with adapter inputs in the eventual pack change set, not with generated project data.
- [x] Populate all engine stage IDs at the recorded CineForge base. Transfer route/owner order and the reviewed stage-specific motion/cut guidance from `pipeline.yaml` and `_handoff()`. Pack-local references must exist on the clean pack base or be explicitly supplied as part of this feature. Keep free-text craft routing in the existing craft bridge, not a second engine rule table. Document how a host uses the packet-provided pack and how a pack maintainer regenerates inventory.
- [x] Run installer and inventory tests with temporary destinations; assert the checked-in inventory regenerates byte-for-byte. No install into the workstation’s active skill directories.

## Task 2 — CineForge reader and project pin

**Files in CineForge:** dedicated small pack manifest and binding modules (used through the existing `cineforge.skills` interface), `cineforge/data/schemas/skill_pack.schema.json`, `tests/test_skill_pack.py`, `cineforge/cli.py`, `cineforge/pipeline.py` creation path.

- [x] Add test fixtures that generate small valid packs, two compatible different adapters, and malformed variants. Tests must fail first: source and copy layout, explicit-root isolation, unsupported contract, strict unknown keys, incomplete stages, scope/path escape, missing/changed files, identical vs conflicting installations.
- [x] Parse manifest and inventory with duplicate-key detection. Check packaged shape and enforce all v1 restrictions also when `jsonschema` is absent. Canonicalize pack roots and check lexical and resolved paths. Build one normalized in-memory view; distinct installed locations of the same bytes are equivalent, conflicting identities need an explicit root. Return diagnostic status separately from compatibility and never execute pack files during discovery.
- [x] Add creation/resume tests: invalid or missing explicit pack leaves no new directory; A is snapshotted to `skill_pack.lock.json`; B updates future projects only; detached A allows read-only status; restoring identical A elsewhere resumes. Validate before `Project.create` creates the directory and persist the lock atomically. Refuse corrupt or unresolvable locks. Use positive evidence of legacy/mocked creation, not current CLI flags alone, to select compatibility behavior. Existing test scenarios that simulate an external production flow use a valid pack fixture rather than widening mock permissions.
- [x] Run pack-reader and project-creation tests; include a reader run with no `jsonschema` installed or imported.

## Task 3 — Resolve runtime handoffs, reporting and provenance

**Files in CineForge:** `cineforge/pipeline.py`, `cineforge/progress.py`, `cineforge/cli.py`, handoff schema, `cineforge/jobs.py`, `cineforge/local_motion.py`, `cineforge/delivery.py`, tests adjacent to handoffs, execution and delivery.

- [x] Drive existing project entrypoints (`new`, `run`, `status --json`) with fixture A/B. Assert owners, route, refs, guide and pack identity come from the project binding; frozen paths point to the verified installation; permission requirements and output/evidence contracts remain identical. Assert both progress presentation and shared JSON use those same owners.
- [x] Read the common binding view for handoffs and progress (CLI, panel and sharing). Restrict old hardcoded craft routes to legacy/fake structure flows. Keep routing data separate from authority and output fields. Translate approved plan/request facts to stable v1 booleans; resolve matching references in the specified order. Do not add provider selection or new creative logic.
- [x] Exercise stale binding, corrupted binding and unbound mock across distinct production mutation entrypoints, beyond `_handoff()`: external `run` before image submission, `complete`, envelope creation, result recording, local motion render/deliver, and standard delivery. Place the shared guard before the relevant write/submission in the owning operation rather than relying only on the CLI. Test acceptance for legacy paths and idempotent evidence completion separately. Preserve gate and receipt validation; attach provenance additively and never infer actual tool usage merely from pins.
- [x] Run focused tests for pack integration, CLI, routing, closure, evidence and code motion. Stub provider effects, not the policy being asserted. Report any independently reproduced preexisting failures rather than skipping or hiding them.

## Task 4 — Cross-repo acceptance and docs

- [x] Build one wheel from the isolated CineForge workspace. Install it only in a disposable virtual environment. Run `cineforge skills --root` against the pack source and the isolated output of the pack installer. No online generation or account credentials are needed.
- [x] Make a second compatible pack fixture with one different owner or guide. Run the same wheel to create A and B, inspect generated handoffs and status, and confirm unchanged required authority and expected output. Replace A, prove status is still viewable and production is blocked, then restore identical A elsewhere and prove resumption. Run malformed provenance/authority fixtures and verify no provider submission. Save the exact commands and observed results in the implementation handoff.
- [x] Update CineForge user docs (`README.md`, CLI and stage contracts) to explain copy-install, explicit root, lock and legacy modes. Self-check linked paths and docs. Only report implemented and exercised behavior; deployment is a separate decision.

## Execution status

- [x] Approved design mapped to both repositories and actual package installer layout.
- [x] Detected that both active checkouts are `main` with unrelated local edits; other worktrees belong to other tasks.
- [x] Isolated worktrees created: `feat/skill-pack-v1` (engine, base `b7b3a18`) and `feat/cineforge-pack-v1` (pack, base `0fafda5`). Active installations and main checkouts not edited by this implementation.
- [x] RED observed: installer inventory not copied (3 failures); reader/CLI contract missing (9 failures); unlisted file and waiting handoff relocation independently reproduced before fixes.
- [x] Real source and copy-installed pack checked: `python scripts/install_package.py --skills-root <temp-pack>`, `cineforge skills --root <temp-pack>` (444 pinned files), and `python scripts/build_cineforge_inventory.py --check`. Pack regression: 38 passed and 5 subtests passed.
- [x] Disposable wheel built with `uv build --wheel`; accepted A/B using the same CLI executable without `jsonschema`. S06 owner/route/refs changed, S08 authority and expected output did not. B could read A's status but could not run A. Identical A relocated an issued handoff without rewriting input pins. A pack injecting `authority_granted` was rejected before project creation. No providers called for this smoke test.
- [x] Final engine suite: `python -m pytest -q --tb=short` — 198 passed, 2 skipped. `git diff --check` clean in both worktrees.
- [x] Integrated into fresh isolated worktrees based on engine `35ccdfc` and pack `94aad5d`. Rebuilt the inventory and checked the engine and pack copies of the v1 schema are byte-identical. Pack CI runs `python scripts/check_cineforge_contract.py` before tests. Detected and fixed an integration edge: the new goal driver now checks the pack before it writes an external attempt.
- [x] Latest integrated engine: 231 passed, 2 live-provider tests skipped. Latest integrated pack: 1369 passed, 5 skipped, 534 subtests passed. Reran the goal delivery provenance and wrong-pack attempt tests after adding the final assertions: 2 passed.
- [x] Release-candidate crossover: one `cineforge-0.1.4-py3-none-any.whl`, two separately built and unpacked skill archives (2.64 candidate and 2.65 test variant). Verified owners/route/refs changed but execution permission and expected output did not; B refused A's run and completion; identical relocated A kept the original pins and completed with a receipt tied to A. Verified authority and outputs policy injection was rejected without `jsonschema`, and ran the smoke with no provider calls.
- Local evidence: `/tmp/cineforge-pack-integrated.zFAHsb/{final-engine-suite.log,final-pack-suite.log,release-smoke.log,verify_release_candidates.py}`. Branches `feat/skill-pack-v1-integrated-engine` and `feat/skill-pack-v1-integrated-pack`. Release candidates: CineForge 0.1.4 and pack 2.64. Deliver the pack first, then the compatible engine. Keep the installed pack in a versioned directory so a later update can preserve existing project bindings.
