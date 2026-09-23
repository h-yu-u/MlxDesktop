# AGENTS.md — MLX Studio Engineering Rules

## 1. Project intent

Build an Apple Silicon desktop application for running local MLX text, multimodal, and image-generation models.

Architecture:

- Tauri 2 desktop shell.
- Vue 3 + Vite + TypeScript frontend.
- Naive UI for base UI components.
- Python 3.12 + uv + FastAPI Runtime Supervisor.
- One active Python inference Worker.
- Engine adapters for mlx-lm, mlx-vlm, and MFLUX.
- SQLite for metadata; file system for binary assets.

## 2. Required engineering style

- Prefer high cohesion and low coupling.
- Prefer pure functions and immutable transformations.
- Keep side effects at explicit boundaries.
- Prefer composition over inheritance.
- Do not add abstraction without a real volatile boundary or repeated use case.
- Do not create generic dumping grounds such as `utils.ts`, `helpers.py`, or `common/` without a single clear theme.

## 3. Dependency direction

Allowed:

```text
UI → Application → Domain
Infrastructure/Adapters → Domain Ports
Entrypoints → Application
```

Forbidden:

- Domain importing Vue, Pinia, Naive UI, FastAPI, Pydantic, Tauri, SQLite, or MLX packages.
- Vue components importing MLX-specific details.
- Components calling HTTP directly.
- Model adapters accessing UI or conversation persistence.
- Rust/Tauri code implementing model or chat business logic.

## 4. Side-effect rules

Pure code should handle:

- State transitions.
- Model capability derivation.
- Request construction.
- Validation.
- Error mapping.
- Scheduling decisions.

Side effects belong only in:

- API clients.
- Repositories.
- File stores.
- Download providers.
- Worker hosts.
- Engine adapters.
- Tauri platform modules.

Never perform I/O in Pinia getters, Vue computed values, or domain functions.

## 5. Frontend rules

- Use Vue 3 Composition API and `<script setup lang="ts">`.
- Use Naive UI for Button, Input, Select, Modal, Drawer, Dialog, Upload, Table, Tooltip, Progress, Message, Notification, Skeleton, Empty, and common layout primitives.
- Use VueUse before writing common browser/reactivity composables.
- Custom components must represent product-domain concepts, not reimplement UI primitives.
- Pages compose features; containers orchestrate; presentational components use props/events.
- Pinia stores orchestrate state and effects; domain reducers stay in plain TypeScript.
- Use `unknown` at external boundaries; avoid `any`.
- API DTOs are generated from FastAPI OpenAPI. Do not duplicate them manually.

## 6. Python rules

- Python 3.12 managed by uv.
- Use Ruff and Pyright.
- Domain models should use immutable dataclasses/value objects where practical.
- Pydantic is for entrypoint DTOs, not domain models.
- MLX imports are allowed only under engine adapters/worker entrypoints.
- Do not keep a model in a hidden global singleton.
- Long-running inference belongs in a Worker process, not the Supervisor event loop.
- Map upstream exceptions to stable domain error codes.
- Top-level process/task boundaries may catch broad exceptions; inner business code may not.

## 7. Rust/Tauri rules

- Keep Rust thin.
- Tauri manages sidecar lifecycle, security, dialogs, updater, and native integration.
- Never accept an arbitrary executable path or arbitrary shell command from the frontend.
- Scope capabilities to the fixed sidecar and required arguments only.
- Child-process cleanup must be idempotent.

## 8. File and function limits

Soft limits:

- Vue SFC: 220 lines.
- TypeScript: 220 lines.
- Python: 250 lines.
- Rust: 250 lines.
- Function: 35 lines.
- Nesting: 3 levels.
- Function parameters: 4; use a typed parameter object beyond that.

Hard limits require an explicit documented exception:

- Vue SFC: 320 lines.
- TypeScript: 350 lines.
- Python/Rust: 400 lines.
- Function: 60 lines.

Generated files, migrations, and compatibility data are exempt when stored in dedicated directories.

## 9. Testing rules

Every feature should include the narrowest appropriate tests:

- Pure domain logic: unit tests.
- Engine implementations: shared contract tests.
- API + persistence: integration tests.
- Vue states and interactions: Vitest + Vue Test Utils.
- Full web flows: Playwright with mocked Tauri bridge.
- Real MLX models: Apple Silicon system tests using pinned small models.

Bug fixes require a regression test.

Do not assert complete nondeterministic model output. Assert protocol events, schemas, terminal state, valid files, dimensions, and stable invariants.

## 10. UI states

Every asynchronous screen or action must handle:

- Idle.
- Loading/preparing.
- Empty.
- Success.
- Error.
- Cancelled when applicable.

Never leave a task indefinitely in `loading` or `cancelling`.

## 11. Model capability rules

- Model behavior is driven by `ModelManifest` and compatibility data.
- Do not branch on model display name or string fragments.
- `trust_remote_code` is off by default.
- Unknown, partially supported, incompatible, and broken are distinct states.

## 12. Security and privacy

- Runtime binds to `127.0.0.1` only.
- Desktop session token is ephemeral and never written to disk.
- External API is disabled by default and uses a separate token.
- Do not log full prompts, outputs, file contents, or secrets by default.
- Do not execute code while scanning model directories.
- Validate all paths and file sizes.
- Markdown raw HTML is disabled by default.

## 13. Required checks before completion

Run:

```bash
pnpm check
pnpm test
```

For Runtime or engine changes also run the relevant contract/integration/system test.

A task is not complete until:

- Acceptance criteria pass.
- Tests are present.
- Types and lint pass.
- Error/loading/empty/cancel states are handled.
- No dependency-boundary violation is introduced.
- Documentation and migrations are updated where needed.

