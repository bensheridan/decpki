# Tasks: Node 24 + pnpm Migration

**Input**: Design documents from `specs/010-node24-pnpm/`

**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Organization**: Tasks grouped by user story. Each story is independently testable.
No automated test tasks — validation is manual per quickstart.md scenarios.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US#]**: User story this task belongs to

---

## Phase 1: Setup

**Purpose**: Prepare the environment and delete the old lockfile.

- [X] T001 Delete `browser/package-lock.json` from the repository (git rm if tracked)
- [X] T002 Add `browser/package-lock.json` to `.gitignore` so it cannot reappear

---

## Phase 2: Foundational

**Purpose**: Update `browser/package.json` with Node 24 engine declaration, packageManager field, and unpinned devDependencies. This unblocks all three user stories.

- [X] T003 Add `"engines": { "node": ">=24.0.0" }` to `browser/package.json`
- [X] T004 Add `"packageManager": "pnpm@10.28.1"` to `browser/package.json` (use current `pnpm --version` output)
- [X] T005 Restore devDependencies in `browser/package.json` to latest semver ranges: `"vitest": "^4.1.9"`, `"@vitest/coverage-v8": "^4.1.9"`, `"happy-dom": "^20.10.6"` (remove Node 18 pins)
- [X] T006 Create `browser/.npmrc` containing `engine-strict=true` on a single line

**Checkpoint**: `browser/package.json` has `engines`, `packageManager`, and unpinned devDeps. `browser/.npmrc` exists.

---

## Phase 3: User Story 1 — Clean Install on Node 24 (Priority: P1)

**Goal**: `pnpm install` in `browser/` produces `pnpm-lock.yaml` with zero engine warnings and all tests pass.

**Independent Test**: `cd browser && rm -rf node_modules && pnpm install && pnpm test` — zero EBADENGINE warnings, 64 tests green.

- [X] T007 [US1] Run `pnpm install` inside `browser/` to generate `browser/pnpm-lock.yaml`
- [X] T008 [US1] Verify `pnpm test` passes (all 64 unit tests green, vitest ≥ 4.x)
- [X] T009 [US1] Commit `browser/pnpm-lock.yaml` to the repository (git add)

**Checkpoint**: `pnpm-lock.yaml` committed, tests pass, no engine warnings.

---

## Phase 4: User Story 2 — Scripts and README Use pnpm (Priority: P2)

**Goal**: `scripts/start-demo.sh` checks for pnpm and README references pnpm throughout.

**Independent Test**: Follow README quickstart substituting pnpm — no npm references encountered. `start-demo.sh --help` (or dry-run) shows pnpm in prerequisite list.

- [X] T010 [P] [US2] Add `require_cmd pnpm "Run: corepack enable pnpm  (Node 24 includes corepack)"` to `scripts/start-demo.sh` after the existing `require_cmd` calls
- [X] T011 [P] [US2] Replace `cd browser && npm install && cd ..` with `cd browser && pnpm install && cd ..` in `README.md`
- [X] T012 [P] [US2] Search README and all files under `specs/` for remaining `npm install` references in user-facing quickstart sections and update to `pnpm install`

**Checkpoint**: `grep -r "npm install" README.md scripts/` returns nothing.

---

## Phase 5: User Story 3 — Dev Deps Unpinned (Priority: P3)

**Goal**: Confirm vitest and happy-dom resolved by pnpm are at their latest versions (≥ 4.x and ≥ 20.x respectively), not the Node 18-era pins.

**Independent Test**: `pnpm list vitest happy-dom` shows ≥ 4.x and ≥ 20.x in `browser/`.

- [X] T013 [US3] Run `pnpm list vitest happy-dom` inside `browser/` and confirm versions ≥ vitest 4.x, happy-dom 20.x — update `package.json` ranges if pnpm resolved older versions

**Checkpoint**: `pnpm-lock.yaml` pins latest vitest and happy-dom; no Node 18-era downgrade.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T014 [P] Verify `bash -n scripts/start-demo.sh` still passes syntax check after T010
- [X] T015 [P] Verify `npm install` in `browser/` exits non-zero (engine-strict rejection) — confirms `.npmrc` is effective
- [X] T016 [P] Search the full repo for any remaining `npm install` in user-facing docs (`grep -r "npm install" README.md scripts/ specs/010-node24-pnpm/`) and fix any stragglers

---

## Dependencies & Execution Order

- **Phase 1** (T001–T002): No dependencies — start immediately
- **Phase 2** (T003–T006): Depends on Phase 1 complete (package.json changes need lockfile deleted first)
- **Phase 3** (T007–T009): Depends on Phase 2 (needs updated package.json to generate correct lockfile)
- **Phase 4** (T010–T012): Independent of Phase 3 — can run in parallel with Phase 3; depends only on Phase 1
- **Phase 5** (T013): Depends on Phase 3 (needs pnpm-lock.yaml to inspect resolved versions)
- **Phase 6** (T014–T016): Depends on all prior phases

### Parallel Opportunities

- T010, T011, T012 within Phase 4 are all independent (different files)
- T014, T015, T016 within Phase 6 are all independent

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001–T002 (delete lockfile, update gitignore)
2. T003–T006 (update package.json, create .npmrc)
3. T007–T009 (pnpm install, test, commit lockfile)
4. **Validate**: `pnpm test` passes, no engine warnings

### Incremental Delivery

- US1 → working pnpm install on Node 24 (highest value)
- US2 → docs and scripts aligned (prevents confusion for new contributors)
- US3 → confirm latest dep versions resolved (cleanup confirmation)
- Polish → npm rejection confirmed, final grep sweep
