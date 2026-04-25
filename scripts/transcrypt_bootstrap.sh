#!/usr/bin/env bash
# transcrypt_bootstrap.sh — Bootstrap transcrypt for encrypted file support
#
# Usage: source ./scripts/transcrypt_bootstrap.sh && transcrypt_bootstrap
#
# Checks for a TRANSCRYPT_PASSWORD env var or prompts interactively.
# If .transcrypt/config exists, uses that to configure; otherwise initialises fresh.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/colors.sh" 2>/dev/null || true

transcrypt_bootstrap() {
  if ! command -v transcrypt &>/dev/null; then
    echo -e "${YELLOW:-}WARNING: transcrypt not found.${ENDCOLOR:-}"
    echo "Install it: https://github.com/elasticdog/transcrypt"
    echo "  macOS:  brew install transcrypt"
    echo "  Linux:  see https://github.com/elasticdog/transcrypt#installation"
    return 1
  fi

  # Determine cipher (default: aes-256-cbc)
  local cipher="${TRANSCRYPT_CIPHER:-aes-256-cbc}"

  # Check if already initialised
  if [ -f ".transcrypt/config" ]; then
    echo "transcrypt already initialised for this repo."
    transcrypt --list 2>/dev/null || true
    return 0
  fi

  # Resolve password
  local password="${TRANSCRYPT_PASSWORD:-}"
  if [ -z "$password" ]; then
    if [ -t 0 ]; then
      read -rsp "transcrypt password: " password
      echo ""
    else
      echo -e "${RED:-}ERROR: TRANSCRYPT_PASSWORD env var not set and no TTY available.${ENDCOLOR:-}"
      return 1
    fi
  fi

  transcrypt --cipher="$cipher" --password="$password" --yes
  echo -e "${GREEN:-}✓ transcrypt initialised (cipher: ${cipher})${ENDCOLOR:-}"
}
