#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Portable semver utility — no external dependencies required.
# Usage: scripts/semver.sh bump patch 1.2.3 → 1.2.4
#        scripts/semver.sh compare 1.2.3 1.2.4 → -1

set -o errexit -o nounset -o pipefail

NAT='0|[1-9][0-9]*'
ALPHANUM='[0-9]*[A-Za-z-][0-9A-Za-z-]*'
IDENT="$NAT|$ALPHANUM"
FIELD='[0-9A-Za-z-]+'

SEMVER_REGEX="\
^[vV]?\
($NAT)\\.($NAT)\\.($NAT)\
(\\-(${IDENT})(\\.(${IDENT}))*)?\
(\\+${FIELD}(\\.${FIELD})*)?$"

PROG=semver
PROG_VERSION="3.4.0"

function error { echo -e "$1" >&2; exit 1; }

function validate_version {
  local version=$1
  if [[ "$version" =~ $SEMVER_REGEX ]]; then
    if [ "$#" -eq "2" ]; then
      local major=${BASH_REMATCH[1]}
      local minor=${BASH_REMATCH[2]}
      local patch=${BASH_REMATCH[3]}
      local prere=${BASH_REMATCH[4]}
      local build=${BASH_REMATCH[8]}
      eval "$2=(\"$major\" \"$minor\" \"$patch\" \"$prere\" \"$build\")"
    else
      echo "$version"
    fi
  else
    error "version $version does not match the semver scheme 'X.Y.Z(-PRERELEASE)(+BUILD)'."
  fi
}

function is_nat { [[ "$1" =~ ^($NAT)$ ]]; }
function is_null { [ -z "$1" ]; }
function order_nat { [ "$1" -lt "$2" ] && { echo -1; return; }; [ "$1" -gt "$2" ] && { echo 1; return; }; echo 0; }
function order_string { [[ $1 < $2 ]] && { echo -1; return; }; [[ $1 > $2 ]] && { echo 1; return; }; echo 0; }

function normalize_part {
  if [ "$1" == "prerelease" ]; then echo "prerel"; else echo "$1"; fi
}

function compare_fields {
  local l="$1[@]" r="$2[@]"
  local leftfield=("${!l}") rightfield=("${!r}")
  local left right i=$((-1)) order=0
  while true; do
    [ $order -ne 0 ] && { echo $order; return; }
    : $((i++))
    left="${leftfield[$i]}"; right="${rightfield[$i]}"
    is_null "$left" && is_null "$right" && { echo 0; return; }
    is_null "$left" && { echo -1; return; }
    is_null "$right" && { echo 1; return; }
    is_nat "$left" && is_nat "$right" && { order=$(order_nat "$left" "$right"); continue; }
    is_nat "$left" && { echo -1; return; }
    is_nat "$right" && { echo 1; return; }
    { order=$(order_string "$left" "$right"); continue; }
  done
}

# shellcheck disable=SC2206
function compare_version {
  local order
  validate_version "$1" V
  validate_version "$2" V_
  local left=("${V[0]}" "${V[1]}" "${V[2]}") right=("${V_[0]}" "${V_[1]}" "${V_[2]}")
  order=$(compare_fields left right)
  [ "$order" -ne 0 ] && { echo "$order"; return; }
  local prerel="${V[3]:1}" prerel_="${V_[3]:1}"
  # shellcheck disable=SC2206
  local left=(${prerel//./ }) right=(${prerel_//./ })
  [ -z "$prerel" ] && [ -z "$prerel_" ] && { echo 0; return; }
  [ -z "$prerel" ] && { echo 1; return; }
  [ -z "$prerel_" ] && { echo -1; return; }
  compare_fields left right
}

function render_prerel {
  if [ -z "$2" ]; then echo "${1}"; else echo "${2}${1}"; fi
}

PREFIX_ALPHANUM='[.0-9A-Za-z-]*[.A-Za-z-]'
DIGITS='[0-9][0-9]*'
EXTRACT_REGEX="^(${PREFIX_ALPHANUM})*(${DIGITS})$"

function extract_prerel {
  local prefix numeric
  if [[ "$1" =~ $EXTRACT_REGEX ]]; then
    prefix="${BASH_REMATCH[1]}"; numeric="${BASH_REMATCH[2]}"
  else
    prefix="${1}"; numeric=
  fi
  eval "$2=(\"$prefix\" \"$numeric\")"
}

function bump_prerel {
  local proto prev_prefix prev_numeric
  if [[ ! ("$1" =~ \.$) ]]; then echo "$1"; return; fi
  proto="${1%.}"
  extract_prerel "${2#-}" prerel_parts
  # shellcheck disable=SC2154
  prev_prefix="${prerel_parts[0]}"; prev_numeric="${prerel_parts[1]}"
  if [ "$proto" == "+" ]; then
    if [ -n "$prev_numeric" ]; then
      : $((++prev_numeric)); render_prerel "$prev_numeric" "$prev_prefix"
    else
      render_prerel 1 "$prev_prefix"
    fi
    return
  fi
  if [ "$prev_prefix" != "$proto" ]; then
    render_prerel 1 "$proto"
  elif [ -n "$prev_numeric" ]; then
    : $((++prev_numeric)); render_prerel "$prev_numeric" "$prev_prefix"
  else
    render_prerel 1 "$prev_prefix"
  fi
}

function command_bump {
  local new version sub_version command
  command="$(normalize_part "$1")"
  case $# in
    2) case "$command" in
         major|minor|patch|prerel|release) sub_version="+."; version=$2;;
         *) error "Unknown bump part: $command";;
       esac ;;
    3) case "$command" in
         prerel|build) sub_version=$2; version=$3;;
         *) error "Unknown bump part: $command";;
       esac ;;
    *) error "Wrong number of arguments for bump";;
  esac
  validate_version "$version" parts
  # shellcheck disable=SC2154
  local major="${parts[0]}" minor="${parts[1]}" patch="${parts[2]}" prere="${parts[3]}" build="${parts[4]}"
  case "$command" in
    major)   new="$((major + 1)).0.0";;
    minor)   new="${major}.$((minor + 1)).0";;
    patch)   new="${major}.${minor}.$((patch + 1))";;
    release) new="${major}.${minor}.${patch}";;
    prerel)  new=$(validate_version "${major}.${minor}.${patch}-$(bump_prerel "$sub_version" "$prere")");;
    build)   new=$(validate_version "${major}.${minor}.${patch}${prere}+${sub_version}");;
    *)       error "Unknown command: $command";;
  esac
  echo "$new"
}

function command_get {
  [ "$#" -ne "2" ] && error "Usage: semver get <part> <version>"
  local part="$1" version="$2"
  validate_version "$version" parts
  # shellcheck disable=SC2154
  local major="${parts[0]}" minor="${parts[1]}" patch="${parts[2]}"
  local prerel="${parts[3]:1}" build="${parts[4]:1}"
  local release="${major}.${minor}.${patch}"
  part="$(normalize_part "$part")"
  case "$part" in
    major|minor|patch|release|prerel|build) echo "${!part}";;
    *) error "Unknown part: $part";;
  esac
}

function command_compare {
  [ "$#" -ne "2" ] && error "Usage: semver compare <v1> <v2>"
  local v v_
  v=$(validate_version "$1"); v_=$(validate_version "$2")
  set +u
  compare_version "$v" "$v_"
}

function command_diff {
  validate_version "$1" v1_parts
  validate_version "$2" v2_parts
  # shellcheck disable=SC2154
  if   [ "${v1_parts[0]}" != "${v2_parts[0]}" ]; then echo "major"
  elif [ "${v1_parts[1]}" != "${v2_parts[1]}" ]; then echo "minor"
  elif [ "${v1_parts[2]}" != "${v2_parts[2]}" ]; then echo "patch"
  elif [ "${v1_parts[3]}" != "${v2_parts[3]}" ]; then echo "prerelease"
  elif [ "${v1_parts[4]}" != "${v2_parts[4]}" ]; then echo "build"
  fi
}

function command_validate {
  [ "$#" -ne "1" ] && error "Usage: semver validate <version>"
  if [[ "$1" =~ $SEMVER_REGEX ]]; then echo "valid"; else echo "invalid"; fi
}

case $# in
  0) error "Usage: semver <bump|get|compare|diff|validate> ...";;
esac

case $1 in
  --help|-h)    echo "semver ${PROG_VERSION} — bump/compare/validate semver strings"; exit 0;;
  --version|-v) echo "${PROG}: ${PROG_VERSION}"; exit 0;;
  bump)     shift; command_bump "$@";;
  get)      shift; command_get "$@";;
  compare)  shift; command_compare "$@";;
  diff)     shift; command_diff "$@";;
  validate) shift; command_validate "$@";;
  *)        error "Unknown command: $1";;
esac
