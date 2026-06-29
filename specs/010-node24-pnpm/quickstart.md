# Quickstart Validation: Node 24 + pnpm Migration

## Prerequisites

- Node.js 24 installed (`node --version` shows `v24.x.x`)
- pnpm installed: `corepack enable pnpm` (or `npm install -g pnpm`)
- Repo cloned fresh (no existing `node_modules`)

---

## Scenario 1: Clean install on Node 24

```bash
cd browser
rm -rf node_modules
pnpm install
```

**Expected**: No EBADENGINE warnings. `pnpm-lock.yaml` present. `node_modules` populated.

---

## Scenario 2: Tests pass

```bash
cd browser
pnpm test
```

**Expected**: All 64 unit tests pass. vitest reports ≥ 4.x version. Exit code 0.

---

## Scenario 3: npm install is rejected

```bash
cd browser
npm install
```

**Expected**: npm exits non-zero with an engine mismatch error (due to `engine-strict=true`
in `.npmrc`). No `package-lock.json` created.

---

## Scenario 4: Full demo flow uses pnpm throughout

```bash
# From repo root — follow README quickstart verbatim
pip install -e .
pip install -r bff/requirements.txt
cd browser && pnpm install && cd ..
bash scripts/setup-validators.sh
bash scripts/start-demo.sh
```

**Expected**: `start-demo.sh` prerequisite check passes (pnpm found). Demo server starts.
Open http://localhost:3000/register.html — page loads correctly.

---

## Scenario 5: Engine warning on Node < 24

```bash
# On a machine with Node 18 (or nvm use 18)
cd browser
pnpm install
```

**Expected**: pnpm prints an engine compatibility warning referencing Node 24 requirement.
Install may or may not proceed depending on pnpm `engine-strict` setting — the warning is
the important outcome.
