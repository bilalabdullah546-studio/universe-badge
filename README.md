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
| badge | Official | GitHub profile, avatar, contribution graph |
| pokedex | **Custom** | Pokédex viewer with sprites via PokéAPI |
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

## Setup

1. Copy `secrets.py.example` to `secrets.py` on the badge
2. Edit with your WiFi credentials and GitHub username
3. Run `./sync.sh` to deploy to badge (badge must be in disk mode)
4. Eject and reset badge

## Sync to Badge

Put badge in disk mode (double-tap RESET), then:

```bash
./sync.sh
diskutil eject /Volumes/BADGER
```

## Credits

- [badger/home](https://github.com/badger/home) — Official badge firmware and apps
- [badger/badgerware](https://github.com/badger/badgerware) — Badge API documentation
- [jamshedd/GitHubUniverse2025BadgerApps](https://github.com/jamshedd/GitHubUniverse2025BadgerApps) — Community sample apps
- [PokéAPI](https://pokeapi.co/) — Pokémon data API
