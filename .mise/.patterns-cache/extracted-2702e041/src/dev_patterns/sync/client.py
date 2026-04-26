"""GitHub HTTP client for downloading tarballs and querying commit SHAs."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

_SHA_LEN = 40


class GitHubClient:
    """Minimal GitHub API client that avoids third-party dependencies.

    Uses ``gh`` CLI when available (authenticated), falls back to plain
    ``urllib``/``curl`` for unauthenticated access.

    Attributes:
        repo: GitHub ``org/repo`` slug.
    """

    _GH_API_BASE = "https://api.github.com"
    _GH_BASE = "https://github.com"

    def __init__(self, repo: str) -> None:
        """Initialise the client.

        Args:
            repo: GitHub ``org/repo`` slug, e.g. ``"orchestras/dev-patterns"``.
        """
        self.repo = repo
        self._gh_available: bool | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def head_sha(self, ref: str = "main") -> str | None:
        """Return the commit SHA at *ref*, or None on failure.

        Args:
            ref: Branch name, tag, or SHA prefix to resolve.

        Returns:
            Full 40-character commit SHA, or None if unreachable.
        """
        if self._use_gh():
            return self._gh_head_sha(ref)
        return self._api_head_sha(ref)

    def download_tarball(self, ref: str, dest: Path) -> Path:
        """Download a tarball for *ref* and save it to *dest*.

        Args:
            ref:  Git ref (branch, tag, or SHA).
            dest: Destination file path.

        Returns:
            Path to the downloaded file.

        Raises:
            RuntimeError: If download fails.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        if self._use_gh():
            ok = self._gh_download(ref, dest)
            if ok:
                return dest
        self._curl_download(ref, dest)
        return dest

    def download_release_tarball(self, tag: str, dest: Path) -> Path:
        """Download a GitHub Release tarball for *tag* and save it to *dest*.

        This is the path used when ``.githooks-version`` specifies a release
        tag like ``v0.1.12``.

        Args:
            tag:  Release tag name (e.g. ``"v0.1.12"``).
            dest: Destination file path.

        Returns:
            Path to the downloaded file.

        Raises:
            RuntimeError: If the release or tarball is not found.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"{self._GH_BASE}/{self.repo}/archive/refs/tags/{tag}.tar.gz"
        try:
            self._urllib_download(url, dest)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to download release tarball for {tag} from {self.repo}: {exc}"
            ) from exc
        else:
            return dest

    # ── Private helpers ───────────────────────────────────────────────────────

    def _use_gh(self) -> bool:
        """Return True if the ``gh`` CLI is available and authenticated."""
        if self._gh_available is not None:
            return self._gh_available
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            self._gh_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._gh_available = False
        return self._gh_available

    def _gh_head_sha(self, ref: str) -> str | None:
        """Use ``gh api`` to resolve a ref to a SHA."""
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{self.repo}/commits/{ref}", "--jq", ".sha"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            sha = result.stdout.strip()
            return sha if len(sha) == _SHA_LEN else None
        except Exception:
            return None

    def _api_head_sha(self, ref: str) -> str | None:
        """Use the unauthenticated GitHub API to resolve a ref to a SHA."""
        url = f"{self._GH_API_BASE}/repos/{self.repo}/commits/{ref}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
                sha = data.get("sha", "")
                return sha if len(sha) == _SHA_LEN else None
        except Exception:
            return None

    def _gh_download(self, ref: str, dest: Path) -> bool:
        """Download via ``gh api repos/{repo}/tarball/{ref}``."""
        try:
            with dest.open("wb") as fh:
                result = subprocess.run(
                    [
                        "gh",
                        "api",
                        f"repos/{self.repo}/tarball/{ref}",
                        "--header",
                        "Accept: application/vnd.github+json",
                    ],
                    stdout=fh,
                    stderr=subprocess.DEVNULL,
                    timeout=60,
                    check=False,
                )
            return result.returncode == 0 and dest.stat().st_size > 0
        except Exception:
            return False

    def _curl_download(self, ref: str, dest: Path) -> None:
        """Download via ``urllib`` (falls back to curl subprocess)."""
        url = f"{self._GH_BASE}/{self.repo}/archive/{ref}.tar.gz"
        try:
            self._urllib_download(url, dest)
        except Exception:
            self._subprocess_curl(url, dest)

    def _urllib_download(self, url: str, dest: Path) -> None:
        """Download *url* to *dest* using stdlib urllib."""
        with urllib.request.urlopen(url, timeout=60) as resp:
            dest.write_bytes(resp.read())

    def _subprocess_curl(self, url: str, dest: Path) -> None:
        """Download *url* to *dest* using the system ``curl`` command."""
        result = subprocess.run(
            ["curl", "-sSfL", url, "-o", str(dest)],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed for {url}: {result.stderr.decode()}")

    def _make_temp_dest(self, suffix: str = ".tar.gz") -> Path:
        """Create a temporary file path."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        return Path(path)
