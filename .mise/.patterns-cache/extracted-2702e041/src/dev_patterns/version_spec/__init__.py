"""Version-spec resolution for hooks channels.

Supports three specification formats (in priority order):

1. **mise.toml env vars** — ``GITHOOKS_VERSION``, ``GITHOOKS_REPO``, ``GITHOOKS_PROFILE``
   Read from the current project's ``mise.toml`` or from environment variables.

2. **New .githooks-version format** — ``repo/folder/version``, e.g.::

       orchestras/dev-patterns/python3a/v0.1.2

3. **Old .githooks-version format** — bare version tag, e.g.::

       v0.1.12

   Falls back to the default directory inside the hooks repo.

Resolution result exposes ``repo``, ``channel``, ``version`` and ``use_release``
so callers can decide whether to download a release tarball or a branch/SHA.
"""

from dev_patterns.version_spec.resolver import VersionSpec, VersionSpecResolver

__all__ = ["VersionSpec", "VersionSpecResolver"]
