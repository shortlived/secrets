# dev-patterns

> Central patterns library for orchestras repositories — git hooks, mise tasks, and channel subscriptions

Provides a declarative `githooks.toml`-based hook manager and a sync engine that distributes
patterns to subscriber repos via channel subscriptions, without requiring YAML, Node.js, or
lefthook.

---

## Features

| Component | Role |
|-----------|------|
| `dev_patterns` | Python library: sync engine, hook installer, version-spec resolver |
| `lib/python3a/` | Python 3 channel (hooks + mise tasks) |
| `scripts/sync_patterns.sh` | Bootstrap wrapper (no package install needed) |
| `scripts/sync_patterns.py` | Standalone sync (stdlib-only, Python 3.12+) |
| UV | Fast Python package manager + venv |
| Ruff | Linter + formatter |
| Ty | Type checker |
| pytest | Test runner with coverage |
| Mise | Tool version manager + task runner |
| GHAS / CodeQL | Security scanning |

---

## Quick Start — Subscribing a repo

```bash
# Bootstrap (curl the wrapper into your scripts/ dir)
curl -sSfL \
  https://raw.githubusercontent.com/orchestras/dev-patterns/main/scripts/sync_patterns.sh \
  -o scripts/sync_patterns.sh && chmod +x scripts/sync_patterns.sh

# Run setup (interactive: prompts for repo + channel)
./scripts/sync_patterns.sh

# OR non-interactive:
PATTERNS_REPO=orchestras/dev-patterns PATTERNS_CHANNEL=python3a \
  ./scripts/sync_patterns.sh

# After initial sync, use mise tasks:
mise run patterns:sync       # pull latest patterns
mise run patterns:check-hash # check if stale; auto-syncs
```

---

## Channel structure

```
lib/
 $channel/           # e.g. python3a
    hooks/
       githooks.toml   # declarative TOML manifest
       pre-commit
       commit-msg
       pre-push
    mise/
        mise.toml       # channel env vars
        tasks/
            patterns/
                setup
                sync
                subscribe
                check-hash
```

---

## Version-spec resolution (.githooks-version support)

Subscriber repos can configure the channel via priority chain:

1. `PATTERNS_*` env vars (`PATTERNS_REPO`, `PATTERNS_CHANNEL`, `PATTERNS_HASH`)
2. `mise.toml [env]` keys: `GITHOOKS_REPO`, `GITHOOKS_VERSION`, `GITHOOKS_PROFILE`
3. `.githooks-version` new format: `org/repo/channel/version`
4. `.githooks-version` legacy format: `v0.1.12` (pulls GitHub Release tarball)
5. Built-in defaults (`orchestras/dev-patterns`, `python3a`, `main`)

Legacy `.githooks-version` (compatible with existing repos):

```
v0.1.12
```

New format:

```
orchestras/dev-patterns/python3a/v0.1.2
```

---

## Task Reference

```bash
mise run patterns:setup      # interactive subscribe wizard
mise run patterns:sync       # pull latest (skips if .patterns-hash is current)
mise run patterns:subscribe  # non-interactive subscribe
mise run patterns:check-hash # lazy hash check; auto-syncs if stale
```

### Development

```bash
mise run install        # uv sync --all-extras
mise run run            # python -m dev_patterns
mise run build          # sync version.py from pyproject.toml
```

### Code Quality

```bash
mise run lint           # ruff check src/ tests/
mise run lint:fix       # ruff check --fix
mise run fmt            # ruff format
mise run fmt:check      # ruff format --check
mise run typecheck      # ty check src/
mise run test           # pytest
mise run test:cov       # pytest + coverage
mise run ci:all         # full pipeline
```

### Releases

```bash
mise run bump:patch     # (or :minor / :major)
mise run tag:push       # triggers release CI
```

---

## Project Structure

```
.
 .mise/tasks/
    patterns/          # patterns:setup/sync/subscribe/check-hash
 .github/
    settings.yml       # Settings app config (rulesets, GHAS, etc.)
    workflows/         # CI/CD pipelines
 config/
    githooks/hooks/    # Git hooks (synced via patterns:sync)
 lib/
    python3a/          # python3a channel
 scripts/
    sync_patterns.sh   # Bootstrap wrapper
    sync_patterns.py   # Standalone sync script
 src/
    dev_patterns/      # Main Python package
       commands/      # CLI commands (sync, hooks)
       core/          # Base classes + styled Console UI
       hooks/         # HookManifest + HookInstaller
       sync/          # SyncEngine + GitHubClient
       version_spec/  # VersionSpecResolver
 tests/               # pytest test suite (85 tests, 80%+ coverage)
 AGENTS.md            # AI agent instructions
 CHANGELOG.md
 mise.toml            # Tool versions + task discovery
 pyproject.toml       # Python config (Ruff, pytest, coverage, etc.)
```

---

## Branch Workflow

No merge commits. Every integration is a rebase.

```bash
mise run vcs:rebase                    # rebase feature onto develop
mise run vcs:integrate feat/my-feature # integrate feature into develop
mise run vcs:release                   # develop to main
```
