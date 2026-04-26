"""Runtime fetch of the compiletimehash from the private secrets repository.

The compiletimehash never lives on disk.  It is fetched fresh on every
``acquiesce`` and ``push`` invocation via the GitHub Contents API, authenticated
with the gh CLI OAuth token.  The token is discarded immediately after the
fetch; the compiletimehash is discarded after key derivation.

Environment variable ``SLS_COMPILETIMEHASH`` can be set to bypass the network
fetch (used in unit tests and offline development environments).
"""

from __future__ import annotations

import base64
import os
import subprocess

import httpx

from sls.core.config import COMPILETIMEHASH_FILE, COMPILETIMEHASH_REPO


class CompileTimeHashError(Exception):
    """Raised when the compiletimehash cannot be fetched."""


def _get_gh_token() -> str:
    """Retrieve the GitHub CLI OAuth token via ``gh auth token``.

    Returns:
        The OAuth token string.

    Raises:
        CompileTimeHashError: If the gh CLI is not available or not authenticated.
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        token = result.stdout.strip()
        if not token:
            raise CompileTimeHashError("gh auth token returned an empty token")
    except FileNotFoundError as exc:
        raise CompileTimeHashError("gh CLI not found — install it with 'brew install gh'") from exc
    except subprocess.CalledProcessError as exc:
        raise CompileTimeHashError(
            f"gh auth token failed (are you logged in?): {exc.stderr.strip()}"
        ) from exc
    else:
        return token
    return ""  # unreachable but satisfies type checker


def fetch_compiletimehash() -> bytes:
    """Fetch the compiletimehash from the private GitHub secrets repository.

    Resolution order:

    1. ``SLS_COMPILETIMEHASH`` environment variable (hex string) — used in
       testing and environments without network or gh CLI access.
    2. GitHub Contents API using ``gh auth token`` for authentication.

    Returns:
        Raw bytes of the compiletimehash (expected to be 32 bytes).

    Raises:
        CompileTimeHashError: If the hash cannot be fetched or decoded.
    """
    env_value = os.environ.get("SLS_COMPILETIMEHASH")
    if env_value:
        try:
            return bytes.fromhex(env_value)
        except ValueError as exc:
            raise CompileTimeHashError(f"SLS_COMPILETIMEHASH is not valid hex: {exc}") from exc

    gh_token = _get_gh_token()

    url = f"https://api.github.com/repos/{COMPILETIMEHASH_REPO}/contents/{COMPILETIMEHASH_FILE}"
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = httpx.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CompileTimeHashError(
            f"GitHub API returned {exc.response.status_code} fetching compiletimehash"
        ) from exc
    except httpx.RequestError as exc:
        raise CompileTimeHashError(f"Network error fetching compiletimehash: {exc}") from exc
    finally:
        gh_token = ""

    payload = response.json()
    if "content" not in payload:
        raise CompileTimeHashError("Unexpected GitHub API response — no 'content' field")

    try:
        file_content = base64.b64decode(payload["content"]).decode().strip()
    except Exception as exc:
        raise CompileTimeHashError(f"Failed to decode compiletimehash file content: {exc}") from exc

    try:
        return bytes.fromhex(file_content)
    except ValueError as exc:
        raise CompileTimeHashError(f"compiletimehash.txt content is not valid hex: {exc}") from exc
