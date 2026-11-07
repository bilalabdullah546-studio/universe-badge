#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SYNC_SCRIPT="$ROOT/sync.sh"
cd "$ROOT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin" "$TMP/badge/apps"
export BADGE_VOLUME="$TMP/badge"
export CALL_LOG="$TMP/calls.log"
export PATH="$TMP/bin:$PATH"

cat > "$TMP/bin/rsync" <<'STUB'
#!/bin/bash
printf 'rsync %s\n' "$*" >> "$CALL_LOG"
STUB
cat > "$TMP/bin/dot_clean" <<'STUB'
#!/bin/bash
printf 'dot_clean %s\n' "$*" >> "$CALL_LOG"
exit 1
STUB
chmod +x "$TMP/bin/rsync" "$TMP/bin/dot_clean"

fail() {
    echo "FAIL: $1" >&2
    exit 1
}

# No argument must only issue dry-run commands and must not call dot_clean.
: > "$CALL_LOG"
"$SYNC_SCRIPT" > "$TMP/default.out"
grep -q '^rsync .*--dry-run' "$CALL_LOG" || fail "default invocation did not use rsync --dry-run"
if grep -q '^dot_clean ' "$CALL_LOG"; then fail "default invocation called dot_clean"; fi
grep -q 'Dry run complete; no files were changed' "$TMP/default.out" || fail "default output did not identify dry-run mode"

# --apply must not write unless the exact confirmation is supplied.
: > "$CALL_LOG"
if printf 'NO\n' | "$SYNC_SCRIPT" --apply > "$TMP/cancel.out" 2>&1; then
    fail "--apply accepted an unconfirmed response"
fi
[ ! -s "$CALL_LOG" ] || fail "cancelled --apply invoked a write command"

# Confirmed --apply may write and runs dot_clean only after confirmation.
: > "$CALL_LOG"
printf 'APPLY\n' | "$SYNC_SCRIPT" --apply > "$TMP/apply.out"
grep -q '^rsync ' "$CALL_LOG" || fail "confirmed --apply did not invoke rsync"
if grep -q '^rsync .*--dry-run' "$CALL_LOG"; then fail "confirmed --apply unexpectedly used dry-run"; fi
grep -q '^dot_clean ' "$CALL_LOG" || fail "confirmed --apply did not run dot_clean"
grep -q 'Sync complete\.' "$TMP/apply.out" || fail "best-effort dot_clean failure interrupted the sync"

# A directory without the expected apps folder must be rejected before rsync.
mkdir -p "$TMP/unexpected"
: > "$CALL_LOG"
if BADGE_VOLUME="$TMP/unexpected" "$SYNC_SCRIPT" --dry-run > "$TMP/missing-apps.out" 2>&1; then
    fail "unexpected directory was accepted"
fi
[ ! -s "$CALL_LOG" ] || fail "unexpected directory reached rsync"

echo "PASS: sync safety tests"
