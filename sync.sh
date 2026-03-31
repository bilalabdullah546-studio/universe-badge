#!/bin/bash
# Sync local repo to BADGER badge volume
# Usage: ./sync.sh

BADGE_VOLUME="/Volumes/BADGER"

if [ ! -d "$BADGE_VOLUME" ]; then
    echo "Badge not mounted at $BADGE_VOLUME"
    echo "Put badge in disk mode (double-tap RESET) and try again."
    exit 1
fi

echo "Syncing apps to badge..."
rsync -av --delete \
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

# Sync sprites if they exist locally
if [ -d "./apps/pokedex/sprites" ]; then
    echo "Syncing normal sprites..."
    rsync -av ./apps/pokedex/sprites/ "$BADGE_VOLUME/sprites/"
fi

if [ -d "./apps/pokedex/shiny" ]; then
    echo "Syncing shiny sprites..."
    rsync -av ./apps/pokedex/shiny/ "$BADGE_VOLUME/shiny/"
fi

# Clean macOS resource forks
dot_clean -m "$BADGE_VOLUME/" 2>/dev/null

echo ""
echo "Sync complete."
echo "Eject with: diskutil unmountDisk force $BADGE_VOLUME"
