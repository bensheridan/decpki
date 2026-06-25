---
name: project-platform-compat
description: macOS platform authenticator does not support ed25519 passkeys — prototype requires a different device
metadata:
  type: project
---

macOS's Secure Enclave only generates P-256 (ES256, alg -7) WebAuthn credentials. The prototype hardcodes ed25519 (alg -8) throughout, so registration fails on macOS with "Device does not support ed25519 passkeys."

**Why:** The entire crypto chain (COSE key extraction, assertion verification, bundle storage) is built around ed25519 only.

**How to apply:** If the user reports registration failures on Apple hardware, this is the cause. Known workarounds: USB YubiKey 5 series or Android with a FIDO2 authenticator. Proper fix = adding ES256 support to `bff/cose.py` (COSE key extraction), `bff/session.py` (`verify_assertion`), and the enrolment BFF — non-trivial but scoped.
