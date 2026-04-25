#!/usr/bin/env bash
# sync_githooks.sh — Sync git hooks from orchestras/git-hooks
#
# This is the standalone script version of `mise run hooks:sync`.
# Can be called directly without mise (e.g., in CI or bootstrap scripts).
#
# Configuration (read from env or mise.toml env section):
#   GITHOOKS_REPO    — GitHub org/repo (default: orchestras/git-hooks)
#   GITHOOKS_VERSION — Git ref/tag/SHA (default: main)
#   GITHOOKS_PROFILE — Subfolder/profile within the repo (default: python-3.14-uv-ty-ruff)

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/colors.sh" 2>/dev/null || true

HOOKS_REPO="${GITHOOKS_REPO:-orchestras/git-hooks}"
HOOKS_VERSION="${GITHOOKS_VERSION:-main}"
HOOKS_PROFILE="${GITHOOKS_PROFILE:-python-3.14-uv-ty-ruff}"
HOOKS_DEST="config/githooks/hooks"
CACHE_DIR=".mise/.githooks-cache"

echo -e "${CYAN:-}Syncing git hooks from ${HOOKS_REPO}@${HOOKS_VERSION}${ENDCOLOR:-}"
echo "  Profile: ${HOOKS_PROFILE}"
echo "  Destination: ${HOOKS_DEST}"
echo ""

mkdir -p "${CACHE_DIR}" "${HOOKS_DEST}"

# Download tarball
TARBALL="${CACHE_DIR}/hooks-${HOOKS_VERSION}.tar.gz"
if command -v gh &>/dev/null && gh auth status &>/dev/null 2>&1; then
  gh api "repos/${HOOKS_REPO}/tarball/${HOOKS_VERSION}" \
    --header "Accept: application/vnd.github+json" \
    > "${TARBALL}" 2>/dev/null || \
  curl -sSfL "https://github.com/${HOOKS_REPO}/archive/${HOOKS_VERSION}.tar.gz" \
    -o "${TARBALL}"
else
  curl -sSfL "https://github.com/${HOOKS_REPO}/archive/${HOOKS_VERSION}.tar.gz" \
    -o "${TARBALL}"
fi

# Extract
EXTRACT_DIR="${CACHE_DIR}/extracted-${HOOKS_VERSION}"
rm -rf "${EXTRACT_DIR}"
mkdir -p "${EXTRACT_DIR}"
tar -xzf "${TARBALL}" -C "${EXTRACT_DIR}" --strip-components=1

# Look for the profile subfolder first, then fall back to root hooks/
PROFILE_DIR="${EXTRACT_DIR}/${HOOKS_PROFILE}/hooks"
ROOT_DIR="${EXTRACT_DIR}/hooks"

if [ -d "${PROFILE_DIR}" ]; then
  echo -e "Using profile directory: ${HOOKS_PROFILE}/hooks"
  SOURCE_DIR="${PROFILE_DIR}"
elif [ -d "${ROOT_DIR}" ]; then
  echo -e "Using root hooks/ directory"
  SOURCE_DIR="${ROOT_DIR}"
else
  echo -e "${YELLOW:-}WARNING: No hooks directory found.${ENDCOLOR:-}"
  echo "Expected: ${HOOKS_PROFILE}/hooks/ or hooks/"
  ls "${EXTRACT_DIR}" || true
  exit 0
fi

# Sync hooks
cp -r "${SOURCE_DIR}/." "${HOOKS_DEST}/"
find "${HOOKS_DEST}" -type f -exec chmod +x {} \;

echo -e "${GREEN:-}✓ Hooks synced → ${HOOKS_DEST}/${ENDCOLOR:-}"
echo ""
echo "Installed hooks:"
for f in "${HOOKS_DEST}"/*; do
  [ -f "$f" ] && echo "  - $(basename "$f")"
done

# Register with git
git config --local core.hooksPath "${HOOKS_DEST}"
echo ""
echo -e "${GREEN:-}✓ core.hooksPath set to ${HOOKS_DEST}${ENDCOLOR:-}"
