# Contributing

Thank you for contributing to this project! Please read this guide before opening issues or PRs.

## Prerequisites

- [Mise](https://mise.jdx.dev) — tool version manager
- [UV](https://docs.astral.sh/uv/) — Python package manager (managed by mise)
- [Git](https://git-scm.com) with GPG signing configured (optional but recommended)
- [gh CLI](https://cli.github.com) — for `mise run vcs:protect` and scanning tasks

## Setup

```bash
# Clone the repo
git clone https://github.com/orchestras/python3
cd python3

# Initialise everything
mise run project:init
```

This will:
1. Install Python, UV, Ruff, and delta via mise
2. Install Python dependencies with `uv sync`
3. Configure local git settings (delta pager, rebase-only, hooks path)
4. Sync tags from remote
5. Install shell completions

## Development Workflow

### Branch naming

```
feat/<description>
fix/<description>
chore/<description>
refactor/<description>
```

### Making changes

```bash
# Create a feature branch from develop
git checkout develop
git pull origin develop
git checkout -b feat/my-feature

# Make your changes, then run the full pipeline before committing
mise run ci:all

# Commit with Conventional Commits format
git add .
git commit -m "feat: add my new feature"

# Push your feature branch
git push -u origin feat/my-feature
```

### Keeping your feature branch current

If `develop` has moved on while you were working, rebase your branch onto it:

```bash
# From your feature branch:
mise run vcs:rebase
# This runs: git pull --rebase origin develop
# and commits any autoStash residue with a chore label.
```

### Opening a PR

- Target `develop` (not `main`)
- Fill out the PR template completely
- All required status checks must pass: `lint`, `typecheck`, `test`, `security`
- At least 1 approving review required

## Code Standards

### Style

All code is formatted and linted by Ruff. Run:

```bash
mise run fmt       # format
mise run lint      # lint
mise run lint:fix  # auto-fix lint issues
```

### Type annotations

All public functions must have complete type annotations. Run:

```bash
mise run typecheck   # ty check
```

### Tests

All new features must include tests. Tests live in `tests/` and follow the `test_*.py` naming convention.

```bash
mise run test        # run tests
mise run test:cov    # with coverage (must stay above 80%)
```

### Docstrings

Use [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for all public functions and classes.

```python
def my_function(arg: str) -> int:
    """Brief one-line description.

    Args:
        arg: Description of the argument.

    Returns:
        Description of return value.

    Raises:
        ValueError: When the input is invalid.
    """
```

### Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new feature
fix: fix a bug
docs: update documentation
chore: maintenance task
refactor: code restructuring without behaviour change
test: add or fix tests
ci: changes to CI configuration
```

The `commit-msg` hook enforces this format.

## Releasing

Releases are managed by the maintainers using a strict rebase-only flow — no merge commits anywhere.

### 1. Integrate a feature branch into develop

```bash
# From your feature branch (or pass the name explicitly):
mise run vcs:integrate feat/my-feature

# What it does:
#   git checkout feat/my-feature
#   git pull --rebase origin develop          # ensure feature is current
#   git checkout develop
#   git pull origin develop                   # ensure local develop is current
#   git rebase feat/my-feature               # fast-forward develop onto feature tip
#   git push --force-with-lease origin develop
```

### 2. Release develop → main

```bash
mise run vcs:release

# What it does:
#   git checkout main
#   git rebase origin/develop
#   git push --force-with-lease origin main
```

### 3. Bump version and push tag

```bash
mise run bump:patch    # (or :minor / :major)
mise run tag:push      # pushes tag → triggers binary + Docker release workflow
```

CI then builds PyInstaller binaries for Linux/macOS/Windows and a multi-arch Docker image, then creates a GitHub Release.

## Security

- Never commit secrets, credentials, or API keys
- Use `mise run scan:secrets` before pushing
- Use `mise run scan:deps` to audit dependencies
- Report security vulnerabilities privately via GitHub Security Advisories
