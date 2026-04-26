#!/usr/bin/env python3
"""sync_patterns.py — Standalone patterns channel sync script.

This script can run WITHOUT the dev_patterns package being installed.
It imports nothing from the package; instead it re-implements the minimal
logic needed to bootstrap a new repo before the package is available.

Once the package is installed (``uv sync``), prefer using::

    dev-patterns sync

or the mise tasks::

    mise run patterns:sync

Usage::

    python scripts/sync_patterns.py [options]
    python scripts/sync_patterns.py --repo orchestras/dev-patterns --channel python3a

The script:
    1. Resolves which repo/channel/version to use (env → mise.toml → .githooks-version)
    2. Fetches the latest HEAD SHA from the repo
    3. Skips if .patterns-hash matches
    4. Downloads and extracts the tarball
    5. Copies lib/$channel/ into the project tree
    6. Writes .patterns-hash

Python 3.12+ required (no third-party dependencies).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# ── Minimum Python version check ─────────────────────────────────────────────
if sys.version_info < (3, 12):
    print("ERROR: Python 3.12+ required.", file=sys.stderr)
    sys.exit(1)

import tomllib

# ── ANSI colours ──────────────────────────────────────────────────────────────
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

CHECK = "✓"
CROSS = "✗"
ARROW = "→"
SPIN = "⟳"
WARN = "⚠"


def header(msg: str) -> None:
    """Print a section header."""
    print(f"{CYAN}{BOLD}{msg}{RESET}")


def step(msg: str) -> None:
    """Print a step line."""
    print(f"  {BLUE}{ARROW}{RESET} {msg}")


def working(msg: str) -> None:
    """Print a working/progress line."""
    print(f"  {DIM}{SPIN}{RESET} {msg}")


def ok(msg: str) -> None:
    """Print a success line."""
    print(f"  {GREEN}{CHECK}{RESET} {msg}")


def warn(msg: str) -> None:
    """Print a warning."""
    print(f"  {YELLOW}{WARN}{RESET} {msg}", file=sys.stderr)


def error(msg: str) -> None:
    """Print an error."""
    print(f"  {YELLOW}{CROSS}{RESET} {msg}", file=sys.stderr)


def done(msg: str) -> None:
    """Print a bold success summary."""
    print(f"{GREEN}{BOLD}{CHECK} {msg}{RESET}")


# ── Version-spec resolution ───────────────────────────────────────────────────

DEFAULT_REPO = "orchestras/dev-patterns"
DEFAULT_CHANNEL = "python3a"
DEFAULT_VERSION = "main"


def resolve_spec(
    root: Path,
    override_repo: str | None = None,
    override_channel: str | None = None,
) -> tuple[str, str, str, bool]:
    """Return (repo, channel, version, use_release).

    Resolution order:
    1. CLI overrides
    2. PATTERNS_* env vars
    3. mise.toml [env] GITHOOKS_* keys
    4. .githooks-version file (new format: repo/channel/version)
    5. .githooks-version file (old format: v0.1.12)
    6. Built-in defaults
    """
    env = os.environ

    # 1. CLI overrides take highest precedence
    if override_repo and override_channel:
        return override_repo, override_channel, DEFAULT_VERSION, False

    # 2. PATTERNS_* env vars
    p_repo = env.get("PATTERNS_REPO", "").strip()
    p_channel = env.get("PATTERNS_CHANNEL", "").strip()
    p_hash = env.get("PATTERNS_HASH", "").strip()
    if p_repo and p_channel:
        return p_repo, p_channel, p_hash or DEFAULT_VERSION, False

    # 3. mise.toml [env] section
    mise_toml = root / "mise.toml"
    if mise_toml.exists():
        try:
            data = tomllib.loads(mise_toml.read_text())
            env_sec: dict = data.get("env", {})
            gh_repo = str(env_sec.get("GITHOOKS_REPO", "")).strip()
            gh_ver = str(env_sec.get("GITHOOKS_VERSION", "")).strip()
            gh_prof = str(env_sec.get("GITHOOKS_PROFILE", "")).strip()
            if gh_repo or gh_ver or gh_prof:
                repo = gh_repo or DEFAULT_REPO
                channel = override_channel or gh_prof or DEFAULT_CHANNEL
                version = gh_ver or DEFAULT_VERSION
                use_release = _is_release_tag(version)
                return repo, channel, version, use_release
        except Exception:
            pass

    # 4 & 5. .githooks-version file
    gv_file = root / ".githooks-version"
    if gv_file.exists():
        raw = gv_file.read_text().strip()
        parts = raw.split("/")
        if len(parts) == 4:
            repo = f"{parts[0]}/{parts[1]}"
            channel = parts[2]
            version = parts[3]
            return repo, channel, version, _is_release_tag(version)
        if len(parts) == 1 and raw:
            use_release = _is_release_tag(raw)
            return DEFAULT_REPO, DEFAULT_CHANNEL, raw, use_release

    # 6. Defaults
    return DEFAULT_REPO, override_channel or DEFAULT_CHANNEL, DEFAULT_VERSION, False


def _is_release_tag(version: str) -> bool:
    return bool(re.match(r"^v\d+\.\d+\.\d+", version))


# ── GitHub helpers ────────────────────────────────────────────────────────────

def _gh_available() -> bool:
    try:
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def fetch_head_sha(repo: str, ref: str = "main") -> str | None:
    """Return the HEAD SHA for *ref* on *repo*, or None."""
    if _gh_available():
        try:
            r = subprocess.run(
                ["gh", "api", f"repos/{repo}/commits/{ref}", "--jq", ".sha"],
                capture_output=True, text=True, timeout=15,
            )
            sha = r.stdout.strip()
            if len(sha) == 40:  # noqa: PLR2004
                return sha
        except Exception:
            pass
    # Fallback: unauthenticated API
    url = f"https://api.github.com/repos/{repo}/commits/{ref}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read())
            sha = data.get("sha", "")
            return sha if len(sha) == 40 else None  # noqa: PLR2004
    except Exception:
        return None


def download_tarball(repo: str, ref: str, dest: Path) -> bool:
    """Download a tarball for *ref* to *dest*. Returns True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _gh_available():
        try:
            with dest.open("wb") as fh:
                r = subprocess.run(
                    ["gh", "api", f"repos/{repo}/tarball/{ref}",
                     "--header", "Accept: application/vnd.github+json"],
                    stdout=fh, stderr=subprocess.DEVNULL, timeout=60,
                )
            if r.returncode == 0 and dest.stat().st_size > 0:
                return True
        except Exception:
            pass
    # Fallback: urllib
    url = f"https://github.com/{repo}/archive/{ref}.tar.gz"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310
            dest.write_bytes(resp.read())
        return dest.stat().st_size > 0
    except Exception:
        return False


def download_release_tarball(repo: str, tag: str, dest: Path) -> bool:
    """Download a GitHub Releases tarball for *tag* to *dest*."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{repo}/archive/refs/tags/{tag}.tar.gz"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310
            dest.write_bytes(resp.read())
        return dest.stat().st_size > 0
    except Exception:
        return False


# ── Extraction ────────────────────────────────────────────────────────────────

def extract_tarball(tarball: Path, extract_dir: Path) -> Path:
    """Extract *tarball* (stripping top-level GitHub dir) into *extract_dir*."""
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with tarfile.open(tarball, "r:gz") as tf:
        members = tf.getmembers()
        prefix = members[0].name.split("/")[0] if members else ""
        for member in members:
            rel = (
                member.name[len(prefix) + 1:]
                if member.name.startswith(prefix + "/")
                else member.name
            )
            if not rel:
                continue
            dest = extract_dir / rel
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                dest.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(member) as fh, dest.open("wb") as out:  # type: ignore[union-attr]
                    shutil.copyfileobj(fh, out)
                if member.mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return extract_dir


# ── Apply helpers ─────────────────────────────────────────────────────────────

def copy_tree(
    src: Path,
    dst: Path,
    make_executable: bool = False,
    skip_ext: set[str] | None = None,
    only_ext: set[str] | None = None,
) -> list[str]:
    """Recursively copy *src* → *dst*, returning list of relative dest paths."""
    dst.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        ext = item.suffix.lower()
        if skip_ext and ext in skip_ext:
            continue
        if only_ext and ext not in only_ext:
            continue
        rel = item.relative_to(src)
        dest_file = dst / rel
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest_file)
        if make_executable:
            current = dest_file.stat().st_mode
            dest_file.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        written.append(str(dest_file))
    return written


def apply_channel(extract_dir: Path, channel: str, root: Path) -> list[str]:
    """Apply lib/$channel/ content into *root*."""
    channel_dir = extract_dir / "lib" / channel
    if not channel_dir.exists():
        warn(f"Channel directory not found: lib/{channel}")
        return []

    written: list[str] = []

    tasks_src = channel_dir / "mise" / "tasks"
    if tasks_src.exists():
        working("Syncing mise tasks…")
        w = copy_tree(tasks_src, root / ".mise" / "tasks", make_executable=True)
        written += w
        ok(f"Tasks synced → .mise/tasks/ ({len(w)} files)")

    hooks_src = channel_dir / "hooks"
    if hooks_src.exists():
        working("Syncing git hooks…")
        dst = root / "config" / "githooks" / "hooks"
        w = copy_tree(hooks_src, dst, make_executable=True, skip_ext={".toml"})
        m = copy_tree(hooks_src, dst, make_executable=False, only_ext={".toml"})
        written += w + m
        ok(f"Hooks synced → config/githooks/hooks/ ({len(w) + len(m)} files)")

    for item in channel_dir.iterdir():
        if item.name in ("mise", "hooks"):
            continue
        dest = root / item.name
        if item.is_dir():
            w = copy_tree(item, dest)
            written += w
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            written.append(str(dest))
        ok(f"Synced {item.name}")

    return written


def apply_release(extract_dir: Path, root: Path) -> list[str]:
    """Apply a release tarball by mirroring everything into *root*.

    # NOTE: To restrict which paths are extracted from the release tarball
    # (e.g. only config/hooks and bin/), add path filtering here.
    # Currently the entire tarball is extracted to preserve compatibility
    # with unknown release layouts.
    """
    written: list[str] = []
    for src_path in extract_dir.rglob("*"):
        if src_path.is_dir():
            continue
        rel = src_path.relative_to(extract_dir)
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest)
        written.append(str(rel))
    if written:
        ok(f"Extracted {len(written)} files from release tarball")
    return written


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    parser = argparse.ArgumentParser(
        description="Sync patterns channel from dev-patterns repo",
    )
    parser.add_argument("--repo", default=None, help="GitHub org/repo slug")
    parser.add_argument("--channel", default=None, help="Channel name (e.g. python3a)")
    parser.add_argument("--root", default=None, help="Project root directory")
    parser.add_argument("--force", action="store_true", help="Sync even if hash is current")
    parser.add_argument(
        "--list-channels",
        action="store_true",
        help="List available channels in the repo and exit",
    )
    args = parser.parse_args(argv)

    root = Path(args.root or os.getcwd()).resolve()
    header("Patterns Sync")

    repo, channel, version, use_release = resolve_spec(
        root,
        override_repo=args.repo,
        override_channel=args.channel,
    )

    step(f"Repo:    {repo}")
    step(f"Channel: {channel}")
    step(f"Version: {version}")
    print()

    if args.list_channels:
        _list_channels(repo)
        return 0

    cache_dir = root / ".mise" / ".patterns-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    hash_file = root / ".patterns-hash"

    if use_release:
        # Release tarball path — no hash check, just download and apply
        working(f"Downloading release tarball {version}…")
        tarball = cache_dir / f"release-{version}.tar.gz"
        if not download_release_tarball(repo, version, tarball):
            error(f"Failed to download release tarball {version}")
            return 1
        extract_dir = extract_tarball(tarball, cache_dir / f"release-{version}")
        apply_release(extract_dir, root)
        print()
        done(f"Release {version} applied from {repo}")
        return 0

    # Commit-hash path
    working("Fetching latest commit hash…")
    latest_sha = fetch_head_sha(repo, version)
    if not latest_sha:
        warn(f"Could not fetch commit hash for {repo}@{version}. Skipping.")
        return 0

    cached_sha = hash_file.read_text().strip() if hash_file.exists() else ""
    if not args.force and cached_sha == latest_sha:
        ok(f"Already current ({latest_sha[:8]})")
        return 0

    working(f"Downloading tarball ({latest_sha[:8]})…")
    tarball = cache_dir / f"patterns-{latest_sha[:8]}.tar.gz"
    if not download_tarball(repo, latest_sha, tarball):
        error("Tarball download failed")
        return 1

    extract_dir = extract_tarball(tarball, cache_dir / f"extracted-{latest_sha[:8]}")
    apply_channel(extract_dir, channel, root)

    hash_file.write_text(latest_sha + "\n")
    print()
    done(f"Patterns synced ({channel} @ {latest_sha[:8]})")
    return 0


def _list_channels(repo: str) -> None:
    """Print available channels by querying the lib/ directory."""
    url = f"https://api.github.com/repos/{repo}/contents/lib"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            items = json.loads(resp.read())
        channels = [item["name"] for item in items if item.get("type") == "dir"]
        print(f"\nChannels in {repo}:")
        for ch in channels:
            print(f"  · {ch}")
    except Exception:
        warn("Could not list channels (network error or private repo)")


if __name__ == "__main__":
    sys.exit(main())
