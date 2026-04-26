# sls — Short-Lived Secrets

> Time-boxed encrypted secret injection from KeePass databases.

`sls` (Short-Lived Secrets) pulls secrets from KeePass in a single brief batch operation,
immediately encrypts them using a multi-factor key, and stores them in `/tmp` as encrypted
blobs. The safe closes immediately after the pull. Subsequently, any program that needs
those secrets calls `sls push <command>`, which decrypts the cache into memory and injects
the secrets as environment variables scoped exclusively to the target child process.

Secrets never persist after the process exits. The cache expires after **28,800 seconds
(8 hours)** from acquiesce time.

---

## Quick Start

```bash
# Install
pip install sls   # or: uv add sls

# 1. Pull all secrets from a KeePass group and write the encrypted cache
sls pull group /path/to/safe.kdbx generic

# 2. Run a command with secrets injected as environment variables
sls push terraform plan

# 3. Check cache health
sls status
# → Cache active. TTL remaining: 25603s (07:06:43)

# 4. Force cache invalidation
sls rotate
```

---

## Design Principles

- **The safe opens once per batch, closes immediately.** No persistent connection to KeePass.
- **No secret ever touches disk in plaintext.** Passwords are read into memory only.
  Cache files are AES-256-GCM encrypted at rest.
- **Compromise of any single component yields nothing.** All five key ingredients must be
  simultaneously available to derive the cache decryption key.

---

## Commands

| Command | Description |
|---------|-------------|
| `sls pull group <db> <group>` | Pull all entries in a KeePass group → write encrypted cache |
| `sls pull entry <db> <path>` | Pull a single entry → print value to stdout |
| `sls acquiesce` | Read `KEY=VALUE` pairs from stdin → write encrypted cache |
| `sls push <command> [args...]` | Decrypt cache → exec command with secrets as env vars |
| `sls rotate` | Rotate session key material — old cache permanently unreadable |
| `sls status` | Show cache TTL remaining (no decryption performed) |

### `sls pull group`

```bash
sls pull group /path/to/secrets.kdbx DevSecrets
# → KeePass password: ****
# → Secrets cached (5 entries from 'DevSecrets'). TTL: 28800s
```

Prompts for the KeePass master password interactively (never supplied on the command line).
Pulls all entries from the named group. Entry titles become environment variable names;
entry passwords become the values.

### `sls pull entry`

```bash
sls pull entry /path/to/secrets.kdbx "DevSecrets/API_TOKEN"
# → KeePass password: ****
# prints the API_TOKEN value to stdout
```

### `sls acquiesce`

```bash
echo "API_TOKEN=secret123\nDB_PASS=hunter2" | sls acquiesce
# → Secrets cached (2 entries). TTL: 28800s
```

Reads `KEY=VALUE` pairs from stdin — the safe-side counterpart is your shell function
(e.g., fish) that opens KeePass, assembles the payload, and pipes it here. Secrets are
**never supplied as CLI arguments** (hidden from `ps aux`).

### `sls push`

```bash
sls push terraform plan
sls push docker build --secret env=MY_TOKEN .
sls push -- python my_script.py --arg value
```

Decrypts the cache entirely in memory and executes the target command with secrets added
to its environment. The secrets exist only for the duration of the child process.

### `sls rotate`

```bash
sls rotate
# → Cache rotated. Old /tmp entries are permanently unreadable.
```

Generates new session key material and writes it to the Keychain. Old `/tmp` cache
directories become permanently unreadable (the keys to derive their names and decrypt
their contents are gone).

### `sls status`

```bash
sls status
# → Cache active. TTL remaining: 25603s (07:06:43)
# or
# → Cache expired. Run 'sls acquiesce'.
```

---

## Key Material & Security

The cache is protected by five independent key components, all of which must be
simultaneously available to decrypt it:

| Component | Source | Rotates |
|-----------|--------|---------|
| `systemhash` | 32 random bytes → Keychain | Every acquiesce/rotate |
| `session_nonce` | 32 random bytes → Keychain | Every acquiesce/rotate |
| `session_start` | Epoch timestamp → Keychain | Every acquiesce/rotate |
| `gh_auth_token` | `gh auth token` → memory | On org SSO policy |
| `compiletimehash` | Private GitHub repo → memory | Manual (repo commit) |

All encryption uses **AES-256-GCM** (authenticated encryption). The GCM authentication
tag prevents bit-flipping attacks against the cache files. Cache directory names are
derived from the key material so that an attacker cannot even locate the files without
the binary algorithm.

### Environment Variable Override (for testing)

```bash
export SLS_COMPILETIMEHASH="aabbccdd..."  # 64-char hex string (32 bytes)
```

Setting `SLS_COMPILETIMEHASH` bypasses the GitHub API fetch. **Never use this in
production** — it defeats the network-bound key component.

---

## Development

```bash
# Install dev dependencies
mise run install      # or: uv sync

# Run tests
mise run test         # or: uv run pytest

# Run with coverage
mise run test:cov

# Lint
mise run lint         # ruff check

# Format
mise run fmt          # ruff format

# Type check
mise run typecheck    # ty check

# Full CI pipeline
mise run ci:all

# Sync hooks and tasks from orchestras/dev-patterns
mise run patterns:sync
```

---

## Repository Structure

```
src/sls/
  __main__.py           ← CLI entry point (argparse)
  version.py            ← auto-generated — do NOT edit
  commands/
    acquiesce.py        ← sls acquiesce
    push.py             ← sls push
    rotate.py           ← sls rotate
    status.py           ← sls status
    pull.py             ← sls pull group / sls pull entry
  core/
    base.py             ← BaseCommand, CommandResult, ExitCode
    config.py           ← non-secret constants (TTL, key names, etc.)
    cache.py            ← CacheWriter + CacheReader (encrypted /tmp files)
    session.py          ← session lifecycle (Keychain I/O, key derivation)
  crypto/
    aes.py              ← AES-256-GCM encrypt/decrypt wrappers
    dayhash.py          ← dayhash derivation (DerivedKeys)
    keys.py             ← key generation and zeroing helpers
  github/
    compiletimehash.py  ← runtime fetch from private secrets repo
  keepass/
    reader.py           ← KeePass .kdbx read (pykeepass wrapper)
```

---

## License

MIT — see [LICENSE](LICENSE).
