# Feature Specification: Node 24 + pnpm Migration

**Feature Branch**: `010-node24-pnpm`

**Created**: 2026-06-29

**Status**: Draft

**Input**: Upgrade Node.js to v24 and migrate from npm to pnpm across the browser toolchain, demo server, and all documentation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Fresh Clone Works with pnpm on Node 24 (Priority: P1)

A developer clones the repo on a machine with Node 24 and pnpm installed. They run `pnpm install` inside the browser directory and get a clean install with no engine warnings. Tests pass and the demo server starts.

**Why this priority**: This is the day-to-day developer workflow. If this breaks, nothing else matters.

**Independent Test**: On Node 24 with pnpm, run `pnpm install && pnpm test` from the `browser/` directory. Zero engine warnings, all tests pass.

**Acceptance Scenarios**:

1. **Given** Node 24 and pnpm are installed, **When** a developer runs `pnpm install` in `browser/`, **Then** no EBADENGINE warnings appear and `pnpm-lock.yaml` is created
2. **Given** a clean install, **When** `pnpm test` is run, **Then** all browser unit tests pass
3. **Given** the demo server, **When** `pnpm dev` (or `node demo/server.mjs`) is run, **Then** the server starts on port 3000

---

### User Story 2 — Quickstart Scripts Use pnpm (Priority: P2)

The `scripts/start-demo.sh` prerequisite check and the README quickstart both reference pnpm instead of npm. A developer following the README uses pnpm throughout.

**Why this priority**: Documentation inconsistency causes confusion. Once toolchain is migrated, all entry points must align.

**Independent Test**: Follow the README quickstart verbatim substituting pnpm. Complete the register → promote → login flow without touching npm.

**Acceptance Scenarios**:

1. **Given** the README quickstart, **When** a developer follows it with pnpm, **Then** every `npm install` reference is replaced by `pnpm install`
2. **Given** `scripts/start-demo.sh`, **When** the prerequisite check runs, **Then** it checks for `pnpm` rather than relying on npm

---

### User Story 3 — Dev Dependency Versions Unpinned (Priority: P3)

vitest, @vitest/coverage-v8, and happy-dom are unpinned from their Node 18-compat versions back to latest. The `engines` field in `package.json` declares Node ≥ 24.

**Why this priority**: The Node 18 pins were a workaround. Removing them keeps the toolchain up to date and reduces future upgrade friction.

**Independent Test**: `browser/package.json` has `"engines": { "node": ">=24.0.0" }` and devDependencies use `^latest` semver ranges. `pnpm install` resolves to the current latest versions with no downgrade warnings.

**Acceptance Scenarios**:

1. **Given** the updated `package.json`, **When** `pnpm install` runs on Node 24, **Then** vitest resolves to ≥ 4.x and happy-dom resolves to ≥ 20.x
2. **Given** a `package.json` with an `engines` field, **Then** running `pnpm install` on Node < 24 prints a clear engine mismatch warning

---

### Edge Cases

- What happens if a contributor runs `npm install` out of habit? — A `.npmrc` with `engine-strict=true` or a `packageManager` field in `package.json` should warn or redirect them.
- What if `pnpm` is not installed? — `scripts/start-demo.sh` should print a clear install hint (e.g. `npm install -g pnpm` or `corepack enable pnpm`).
- Does `package-lock.json` need to be deleted? — Yes, it should be removed and added to `.gitignore` to prevent accidental npm usage from recreating it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `browser/package.json` MUST declare `"engines": { "node": ">=24.0.0" }` and `"packageManager": "pnpm@<current-stable>"` 
- **FR-002**: `browser/` MUST contain `pnpm-lock.yaml` and MUST NOT contain `package-lock.json`
- **FR-003**: `package-lock.json` MUST be removed from the repo and added to `.gitignore`
- **FR-004**: vitest, @vitest/coverage-v8, and happy-dom MUST be unpinned to their latest compatible semver ranges (no Node 18 workaround pins)
- **FR-005**: All browser tests MUST pass after migration (`pnpm test` exits 0)
- **FR-006**: `scripts/start-demo.sh` MUST check for `pnpm` as a prerequisite with an actionable install hint
- **FR-007**: README quickstart MUST replace every `npm install` reference with `pnpm install`
- **FR-008**: `scripts/setup-validators.sh` and `scripts/promote-enrolment.sh` MUST be reviewed; any npm references updated

### Key Entities

- **`browser/package.json`**: Gains `engines` and `packageManager` fields; devDependency versions updated
- **`browser/pnpm-lock.yaml`**: New lockfile replacing `package-lock.json`
- **`scripts/start-demo.sh`**: `require_cmd` call added for `pnpm`
- **`README.md`**: All npm install instructions replaced with pnpm equivalents

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pnpm install && pnpm test` in `browser/` on Node 24 completes with zero engine warnings and all tests green
- **SC-002**: No `package-lock.json` exists anywhere in the repository after migration
- **SC-003**: A developer following the README quickstart top-to-bottom on a fresh Node 24 + pnpm machine encounters zero npm references
- **SC-004**: Running `pnpm install` on Node < 24 produces a clear warning (engine mismatch) rather than silently succeeding

## Assumptions

- The developer environment has Node 24 LTS and pnpm (latest stable) available
- Only the `browser/` directory has Node dependencies — no other `package.json` files exist in the repo
- The demo server (`browser/demo/server.mjs`) uses only Node built-ins and `browser/` deps; it does not need a separate pnpm workspace
- CI/CD pipelines (if any) are out of scope for this feature — only local developer workflow is targeted
- `corepack enable pnpm` is the recommended install method, but `npm install -g pnpm` is acceptable as a fallback hint
