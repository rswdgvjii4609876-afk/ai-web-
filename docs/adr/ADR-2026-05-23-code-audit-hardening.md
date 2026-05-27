# ADR-2026-05-23: Code Audit Hardening and Export Service Trial Split

## Status

Accepted

## Context

The current application remains a modular monolith. A code audit on 2026-05-23 found several production risks that can be fixed without a broad rewrite: user-controlled LLM base URLs, resume Celery tasks carrying decrypted API keys, brittle auth/schema behavior, verbose SMTP errors, weak upload preflight, broad backoffice write permissions, and missing security headers.

The same audit also found structural risks that are too large for a same-day repair: `AIService` and `InterviewService` own too many responsibilities, client/backoffice adapters share domain services directly, public knowledge base content and slices are separate facts, and the server import script's default dry-run still performs deploy preflight work.

## Decision

This change applies low/medium-risk hardening immediately and starts one bounded extraction:

- Keep the system as a modular monolith.
- Route training sample and fine-tuning export callers through `TrainingSampleExportService`.
- Keep interview orchestration, question generation, and report generation inside `InterviewService` for this round.
- Add SSRF protection for user LLM base URLs: official provider domains are allowed by default, custom gateways must be listed in `USER_LLM_ALLOWED_BASE_URLS`, and HTTP/private/loopback/metadata targets are blocked.
- Stop passing decrypted user API keys through Celery. Resume workers rebuild runtime config from the database using only non-sensitive provider/model options from the queue payload.
- Normalize account emails at schema/service boundaries.
- Use exact refresh token hash matching before legacy fallback, avoiding multi-active-token `scalar_one_or_none()` failures.
- Surface knowledge slice rebuild status in API responses while deferring transactional schema changes.

## Consequences

Immediate risk is reduced without changing the primary interview workflow.

The export split is intentionally shallow: it establishes a new boundary and reroutes callers, but several helper implementations still live in `InterviewService`. A deeper extraction should follow once export behavior is covered by more integration tests.

The following remain explicit future approval items:

- Add database-level case-insensitive unique indexes for user/admin email.
- Move refresh tokens to HttpOnly cookies and make access tokens memory-only.
- Add dedicated content-management permissions instead of reusing admin-management permission for public content writes.
- Make public knowledge base content and slice rebuilding fully transactional with persisted `slice_build_status`.
- Move original member-submission images out of Git into encrypted object storage.
- Split `AIService` and `InterviewService` into domain/application services after an ADR and migration plan.
- Split server import commands into `preflight`, `deploy`, `import --dry-run`, and `import --execute`.
