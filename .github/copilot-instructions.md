# Copilot Instructions for python3 template

## Project Overview

This is a Python 3 project template using UV (package manager), Ruff (linter + formatter),
Ty (type checker), pytest (testing), and Mise (task runner / tool manager).

## Key Conventions

- **Package manager**: UV (`uv sync`, `uv add`, `uv run`)
- **Linter/formatter**: Ruff (`ruff check`, `ruff format`)
- **Type checker**: Ty (`ty check`) — Astral's new type checker
- **Test runner**: pytest with coverage (`pytest tests/`)
- **Task runner**: Mise (`mise run <task>`) — tasks are in `.mise/tasks/`
- **Version authority**: `pyproject.toml` → synced to `src/python_template/version.py`

## Code Style

- Line length: 100 characters
- Python minimum: 3.12
- Docstring style: Google
- All public functions must have type annotations and docstrings
- Use `from __future__ import annotations` for forward references

## Workflow

1. Feature branches off `develop`, rebased (never merged) via `mise run vcs:rebase`
2. PRs target `develop` — required status checks must pass
3. Releases: merge develop → main → CI auto-tags → PyInstaller binaries built
4. Bumps: `mise run bump:patch/minor/major` (commits + tags locally), then `mise run tag:push`

## Tasks

Run `mise tasks` to see all available tasks. Key ones:
- `mise run install` — install deps
- `mise run ci:all` — full CI pipeline
- `mise run lint` / `mise run lint:fix` — lint with Ruff
- `mise run fmt` / `mise run fmt:check` — format with Ruff
- `mise run typecheck` — type-check with ty
- `mise run test` / `mise run test:cov` — tests with/without coverage
- `mise run bump:patch/minor/major` — version bump
- `mise run tag:push` — push tags → triggers release
