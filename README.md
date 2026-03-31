# GitHub Universe '25 Badge

Custom firmware for my GitHub Universe 2025 hackable badge (Pimoroni Tufty 2350).

## Hardware

- **MCU:** RP2350B @ 200MHz
- **Display:** 160x120 colour LCD
- **Connectivity:** WiFi, Bluetooth 5.2
- **Framework:** MicroPython + badgeware (MonaOS)

## Apps

| App | Source | Description |
|-----|--------|-------------|
| badge | Custom | GitHub profile, avatar, contribution graph (teal theme) |
| pokedex | **Custom** | Gen 1 Pokedex with shiny sprites, sparkle effects, stat bars |
| quest | Official | Mona's Quest game |
| monapet | Official | Virtual Mona pet |
| sketch | Official | Drawing app |
| flappy | Official | Flappy Mona game |
| gallery | Official | Image gallery |
| snake | Official | Snake game |
| invaders | Official | Space Invaders |
| gitris | Official | Tetris clone |
| jezzball | Official | JezzBall game |
| life | Official | Conway's Game of Life |
| pac-man | Community | Pac-Man arcade game |
| pong | Community | Pong game |
| commits | Official | GitHub commit visualiser |
| weather | Official | Weather display |
| wifi | Official | WiFi utility |

## Pokedex App

Custom-built Pokedex for the badge featuring all 151 Gen 1 Pokemon.

**Features:**
- Instant data loading from local database (12KB, no WiFi needed)
- Normal and shiny sprites with animated sparkles
- Floating bob animation on sprites
- Type badges, stat bars, height/weight display
- A/C to navigate, B for random, UP to toggle shiny

**Controls:**
| Button | Action |
|--------|--------|
| A | Previous Pokemon |
| C | Next Pokemon |
| B | Random Pokemon |
| UP | Toggle shiny/normal |
| A+C hold | Force refresh sprite |

### Sprite Setup

Sprites are not included in this repo (Nintendo/Game Freak copyright). Fetch them:

```bash
cd apps/pokedex
python3 fetch_sprites.py          # Downloads to local ./sprites/ and ./shiny/
python3 fetch_sprites.py /Volumes/BADGER  # Downloads directly to badge
```

## Setup

1. Copy `secrets.py.example` to `secrets.py` on the badge
2. Edit with your WiFi credentials and GitHub username
3. Fetch Pokedex sprites (see above)
4. Run `./sync.sh` to deploy to badge (badge must be in disk mode)
5. Eject and reset badge

## Sync to Badge

Put badge in disk mode (double-tap RESET), then:

```bash
./sync.sh
diskutil unmountDisk force /Volumes/BADGER
```

## Credits

- [badger/home](https://github.com/badger/home) — Official badge firmware and apps
- [badger/badgerware](https://github.com/badger/badgerware) — Badge API documentation
- [PokeAPI](https://pokeapi.co/) — Pokemon data API (BSD 3-Clause)

## Disclaimer

Pokemon and Pokemon character names are trademarks of Nintendo/Game Freak/The Pokemon Company. This is a fan project for personal use on a conference badge, with no commercial intent. Sprite artwork is fetched from PokeAPI at install time and is not distributed with this repository.
