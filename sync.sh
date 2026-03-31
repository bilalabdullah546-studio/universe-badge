#!/bin/bash
# Sync local repo to BADGER badge volume
# Usage: ./sync.sh

BADGE_VOLUME="/Volumes/BADGER"

if [ ! -d "$BADGE_VOLUME" ]; then
    echo "Badge not mounted at $BADGE_VOLUME"
    echo "Put badge in disk mode (double-tap RESET) and try again."
    exit 1
fi

echo "Syncing to badge..."
rsync -av --delete \
    --exclude='.git' \
    --exclude='.gitignore' \
    --exclude='secrets.py' \
    --exclude='README.md' \
    --exclude='sync.sh' \
    --exclude='secrets.py.example' \
    --exclude='.DS_Store' \
    ./ "$BADGE_VOLUME/"

echo ""
echo "Sync complete. Don't forget to check secrets.py on the badge."
echo "Eject with: diskutil eject $BADGE_VOLUME"
