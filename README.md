# python3

> Python 3 template — UV · Ruff · Ty · pytest · Mise · PyInstaller · GHAS

A batteries-included Python 3 project template modelled after [orchestras/deno](https://github.com/orchestras/deno). All automation lives in `.mise/tasks/` as executable scripts (no inline TOML blocks), making tasks portable for the upcoming `mise-sync` engine.

---

## Features

| Tool | Role |
|------|------|
| [UV](https://docs.astral.sh/uv/) | Fast Python package manager + venv |
| [Ruff](https://docs.astral.sh/ruff/) | Linter + formatter (replaces flake8, isort, black) |
| [Ty](https://github.com/astral-sh/ty) | Type checker (Astral's next-gen checker) |
| [pytest](https://pytest.org) | Test runner with coverage |
| [Mise](https://mise.jdx.dev) | Tool version manager + task runner |
| [PyInstaller](https://pyinstaller.org) | Cross-platform binary compilation |
| [GHAS / CodeQL](https://github.com/features/security) | GitHub Advanced Security scanning |
| [Dependabot](https://docs.github.com/en/code-security/dependabot) | Automated dependency updates |

---

## Quick Start

```bash
# 1. Install mise (https://mise.jdx.dev)
curl https://mise.run | sh

# 2. Clone the template and initialise
git clone https://github.com/orchestras/python3 my-project
cd my-project

# 3. Full project init (installs tools, deps, configures git)
mise run project:init

# 4. Run the app
mise run run
```

---

## Task Reference

Run `mise tasks` to list all tasks with descriptions.

### Development

```bash
mise run install        # uv sync --all-extras
mise run run            # python -m python_template
mise run build          # sync version.py from pyproject.toml
```

### Code Quality

```bash
mise run lint           # ruff check src/ tests/
mise run lint:fix       # ruff check --fix
mise run fmt            # ruff format
mise run fmt:check      # ruff format --check (CI safe)
mise run typecheck      # ty check src/
```

### Testing

```bash
mise run test           # pytest tests/
mise run test:cov       # pytest + coverage report
mise run test:watch     # pytest in watch mode (requires pytest-watch)
```

### CI

```bash
mise run ci:all         # full pipeline: install → lint → fmt:check → typecheck → test:cov
```

### Version Bumping

```bash
mise run version              # show current version
mise run bump:patch           # 0.1.5 → 0.1.6
mise run bump:minor           # 0.1.5 → 0.2.0
mise run bump:major           # 0.1.5 → 1.0.0
mise run bump:prerel alpha    # 0.1.5 → 0.1.5-alpha.1
mise run tag:push             # push tags → triggers release workflow
```

### Git & VCS

```bash
mise run git:config           # configure delta, GPG, rebase-only, hooks path
mise run vcs:rebase           # rebase feature branch onto origin/develop
mise run vcs:integrate        # forward-integrate feature → develop (rebase + force push)
mise run vcs:release          # release develop → main (rebase + force push)
mise run vcs:protect          # apply branch protection rulesets via GitHub API
```

### Security & Scanning

```bash
mise run scan:ghas            # trigger CodeQL scan via workflow dispatch
mise run scan:deps            # audit Python deps with pip-audit
mise run scan:secrets         # scan for leaked secrets (trufflehog/gitleaks)
```

### Git Hooks

```bash
mise run hooks:sync           # sync hooks from orchestras/git-hooks
mise run hooks:install        # register hooks path in git config
```

### Binary Compilation

```bash
mise run compile              # PyInstaller one-file binary for current platform
```

> For cross-platform binaries, push a version tag — the [release workflow](.github/workflows/release.yml)
> builds on Linux AMD64/ARM64, macOS ARM64/AMD64, and Windows AMD64 in parallel.

---

## Project Structure

```
.
├── .devcontainer/         # VS Code Dev Container
├── .github/
│   ├── workflows/         # CI/CD pipelines
│   ├── dependabot.yml     # Dependabot config
│   └── CODEOWNERS         # Code ownership
├── .mise/tasks/           # All mise tasks (executable scripts)
├── config/
│   └── githooks/hooks/    # Git hooks (synced via hooks:sync)
├── scripts/               # Shared bash utilities
├── src/
│   └── python_template/   # Main package (rename for your project)
│       ├── __init__.py
│       ├── __main__.py    # CLI entry point
│       ├── version.py     # Auto-generated — do not edit
│       └── py.typed       # PEP 561 marker
├── tests/                 # pytest test suite
├── AGENTS.md              # AI agent instructions
├── CHANGELOG.md           # Changelog
├── CONTRIBUTING.md        # Contributor guide
├── mise.toml              # Tool versions + task discovery
└── pyproject.toml         # Python config (Ruff, pytest, coverage, etc.)
```

---

## Branch Workflow

```
feature/xyz → develop → main → tag → release
```

**No merge commits anywhere.** Every integration is a rebase.

### Keep your feature branch current

```bash
# On your feature branch:
mise run vcs:rebase
# → git pull --rebase origin develop
```

### Integrate a feature branch into develop

```bash
mise run vcs:integrate feat/my-feature
# 1. Rebase feature onto origin/develop
# 2. git checkout develop && git pull
# 3. git rebase feat/my-feature
# 4. git push --force-with-lease origin develop
```

### Release develop → main

```bash
mise run vcs:release
# 1. git checkout main
# 2. git rebase origin/develop
# 3. git push --force-with-lease origin main
```

Then bump and tag:

```bash
mise run bump:patch   # (or :minor / :major)
mise run tag:push     # triggers binary + Docker release CI
```

---

## Renaming This Template

1. Replace `python_template` with your package name throughout `src/`
2. Update `name` in `pyproject.toml`
3. Update `project.scripts` entrypoint in `pyproject.toml`
4. Run `mise run build` to sync `version.py`
5. Update this README

---

## GitHub Status Checks Setup

For required status checks in branch rulesets to work:

1. Push this template to GitHub (on `develop` branch)
2. Open one PR to trigger the `pr-check` workflow — this registers the check names
3. Run `mise run vcs:protect` to apply the ruleset via GitHub API
4. The following checks will be required: `pr-check / lint`, `pr-check / typecheck`, `pr-check / test`, `pr-check / security`

---

## License

MIT © [ørchestras](https://github.com/orchestras)
