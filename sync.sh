#!/bin/bash
# Sync local repo to the BADGER badge volume.
# Usage: ./sync.sh [--dry-run|--apply]
# The default is a non-destructive dry run. Use --apply to write to the device.

set -euo pipefail

BADGE_VOLUME="${BADGE_VOLUME:-/Volumes/BADGER}"
MODE="--dry-run"
if [ "$#" -gt 1 ]; then
    echo "Usage: $0 [--dry-run|--apply]"
    exit 2
fi
if [ "$#" -eq 1 ]; then
    MODE="$1"
fi

case "$MODE" in
    --dry-run|--apply) ;;
    *)
        echo "Usage: $0 [--dry-run|--apply]"
        exit 2
        ;;
esac

if [ ! -d "$BADGE_VOLUME" ]; then
    echo "Badge volume not mounted at $BADGE_VOLUME"
    echo "Put badge in disk mode (double-tap RESET) and try again."
    exit 1
fi

if [ ! -d "$BADGE_VOLUME/apps" ]; then
    echo "Expected badge apps directory not found at $BADGE_VOLUME/apps"
    echo "Refusing to sync to an unexpected volume or directory."
    exit 1
fi

if [ "$MODE" = "--apply" ]; then
    echo "WARNING: this sync uses rsync --delete and may remove files from $BADGE_VOLUME/apps/"
    read -r -p "Type APPLY to continue: " confirmation
    if [ "$confirmation" != "APPLY" ]; then
        echo "Sync cancelled. No files were changed."
        exit 1
    fi
fi

RSYNC_ARGS=(-av --delete)
if [ "$MODE" = "--dry-run" ]; then
    RSYNC_ARGS+=(--dry-run)
fi

echo "Syncing apps to badge ($MODE)..."
rsync "${RSYNC_ARGS[@]}" \
    --exclude='.git' \
    --exclude='.gitignore' \
    --exclude='secrets.py' \
    --exclude='README.md' \
    --exclude='sync.sh' \
    --exclude='secrets.py.example' \
    --exclude='.DS_Store' \
    --exclude='CLAUDE.md' \
    --exclude='fetch_sprites.py' \
    --exclude='sprites/' \
    --exclude='shiny/' \
    ./apps/ "$BADGE_VOLUME/apps/"

# Sync sprites if they exist locally. Keep the same dry-run/apply mode.
if [ -d "./apps/pokedex/sprites" ]; then
    echo "Syncing normal sprites..."
    if [ "$MODE" = "--dry-run" ]; then
        rsync -av --dry-run ./apps/pokedex/sprites/ "$BADGE_VOLUME/sprites/"
    else
        rsync -av ./apps/pokedex/sprites/ "$BADGE_VOLUME/sprites/"
    fi
fi

if [ -d "./apps/pokedex/shiny" ]; then
    echo "Syncing shiny sprites..."
    if [ "$MODE" = "--dry-run" ]; then
        rsync -av --dry-run ./apps/pokedex/shiny/ "$BADGE_VOLUME/shiny/"
    else
        rsync -av ./apps/pokedex/shiny/ "$BADGE_VOLUME/shiny/"
    fi
fi

if [ "$MODE" = "--apply" ]; then
    # Clean macOS resource forks only after an explicitly confirmed write.
    dot_clean -m "$BADGE_VOLUME/" 2>/dev/null
    echo "Sync complete."
else
    echo "Dry run complete; no files were changed."
    echo "Review the rsync output, then run ./sync.sh --apply to write to the badge."
fi
