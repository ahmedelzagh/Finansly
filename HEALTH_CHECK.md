# Project Health Check — Finansly

Date: 2026-02-07

## Scope
- Documentation review (README, env example, deployment files)
- Code review across core modules (Flask app, financial utilities, Telegram bot, price tracker)
- Dependency/config check
- Security and deployment readiness review

## Documentation vs Implementation Mismatches
1) **Price check interval**
   - README states “every 30 minutes”
   - Implementation runs every 8 hours
   - Files:
     - README.md (lines 77–82)
     - app.py (lines 228–235)

2) **Requirements list mismatch**
   - README install list omits `beautifulsoup4`
   - requirements.txt includes `beautifulsoup4`
   - Files:
     - README.md (lines 16–23)
     - requirements.txt (lines 1–6)

## Critical / High Issues
1) **Old Excel data mis-mapped after header upgrade**
   - The code updates headers from old 8-column format to new 10-column headers but does not migrate existing rows.
   - When reading, rows are normalized using the new headers, which shifts values into incorrect columns.
   - Files:
     - financial_utils.py (lines 125–133)
     - app.py (lines 123–155)
   - Impact: Historical records display incorrect values (schema inconsistency).

2) **Delete entry likely fails for timestamps with spaces/colons**
   - Timestamps are interpolated directly into the URL without encoding.
   - Files:
     - templates/index.html (lines 86–88)
   - Impact: Delete action can 404 or behave unexpectedly.

3) **Weak default credentials**
   - Defaults are `admin` / `password123` if env vars are not set.
   - Files:
     - app.py (lines 25–27)
   - Impact: Trivial account compromise in misconfigured deployments.

4) **Telegram webhook lacks request verification**
   - Endpoint does not validate any secret token or Telegram header.
   - Files:
     - app.py (lines 164–168)
     - telegram_bot.py (lines 20–33)
   - Impact: Endpoint can be spammed or abused.

## Medium / Low Issues
5) **Server-side input validation incomplete**
   - Form inputs are cast without try/except, which can raise a 500 on bad input.
   - Files:
     - app.py (lines 66–78)

6) **Redis service unused in Docker**
   - docker-compose includes Redis, but app uses filesystem sessions only.
   - Files:
     - docker-compose.yml (lines 1–14)
     - app.py (lines 20–23)

7) **No automated tests present**
   - No test files found in the repository.

8) **CLI PayPal checker may mislead**
   - Prints “Decision sent to Telegram” even if Telegram is not configured.
   - Files:
     - check_paypal.py (lines 25–30)

## Security / Best-Practice Notes
- **No CSRF protection** on login and main form
  - Files: templates/index.html (lines 107–121), templates/login.html (lines 31–52)
- **Session hardening** not configured (secure cookies, HTTPOnly, SameSite)
  - Files: app.py (lines 20–23)

## Recommendations
### Fix Immediately
1) Migrate old Excel data rows properly when upgrading headers.
2) URL-encode timestamp or use a stable row ID for delete.
3) Require env credentials; remove default weak credentials.
4) Add webhook verification (Telegram secret token).

### Can Be Deferred
- Align README schedule with implementation (or change interval).
- Remove unused dependencies or document why they’re needed.
- Improve input validation UX and add error handling.
- Add CSRF protection and cookie hardening.

### Logical Next Steps
- Implement a data migration path for old Excel rows.
- Add a minimal test suite (financial_utils, PayPal calculator, delete behavior).
- Decide on session storage (filesystem vs Redis) and align Docker + docs.

### Refactoring Needs
- Centralize configuration and env validation.
- Add validation layer for user input and API responses.
- Split webhook logic into a separate blueprint/module and add auth checks.

---

## Fix Plan — Organized by Priority & Phases

### Phase 1: Critical Security/Data Fixes (Do First)
**Branch: `fixup/excel-data-migration`**
- Fix Excel header upgrade bug that corrupts historical data
- Files: financial_utils.py, app.py
- Impact: Data integrity for users
- Status: Completed (merged to main)

**Branch: `fixup/webhook-security`**
- Add Telegram webhook request verification (secret token)
- Files: app.py, telegram_bot.py
- Impact: Production deployment safety
- Status: Completed (merged to main)

**Branch: `fixup/credentials-config`**
- Remove weak defaults (admin/password123); require env vars
- Files: app.py, .env.example
- Impact: Security baseline
- Status: Completed (merged to main)

**Branch: `fixup/delete-url-encoding`**
- URL-encode timestamps in delete endpoint (handle spaces/colons)
- Files: templates/index.html
- Impact: User-facing delete functionality
- Status: Ready for merge (after verification)

### Phase 2: Documentation & Configuration (Quick Wins)
**Branch: `docs/readme-alignment`**
- Fix README: Change "every 30 minutes" to "every 8 hours"
- Add beautifulsoup4 to install section
- Files: README.md
- Status: Not started

**Branch: `cleanup/redis-decision`**
- Remove unused Redis from docker-compose OR document its purpose
- Files: docker-compose.yml, app.py, README.md
- Status: Not started

### Phase 3: Session & Input Hardening (Medium Priority)
**Branch: `feat/session-hardening`**
- Add CSRF protection to forms (Flask-WTF or token-based)
- Improve session cookie security (HTTPOnly, SameSite, Secure flags)
- Files: app.py, templates/index.html, templates/login.html
- Status: Not started

**Branch: `cleanup/input-validation`**
- Add try/except error handling for form input parsing
- Return 400 with user-friendly messages instead of 500 errors
- Files: app.py (form processing sections)
- Status: Not started

### Phase 4: Testing & Quality
**Branch: `feat/test-suite`**
- Add unit tests for financial_utils.py (helpers, calculations)
- Add tests for PayPal transfer calculator
- Add tests for delete endpoint behavior
- Files: tests/ (new directory), test files
- Status: Not started

### Execution Order
1. Phase 1 (Critical) → 4 branches
2. Phase 2 (Quick wins) → 2 branches
3. Phase 3 (Hardening) → 2 branches
4. Phase 4 (Testing) → 1 branch
5. **Total: 9 feature/fix branches to create and merge**

---
End of report.
