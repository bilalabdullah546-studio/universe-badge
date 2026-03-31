"""Pac-Man clone for the Tufty badge.

This module delivers the full Pac-Man experience scoped in ``project/proposal.md``
for RP2350-based Tufty hardware. The implementation is intentionally kept within
one MicroPython source file, relies solely on ``badgeware`` plus standard
MicroPython modules, and renders using primitive drawing routines so it executes
comfortably within the badge's constraints.

Gameplay highlights
-------------------
* Four ghosts running classic scatter/chase/frightened cycles.
* Toroidal wrap so leaving any edge reappears at the opposite edge.
* Power pellets that trigger frightened mode with combo scoring.
* Bonus fruits that spawn mid-round for hefty score boosts.
* Session-long score retention, start/gameplay/level-clear/game-over screens.
* Gradual, capped speed increases to maintain an easy-to-moderate challenge.

The file is organised into sections: constants/data, helper utilities, gameplay
state containers, update logic, rendering, and the main loop entry point.
"""

import math
import urandom

from badgeware import screen, io, brushes, shapes, run, PixelFont


# ---------------------------------------------------------------------------
# Display configuration, fonts, and colour palette
# ---------------------------------------------------------------------------

WIDTH = screen.width
HEIGHT = screen.height

HUD_FONT = PixelFont.load("/system/assets/fonts/ark.ppf")
TITLE_FONT = PixelFont.load("/system/assets/fonts/absolute.ppf")
PROMPT_FONT = PixelFont.load("/system/assets/fonts/ziplock.ppf")
screen.font = HUD_FONT


def measure_text(text: str, font=HUD_FONT, scale: float = 1.0):
    previous = screen.font
    screen.font = font
    width, height = screen.measure_text(text)
    screen.font = previous
    return width * scale, height * scale


def draw_text(text: str, x: int, y: int, color, font=HUD_FONT, scale: float = 1.0) -> None:
    previous = screen.font
    screen.font = font
    screen.brush = color
    if scale != 1.0:
        try:
            screen.text(text, int(x), int(y), scale)
        except TypeError:
            screen.text(text, int(x), int(y))
    else:
        screen.text(text, int(x), int(y))
    screen.font = previous


def draw_rect(x: int, y: int, width: int, height: int, color) -> None:
    if width <= 0 or height <= 0:
        return
    screen.brush = color
    screen.draw(
        shapes.rectangle(
            int(x),
            int(y),
            max(1, int(width)),
            max(1, int(height)),
        )
    )


def draw_circle(cx: int, cy: int, radius: int, color) -> None:
    if radius <= 0:
        return
    screen.brush = color
    screen.draw(shapes.circle(int(cx), int(cy), max(1, int(radius))))


# Core palette (deliberately modest for retro aesthetics).
PEN_BACKGROUND = brushes.color(0, 0, 0)
PEN_WALL = brushes.color(85, 47, 100)
PEN_PELLET = brushes.color(180, 180, 180)
PEN_POWER = brushes.color(120, 220, 255)
PEN_PLAYER = brushes.color(255, 220, 0)
PEN_PLAYER_ALT = brushes.color(255, 190, 0)
PEN_GHOST_RED = brushes.color(255, 60, 60)
PEN_GHOST_GREEN = brushes.color(110, 220, 140)
PEN_GHOST_ORANGE = brushes.color(255, 150, 40)
PEN_GHOST_PINK = brushes.color(255, 130, 200)
PEN_GHOST_COLOURS = [
    PEN_GHOST_RED,
    PEN_GHOST_GREEN,
    PEN_GHOST_ORANGE,
    PEN_GHOST_PINK,
]
PEN_GHOST_FRIGHT = brushes.color(40, 80, 255)
PEN_GHOST_FLASH = brushes.color(255, 255, 255)
PEN_GHOST_EYE_WHITE = brushes.color(255, 255, 255)
PEN_GHOST_EYE_PUPIL = brushes.color(0, 60, 255)
PEN_TEXT = brushes.color(240, 240, 240)
PEN_TEXT_DIM = brushes.color(140, 140, 140)
PEN_TEXT_WARN = brushes.color(255, 200, 80)
PEN_LIVES = brushes.color(255, 200, 0)
PEN_LIFE_EMPTY = brushes.color(60, 60, 60)
PEN_FRUIT_STEM = brushes.color(60, 200, 70)
PEN_FRUIT_RED = brushes.color(255, 60, 100)
PEN_FRUIT_PINK = brushes.color(255, 120, 210)
PEN_FRUIT_ORANGE = brushes.color(255, 170, 60)
PEN_FRUIT_GREEN = brushes.color(140, 240, 120)
PEN_FRUIT_BLUE = brushes.color(120, 200, 255)

# ---------------------------------------------------------------------------
# Timing and gameplay constants
# ---------------------------------------------------------------------------

MAX_FRAME_JITTER_MS = 120
MAX_DT_SECONDS = MAX_FRAME_JITTER_MS / 1000.0
TEST_PATTERN_ENABLED = False
TEST_PATTERN_DURATION_MS = 3000
TILE_WIDTH = 6
TILE_HEIGHT = 5
TILE_STEP = TILE_HEIGHT

MAZE_COLS = 23
MAZE_ROWS = 23
PELLET_SCORE = 10
POWER_PELLET_SCORE = 50
GHOST_BASE_SCORE = 200

INITIAL_LIVES = 5

PLAYER_SPEED_TILES = [7.2, 8.4, 9.6, 10.8]
GHOST_SPEED_TILES = [6.6, 7.8, 9.0, 10.2]
FRIGHTENED_SPEED_FACTOR = 0.6  # ghosts slow down in frightened mode

FRIGHTENED_DURATION_MS = 6000
FRIGHTENED_FLASH_START_MS = 3500

READY_PAUSE_MS = 1500
LEVEL_CLEAR_MS = 2000
GAME_OVER_FLASH_MS = 300
START_PROMPT_FLASH_MS = 400

SCATTER_CHASE_SCRIPT = (
    (7000, 20000),
    (7000, 20000),
    (5000, 20000),
    (5000, 0),  # final entry: chase duration 0 = stay in chase indefinitely
)

# Directions expressed as (dx, dy).
DIR_NONE = (0, 0)
DIR_UP = (0, -1)
DIR_DOWN = (0, 1)
DIR_LEFT = (-1, 0)
DIR_RIGHT = (1, 0)

DIRECTION_ORDER = (DIR_UP, DIR_LEFT, DIR_DOWN, DIR_RIGHT)

# Button mappings for readability.
BUTTON_LEFT = io.BUTTON_A
BUTTON_RIGHT = io.BUTTON_C
BUTTON_UP = getattr(io, "BUTTON_UP", io.BUTTON_A)
BUTTON_DOWN = getattr(io, "BUTTON_DOWN", io.BUTTON_C)
BUTTON_START = io.BUTTON_A  # Primary start/select button placeholder
BUTTON_ALT_START = io.BUTTON_C
BUTTON_EXIT = io.BUTTON_B

# Tile encoding.
TILE_EMPTY = 0
TILE_WALL = 1

PELLET_NONE = 0
PELLET_SMALL = 1
PELLET_POWER = 2

# UI positions.
HUD_MARGIN = 8
HUD_LINE_HEIGHT = 14

# Sprite sizing tweaks to keep characters visually prominent.
PLAYER_RENDER_RADIUS = max(3, min(TILE_WIDTH, TILE_HEIGHT) // 2 + 1)
GHOST_RENDER_RADIUS = max(3, min(TILE_WIDTH, TILE_HEIGHT) // 2)
PLAYER_DRAW_SIZE = PLAYER_RENDER_RADIUS * 2
GHOST_DRAW_SIZE = GHOST_RENDER_RADIUS * 2

FRUIT_TYPES = (
    ("Cherry", 100, PEN_FRUIT_RED),
    ("Strawberry", 300, PEN_FRUIT_PINK),
    ("Orange", 500, PEN_FRUIT_ORANGE),
    ("Melon", 700, PEN_FRUIT_GREEN),
    ("Galaxian", 1000, PEN_FRUIT_BLUE),
)
FRUIT_DURATION_MS = 9000
FRUIT_FLASH_START_MS = 3000
FRUIT_FLASH_INTERVAL_MS = 200
FRUIT_TRIGGER_COUNTS = (70, 170)
MAX_FRUIT_HISTORY = 6

# ---------------------------------------------------------------------------
# Maze layout definition (23 x 23 tiles)
# ---------------------------------------------------------------------------

MAZE_LAYOUT = [
    "#######################",
    "#...#.............#...#",
    "#o#.#.#####.#####.#.#o#",
    "#.......#.....#.......#",
    "###.#.#.#.###.#.#.#.###",
    "#...#.#.#.# #.#.#.#...#",
    "#.#.#.#.#.###.#.#.#.#.#",
    "#...#.#.........#.#...#",
    "#####.#.#######.#.#####",
    "#.....#.........#.....#",
    "# #####.### ###.##### #",
    "........# GGG #........",
    "# #####.#######.##### #",
    "#.....#....S....#.....#",
    "#####.#.#######.#.#####",
    "#...#.#.........#.#...#",
    "#.#.#.#.#.###.#.#.#.#.#",
    "#...#.#.#.# #.#.#.#...#",
    "###.#.#.#.###.#.#.#.###",
    "#.......#.....#.......#",
    "#o#.#.#####.#####.#.#o#",
    "#...#.............#...#",
    "#######################",
]

MAZE_ROWS = len(MAZE_LAYOUT)
MAZE_COLS = len(MAZE_LAYOUT[0])
MAZE_PIXEL_WIDTH = MAZE_COLS * TILE_WIDTH
MAZE_PIXEL_HEIGHT = MAZE_ROWS * TILE_HEIGHT
MAZE_ORIGIN_X = (WIDTH - MAZE_PIXEL_WIDTH) // 2
MAZE_ORIGIN_Y = (HEIGHT - MAZE_PIXEL_HEIGHT) // 2

# Allowed warp links keyed by (col, row, dx, dy) -> destination (col, row)
PORTAL_ROW = 11
PORTAL_LINKS = {
    (0, PORTAL_ROW, -1, 0): (MAZE_COLS - 1, PORTAL_ROW),
    (MAZE_COLS - 1, PORTAL_ROW, 1, 0): (0, PORTAL_ROW),
}

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def tile_index(col: int, row: int) -> int:
    """Return the linear index for the given tile coordinate."""

    return row * MAZE_COLS + col


def wrap_tile(col: int, row: int):
    """Clamp a tile coordinate to the maze bounds."""

    if col < 0:
        col = 0
    elif col >= MAZE_COLS:
        col = MAZE_COLS - 1
    if row < 0:
        row = 0
    elif row >= MAZE_ROWS:
        row = MAZE_ROWS - 1
    return col, row


def tile_center(col: int, row: int):
    """Convert a tile coordinate to the pixel centre point."""

    return (
        MAZE_ORIGIN_X + col * TILE_WIDTH + TILE_WIDTH / 2,
        MAZE_ORIGIN_Y + row * TILE_HEIGHT + TILE_HEIGHT / 2,
    )


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation helper."""

    return a + (b - a) * t


def direction_opposite(a, b) -> bool:
    """Return ``True`` when direction *a* exactly opposes direction *b*."""

    return a[0] == -b[0] and a[1] == -b[1]


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` range."""

    if value < low:
        return low
    if value > high:
        return high
    return value


def distance_sq(a, b) -> int:
    """Return squared distance between two tile coordinates."""

    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


# ---------------------------------------------------------------------------
# Maze assets and parsing
# ---------------------------------------------------------------------------


class Maze:
    """Container for maze geometry, pellets, and spawn locations."""

    def __init__(self) -> None:
        self.tiles = bytearray(MAZE_COLS * MAZE_ROWS)
        self.pellets = bytearray(MAZE_COLS * MAZE_ROWS)
        self.player_start = (1, MAZE_ROWS - 2)
        self.ghost_starts = []
        self.ghost_house_row = None
        self.ghost_house_min_col = MAZE_COLS
        self.ghost_house_max_col = -1
        self.ghost_door = None
        self.total_pellets = 0
        self._parse_layout()

    def _parse_layout(self) -> None:
        """Translate ``MAZE_LAYOUT`` strings into internal arrays."""

        if len(MAZE_LAYOUT) != MAZE_ROWS:
            raise ValueError("MAZE_LAYOUT height mismatch")

        pellet_count = 0

        for row, line in enumerate(MAZE_LAYOUT):
            if len(line) != MAZE_COLS:
                raise ValueError("MAZE_LAYOUT width mismatch in row {}".format(row))
            for col, char in enumerate(line):
                idx = tile_index(col, row)
                tile = TILE_EMPTY
                pellet = PELLET_NONE

                if char == '#':
                    tile = TILE_WALL
                elif char == '.':
                    pellet = PELLET_SMALL
                elif char == 'o':
                    pellet = PELLET_POWER
                elif char == 'S':
                    self.player_start = (col, row)
                elif char == 'G':
                    # Preserve order to give deterministic ghost corners.
                    self.ghost_starts.append((col, row))
                    if self.ghost_house_row is None:
                        self.ghost_house_row = row
                    self.ghost_house_min_col = min(self.ghost_house_min_col, col)
                    self.ghost_house_max_col = max(self.ghost_house_max_col, col)
                    if row > 0:
                        above_char = MAZE_LAYOUT[row - 1][col]
                        if above_char != '#':
                            self.ghost_door = (col, row - 1)
                elif char == ' ':
                    # Explicit space keeps tile empty with no pellet.
                    pass
                else:
                    # Default to empty tile for unknown markers.
                    pass

                self.tiles[idx] = tile
                self.pellets[idx] = pellet
                if pellet in (PELLET_SMALL, PELLET_POWER):
                    pellet_count += 1

        if len(self.ghost_starts) < 3:
            raise ValueError("MAZE_LAYOUT must include at least three ghost start tiles")
        if self.ghost_starts:
            door_row = self.ghost_house_row - 1 if self.ghost_house_row is not None else None
            if door_row is not None:
                if self.ghost_door is None or self.is_wall(self.ghost_door[0], self.ghost_door[1]):
                    search_start = max(0, self.ghost_house_min_col - 2)
                    search_end = min(MAZE_COLS - 1, self.ghost_house_max_col + 2)
                    for candidate_col in range(search_start, search_end + 1):
                        if not self.is_wall(candidate_col, door_row):
                            self.ghost_door = (candidate_col, door_row)
                            break
                if self.ghost_door is None:
                    first_col, first_row = self.ghost_starts[0]
                    self.ghost_door = (first_col, max(0, first_row - 1))
        self.total_pellets = pellet_count

    def is_wall(self, col: int, row: int) -> bool:
        """Return ``True`` if the tile at ``(col, row)`` is a wall."""

        if col < 0 or col >= MAZE_COLS or row < 0 or row >= MAZE_ROWS:
            return True
        return self.tiles[tile_index(col, row)] == TILE_WALL

    def pellet_at(self, col: int, row: int) -> int:
        """Return pellet code at ``(col, row)`` (0, 1, or 2)."""

        if col < 0 or col >= MAZE_COLS or row < 0 or row >= MAZE_ROWS:
            return PELLET_NONE
        return self.pellets[tile_index(col, row)]

    def consume_pellet(self, col: int, row: int) -> int:
        """Remove and return the pellet code at ``(col, row)``."""

        if col < 0 or col >= MAZE_COLS or row < 0 or row >= MAZE_ROWS:
            return PELLET_NONE

        idx = tile_index(col, row)
        pellet = self.pellets[idx]
        self.pellets[idx] = PELLET_NONE
        if pellet in (PELLET_SMALL, PELLET_POWER):
            self.total_pellets -= 1
        return pellet

    def reset_pellets(self) -> None:
        """Restore pellet placements to the original layout."""

        # Re-parse from layout to avoid storing a second buffer.
        self.__init__()

    def in_ghost_house(self, col: int, row: int) -> bool:
        """Return ``True`` when ``(col, row)`` is inside the ghost home pen."""

        if self.ghost_house_row is None:
            return False
        if row != self.ghost_house_row:
            return False
        return self.ghost_house_min_col <= col <= self.ghost_house_max_col


def initial_ghost_exit_direction(maze: Maze, tile):
    """Return a sensible initial direction to nudge a ghost out of the pen."""

    if maze.ghost_door is None:
        return DIR_UP

    door_col, door_row = maze.ghost_door
    col, row = tile

    if row > door_row:
        if col < door_col:
            return DIR_RIGHT
        if col > door_col:
            return DIR_LEFT
        return DIR_UP

    if row == door_row and row > 0:
        return DIR_UP

    return DIR_UP


# ---------------------------------------------------------------------------
# Entity data structures
# ---------------------------------------------------------------------------


class Mover:
    """Base class for any entity that moves tile-to-tile.

    Attributes:
        tile: Current tile (col, row) where the entity is located.
        direction: Current movement direction expressed as (dx, dy).
        next_tile: The tile being moved towards while ``progress`` > 0.
        progress: Normalised progress (0-1) between ``tile`` and ``next_tile``.
        speed: Movement speed in tiles per second.
        queued_direction: Pending direction change requested by input or AI.
    """

    __slots__ = (
        "tile",
        "direction",
        "next_tile",
        "progress",
        "speed",
        "queued_direction",
    )

    def __init__(self, tile, speed_tiles: float) -> None:
        self.tile = tile
        self.direction = DIR_NONE
        self.next_tile = tile
        self.progress = 0.0
        self.speed = speed_tiles
        self.queued_direction = DIR_NONE

    def world_position(self):
        """Return current pixel position by interpolating between tiles."""

        start = tile_center(*self.tile)
        if self.direction == DIR_NONE or self.progress <= 0.0:
            return start
        dest = tile_center(*self.next_tile)
        return (
            lerp(start[0], dest[0], self.progress),
            lerp(start[1], dest[1], self.progress),
        )


class Player(Mover):
    """Player entity with queued direction logic and animation helpers."""

    __slots__ = ("mouth_timer", "alive", "facing")

    def __init__(self, tile, speed_tiles: float) -> None:
        super().__init__(tile, speed_tiles)
        self.mouth_timer = 0.0
        self.alive = True
        self.facing = DIR_RIGHT


class Ghost(Mover):
    """Ghost entity with behavioural state."""

    __slots__ = (
        "name",
        "home_corner",
        "mode",
        "mode_timer",
        "frightened_timer",
        "flash",
        "capture_value",
    )

    def __init__(self, name, tile, speed_tiles: float, home_corner) -> None:
        super().__init__(tile, speed_tiles)
        self.name = name
        self.home_corner = home_corner
        self.mode = "scatter"
        self.mode_timer = 0
        self.frightened_timer = 0
        self.flash = False
        self.capture_value = GHOST_BASE_SCORE


class GameState:
    """Runtime container holding all mutable game state."""

    __slots__ = (
        "running",
        "mode",
        "maze",
        "player",
        "ghosts",
        "score",
        "session_high",
        "lives",
        "level",
        "ghost_combo",
        "frightened_ms",
        "scatter_index",
        "scatter_elapsed",
        "ready_timer",
        "level_timer",
        "blink_timer",
        "game_over_blink",
        "input_queue",
        "pellets_eaten",
        "fruit_active",
        "fruit_timer",
        "fruit_type_index",
        "fruit_tile",
        "fruit_spawn_queue",
        "fruit_history",
        "fruit_flash",
        "fruit_flash_timer",
        "test_pattern_timer",
    )

    def __init__(self, maze: Maze) -> None:
        self.running = True
        self.mode = "START"
        self.maze = maze
        self.player = Player(maze.player_start, PLAYER_SPEED_TILES[0])
        self.ghosts = []
        self.score = 0
        self.session_high = 0
        self.lives = INITIAL_LIVES
        self.level = 1
        self.ghost_combo = 0
        self.frightened_ms = 0
        self.scatter_index = 0
        self.scatter_elapsed = 0
        self.ready_timer = 0
        self.level_timer = 0
        self.blink_timer = 0
        self.game_over_blink = 0
        self.input_queue = DIR_NONE
        self.pellets_eaten = 0
        self.fruit_active = False
        self.fruit_timer = 0
        self.fruit_type_index = 0
        self.fruit_tile = maze.ghost_door if maze.ghost_door else (MAZE_COLS // 2, MAZE_ROWS // 2)
        if self.maze.is_wall(self.fruit_tile[0], self.fruit_tile[1]):
            self.fruit_tile = (MAZE_COLS // 2, MAZE_ROWS // 2)
        self.fruit_spawn_queue = list(FRUIT_TRIGGER_COUNTS)
        self.fruit_history = []
        self.fruit_flash = False
        self.fruit_flash_timer = 0
        self.test_pattern_timer = 0

    def initialise_ghosts(self) -> None:
        """Create the ghosts for the current level."""

        self.ghosts = []
        starts = list(self.maze.ghost_starts)
        original_starts = list(starts)
        corners = [
            (1, 1),
            (MAZE_COLS - 2, 1),
            (MAZE_COLS - 2, MAZE_ROWS - 2),
            (1, MAZE_ROWS - 2),
        ]
        names = ("BLINKY", "INKY", "PINKY", "CLYDE")
        total_required = len(names)
        house_row = self.maze.ghost_house_row

        if len(starts) < total_required and house_row is not None:
            scan_start = max(0, self.maze.ghost_house_min_col - 1)
            scan_end = min(MAZE_COLS - 1, self.maze.ghost_house_max_col + 1)
            for col in range(scan_start, scan_end + 1):
                candidate = (col, house_row)
                if candidate in starts:
                    continue
                if self.maze.is_wall(col, house_row):
                    continue
                starts.append(candidate)
                if len(starts) >= total_required:
                    break

        if len(starts) < total_required and self.maze.ghost_door:
            if self.maze.ghost_door not in starts:
                starts.append(self.maze.ghost_door)

        seed_positions = starts[:] if starts else original_starts
        if not seed_positions:
            seed_positions = [(MAZE_COLS // 2, MAZE_ROWS // 2)]

        while len(starts) < total_required:
            seed_index = len(starts) % len(seed_positions)
            starts.append(seed_positions[seed_index])

        starts = starts[:total_required]
        starts.sort(key=lambda pos: pos[0])

        base_speed = GHOST_SPEED_TILES[self.level_speed_index()]
        for index in range(total_required):
            tile = starts[index]
            ghost = Ghost(
                names[index],
                tile,
                base_speed,
                corners[index % len(corners)],
            )
            ghost.mode = "scatter"
            ghost.mode_timer = 0
            ghost.frightened_timer = 0
            ghost.flash = False
            ghost.capture_value = GHOST_BASE_SCORE
            ghost.queued_direction = initial_ghost_exit_direction(self.maze, tile)
            self.ghosts.append(ghost)

    def level_speed_index(self) -> int:
        """Return clamped index into the per-level speed tables."""

        return int(clamp(self.level - 1, 0, len(PLAYER_SPEED_TILES) - 1))

    def update_speeds(self) -> None:
        """Refresh player and ghost speeds according to current level."""

        idx = int(self.level_speed_index())
        player_speed_tiles = PLAYER_SPEED_TILES[idx]
        ghost_speed_tiles = GHOST_SPEED_TILES[idx]
        self.player.speed = player_speed_tiles
        for ghost in self.ghosts:
            ghost.speed = ghost_speed_tiles


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------


def poll_inputs(state: GameState) -> None:
    """Update the queued direction from current button presses."""

    # Exit shortcut for developer convenience.
    if BUTTON_EXIT in io.pressed:
        state.running = False
        return

    def _active(button):
        return button in io.pressed or button in getattr(io, "held", ())

    left = _active(BUTTON_LEFT)
    right = _active(BUTTON_RIGHT)
    up = _active(BUTTON_UP)
    down = _active(BUTTON_DOWN)

    if state.mode == "TEST_PATTERN":
        if BUTTON_START in io.pressed or BUTTON_ALT_START in io.pressed:
            state.test_pattern_timer = 0
            state.mode = "START"
            state.blink_timer = 0
        return

    if left and not right:
        state.input_queue = DIR_LEFT
    elif right and not left:
        state.input_queue = DIR_RIGHT
    elif up and not down:
        state.input_queue = DIR_UP
    elif down and not up:
        state.input_queue = DIR_DOWN

    # Start button logic also toggled through A or C.
    start_pressed = BUTTON_START in io.pressed or BUTTON_ALT_START in io.pressed
    up_down_pressed = BUTTON_UP in io.pressed or BUTTON_DOWN in io.pressed

    if state.mode in ("START", "GAME_OVER"):
        if start_pressed or up_down_pressed:
            begin_new_game(state)
    elif state.mode == "LEVEL_CLEAR":
        # Allow skipping the interstitial if desired.
        if start_pressed:
            state.level_timer = 0


# ---------------------------------------------------------------------------
# Level and game lifecycle helpers
# ---------------------------------------------------------------------------


def begin_new_game(state: GameState) -> None:
    """Reset score, lives, level, and prepare the first round."""

    state.score = 0
    state.lives = INITIAL_LIVES
    state.level = 1
    state.ghost_combo = 0
    state.maze.reset_pellets()
    state.mode = "READY"
    state.ready_timer = READY_PAUSE_MS
    state.frightened_ms = 0
    state.scatter_index = 0
    state.scatter_elapsed = 0
    state.pellets_eaten = 0
    state.fruit_spawn_queue = list(FRUIT_TRIGGER_COUNTS)
    state.fruit_active = False
    state.fruit_timer = 0
    state.fruit_type_index = 0
    state.fruit_flash = False
    state.fruit_flash_timer = 0
    state.fruit_history = []
    if state.maze.ghost_door:
        state.fruit_tile = state.maze.ghost_door
        if state.maze.is_wall(state.fruit_tile[0], state.fruit_tile[1]):
            state.fruit_tile = (MAZE_COLS // 2, MAZE_ROWS // 2)
    state.player = Player(state.maze.player_start, PLAYER_SPEED_TILES[0])
    state.initialise_ghosts()
    state.update_speeds()


def start_next_level(state: GameState) -> None:
    """Advance to the next level while keeping the current score and lives."""

    state.level += 1
    state.maze.reset_pellets()
    state.mode = "READY"
    state.ready_timer = READY_PAUSE_MS
    state.frightened_ms = 0
    state.scatter_index = 0
    state.scatter_elapsed = 0
    state.pellets_eaten = 0
    state.fruit_spawn_queue = list(FRUIT_TRIGGER_COUNTS)
    state.fruit_active = False
    state.fruit_timer = 0
    state.fruit_type_index = 0
    state.fruit_flash = False
    state.fruit_flash_timer = 0
    if state.maze.ghost_door:
        state.fruit_tile = state.maze.ghost_door
        if state.maze.is_wall(state.fruit_tile[0], state.fruit_tile[1]):
            state.fruit_tile = (MAZE_COLS // 2, MAZE_ROWS // 2)
    state.player = Player(state.maze.player_start, PLAYER_SPEED_TILES[int(state.level_speed_index())])
    state.initialise_ghosts()
    state.update_speeds()


def handle_life_loss(state: GameState) -> None:
    """Deduct a life and either reset for the next attempt or end the game."""

    state.lives -= 1
    state.ghost_combo = 0

    if state.lives <= 0:
        if state.score > state.session_high:
            state.session_high = state.score
        state.mode = "GAME_OVER"
        state.game_over_blink = 0
        return

    state.mode = "READY"
    state.ready_timer = READY_PAUSE_MS
    state.fruit_active = False
    state.fruit_timer = 0
    state.fruit_flash = False
    state.fruit_flash_timer = 0
    state.player = Player(state.maze.player_start, PLAYER_SPEED_TILES[int(state.level_speed_index())])
    state.initialise_ghosts()
    state.update_speeds()


# ---------------------------------------------------------------------------
# Movement and collision helpers
# ---------------------------------------------------------------------------


def resolve_next_tile(tile, direction):
    """Return the next tile when moving from ``tile`` in ``direction``.

    When the movement attempts to leave the maze bounds, only the registered
    portal links allow the move; all other edge exits are blocked.
    """

    if direction == DIR_NONE:
        return None

    entry = (tile[0], tile[1], direction[0], direction[1])
    if entry in PORTAL_LINKS:
        return PORTAL_LINKS[entry]

    col = tile[0] + direction[0]
    row = tile[1] + direction[1]
    if col < 0 or col >= MAZE_COLS or row < 0 or row >= MAZE_ROWS:
        return None
    return (col, row)


def try_commit_direction(mover: Mover, maze: Maze, direction) -> bool:
    """Attempt to set ``mover.direction`` to ``direction`` if the path is open."""

    if direction == DIR_NONE:
        return False

    next_tile = resolve_next_tile(mover.tile, direction)
    if next_tile is None:
        return False

    if maze.is_wall(next_tile[0], next_tile[1]):
        return False

    mover.direction = direction
    mover.next_tile = next_tile
    mover.progress = 0.0
    return True


def update_mover(mover: Mover, maze: Maze, dt: float) -> None:
    """Advance ``mover`` based on its current direction and queued requests."""

    if mover.direction == DIR_NONE:
        # Try to start moving if a queued direction exists.
        if mover.queued_direction != DIR_NONE:
            if try_commit_direction(mover, maze, mover.queued_direction):
                mover.queued_direction = DIR_NONE
        return

    mover.progress += mover.speed * dt
    while mover.progress >= 1.0:
        mover.tile = mover.next_tile
        mover.progress -= 1.0
        if mover.progress < 1e-3:
            mover.progress = 0.0

        # Evaluate direction change priority: queued request first, otherwise continue.
        if mover.queued_direction != DIR_NONE:
            if try_commit_direction(mover, maze, mover.queued_direction):
                mover.queued_direction = DIR_NONE
                continue

        if mover.direction == DIR_NONE:
            mover.next_tile = mover.tile
            mover.progress = 0.0
            return

        next_tile = resolve_next_tile(mover.tile, mover.direction)
        if next_tile is None or maze.is_wall(next_tile[0], next_tile[1]):
            mover.direction = DIR_NONE
            mover.next_tile = mover.tile
            mover.progress = 0.0
            return

        mover.next_tile = next_tile


def fruit_type_for_level(level: int) -> int:
    """Return the fruit index for the supplied ``level``."""

    if level <= 0:
        return 0
    return min(level - 1, len(FRUIT_TYPES) - 1)


def maybe_spawn_fruit(state: GameState) -> None:
    """Spawn a bonus fruit once the pellet thresholds are met."""

    if state.fruit_active:
        return
    if not state.fruit_spawn_queue:
        return
    if state.pellets_eaten < state.fruit_spawn_queue[0]:
        return

    state.fruit_spawn_queue.pop(0)
    state.fruit_active = True
    state.fruit_timer = FRUIT_DURATION_MS
    state.fruit_flash = False
    state.fruit_flash_timer = 0
    state.fruit_type_index = fruit_type_for_level(state.level)

    col, row = state.fruit_tile
    if col < 0 or col >= MAZE_COLS or row < 0 or row >= MAZE_ROWS or state.maze.is_wall(col, row):
        state.fruit_tile = (MAZE_COLS // 2, MAZE_ROWS // 2)
        col, row = state.fruit_tile

    if 0 <= col < MAZE_COLS and 0 <= row < MAZE_ROWS:
        idx = tile_index(col, row)
        existing = state.maze.pellets[idx]
        if existing in (PELLET_SMALL, PELLET_POWER) and state.maze.total_pellets > 0:
            state.maze.total_pellets -= 1
        state.maze.pellets[idx] = PELLET_NONE


def update_bonus_fruit(state: GameState, dt: float) -> None:
    """Advance timers for an active fruit and handle expiry blink."""

    if not state.fruit_active:
        state.fruit_flash = False
        state.fruit_flash_timer = 0
        return

    dt_ms = int(dt * 1000)
    state.fruit_timer = max(0, state.fruit_timer - dt_ms)

    if state.fruit_timer <= 0:
        state.fruit_active = False
        state.fruit_flash = False
        state.fruit_flash_timer = 0
        return

    if state.fruit_timer <= FRUIT_FLASH_START_MS:
        state.fruit_flash_timer += dt_ms
        if state.fruit_flash_timer >= FRUIT_FLASH_INTERVAL_MS:
            state.fruit_flash_timer %= FRUIT_FLASH_INTERVAL_MS
            state.fruit_flash = not state.fruit_flash
    else:
        state.fruit_flash = False
        state.fruit_flash_timer = 0


def collect_active_fruit(state: GameState) -> None:
    """Award fruit points and archive the fruit in the HUD history."""

    if not state.fruit_active:
        return

    _, fruit_score, _ = FRUIT_TYPES[state.fruit_type_index]
    state.score += fruit_score
    state.fruit_active = False
    state.fruit_timer = 0
    state.fruit_flash = False
    state.fruit_flash_timer = 0
    state.fruit_history.append(state.fruit_type_index)
    if len(state.fruit_history) > MAX_FRUIT_HISTORY:
        state.fruit_history = state.fruit_history[-MAX_FRUIT_HISTORY:]


def player_tile_consumption(state: GameState) -> None:
    """Handle pellet consumption and frightened state triggers."""

    col, row = state.player.tile
    pellet = state.maze.consume_pellet(col, row)
    if pellet == PELLET_NONE:
        if state.fruit_active and state.player.tile == state.fruit_tile:
            collect_active_fruit(state)
        return

    if pellet == PELLET_SMALL:
        state.score += PELLET_SCORE
        state.pellets_eaten += 1
    elif pellet == PELLET_POWER:
        state.score += POWER_PELLET_SCORE
        state.pellets_eaten += 1
        state.frightened_ms = FRIGHTENED_DURATION_MS
        state.ghost_combo = 0
        for ghost in state.ghosts:
            ghost.frightened_timer = FRIGHTENED_DURATION_MS
            ghost.mode = "frightened"
            ghost.flash = False
            # Reverse direction immediately for a more authentic feel.
            if ghost.direction != DIR_NONE:
                ghost.direction = (-ghost.direction[0], -ghost.direction[1])
                ghost.tile, ghost.next_tile = ghost.next_tile, ghost.tile
                ghost.progress = 1.0 - ghost.progress

    maybe_spawn_fruit(state)

    if state.fruit_active and state.player.tile == state.fruit_tile:
        collect_active_fruit(state)

    if state.maze.total_pellets == 0:
        state.mode = "LEVEL_CLEAR"
        state.level_timer = LEVEL_CLEAR_MS


# ---------------------------------------------------------------------------
# Ghost AI logic
# ---------------------------------------------------------------------------


def scatter_chase_duration(index: int):
    """Return the scatter/chase window pair for the given cycle index."""

    if index >= len(SCATTER_CHASE_SCRIPT):
        return SCATTER_CHASE_SCRIPT[-1]
    return SCATTER_CHASE_SCRIPT[index]


def update_ghost_modes(state: GameState, dt_ms: int) -> None:
    """Update scatter/chase timers when ghosts are not frightened."""

    if state.frightened_ms > 0:
        return

    state.scatter_elapsed += dt_ms
    scatter_duration, chase_duration = scatter_chase_duration(state.scatter_index)

    if state.ghosts and state.ghosts[0].mode == "frightened":
        return

    if state.ghosts and state.ghosts[0].mode == "scatter":
        if scatter_duration > 0 and state.scatter_elapsed >= scatter_duration:
            for ghost in state.ghosts:
                if ghost.mode != "frightened":
                    ghost.mode = "chase"
            state.scatter_elapsed = 0
    else:
        target = chase_duration if chase_duration > 0 else None
        if target is not None and state.scatter_elapsed >= target:
            state.scatter_index = min(state.scatter_index + 1, len(SCATTER_CHASE_SCRIPT) - 1)
            state.scatter_elapsed = 0
            for ghost in state.ghosts:
                if ghost.mode != "frightened":
                    ghost.mode = "scatter"


def ghost_target_tile(ghost: Ghost, state: GameState):
    """Compute the target tile for a ghost based on its current mode."""

    if ghost.mode == "scatter":
        return ghost.home_corner

    if ghost.mode == "frightened":
        # Frightened ghosts pick random valid tiles; actual selection occurs elsewhere.
        return ghost.tile

    # Chase mode targets depend on ghost identity.
    player_tile = state.player.tile
    player_dir = state.player.direction if state.player.direction != DIR_NONE else state.player.facing
    if player_dir == DIR_NONE:
        player_dir = DIR_RIGHT

    if ghost.name == "BLINKY":
        return player_tile

    if ghost.name == "PINKY":
        ahead_col = player_tile[0] + player_dir[0] * 4
        ahead_row = player_tile[1] + player_dir[1] * 4
        return wrap_tile(ahead_col, ahead_row)

    if ghost.name == "INKY":
        ahead_col = player_tile[0] + player_dir[0] * 2
        ahead_row = player_tile[1] + player_dir[1] * 2
        ahead_tile = wrap_tile(ahead_col, ahead_row)
        blinky_tile = None
        for other in state.ghosts:
            if other.name == "BLINKY":
                blinky_tile = other.tile
                break
        if blinky_tile is None:
            return ahead_tile
        vector_col = ahead_tile[0] - blinky_tile[0]
        vector_row = ahead_tile[1] - blinky_tile[1]
        return wrap_tile(ahead_tile[0] + vector_col, ahead_tile[1] + vector_row)

    if ghost.name == "CLYDE":
        if distance_sq(ghost.tile, player_tile) >= 64:
            return player_tile
        return ghost.home_corner

    return player_tile


def choose_ghost_direction(ghost: Ghost, maze: Maze, state: GameState):
    """Select the next direction for ``ghost`` based on its mode and surroundings."""

    if maze.ghost_door and ghost.mode != "frightened":
        col, row = ghost.tile
        door_col, door_row = maze.ghost_door
        if maze.in_ghost_house(col, row) and row >= door_row:
            if col < door_col:
                return DIR_RIGHT
            if col > door_col:
                return DIR_LEFT
            if row > door_row:
                return DIR_UP
        elif col == door_col and row == door_row:
            # Once outside the home force a horizontal move so ghosts do not bounce back.
            if ghost.home_corner[0] < door_col and not maze.is_wall(col - 1, row):
                return DIR_LEFT
            if ghost.home_corner[0] > door_col and not maze.is_wall(col + 1, row):
                return DIR_RIGHT
            # Fallback: try left then right.
            if not maze.is_wall(col - 1, row):
                return DIR_LEFT
            if not maze.is_wall(col + 1, row):
                return DIR_RIGHT

    possible = []
    for direction in DIRECTION_ORDER:
        next_tile = resolve_next_tile(ghost.tile, direction)
        if next_tile is None:
            continue
        if maze.is_wall(next_tile[0], next_tile[1]):
            continue
        if direction_opposite(direction, ghost.direction) and ghost.mode != "frightened":
            continue
        possible.append((direction, next_tile))

    if not possible:
        return (-ghost.direction[0], -ghost.direction[1]) if ghost.direction != DIR_NONE else DIR_UP

    if ghost.mode == "frightened":
        # Randomly choose a valid direction.
        pick = urandom.getrandbits(2) % len(possible)
        return possible[pick][0]

    target = ghost_target_tile(ghost, state)
    best_direction, best_tile = possible[0]
    best_score = distance_sq(best_tile, target)
    for direction, candidate_tile in possible[1:]:
        score = distance_sq(candidate_tile, target)
        if score < best_score:
            best_score = score
            best_direction = direction
    return best_direction


def update_ghost(ghost: Ghost, state: GameState, dt: float) -> None:
    """Advance a single ghost including mode timers and movement."""

    base_speed = GHOST_SPEED_TILES[int(state.level_speed_index())]

    if ghost.mode == "frightened":
        ghost.frightened_timer -= int(dt * 1000)
        if ghost.frightened_timer <= 0:
            ghost.mode = "scatter"
            ghost.flash = False
            ghost.frightened_timer = 0
            ghost.speed = base_speed
        elif ghost.frightened_timer <= FRIGHTENED_FLASH_START_MS:
            ghost.flash = not ghost.flash
        ghost.speed = base_speed * FRIGHTENED_SPEED_FACTOR
    else:
        ghost.speed = base_speed

    if ghost.direction == DIR_NONE or ghost.progress <= 0.1:
        desired = choose_ghost_direction(ghost, state.maze, state)
        if desired != ghost.direction:
            if ghost.progress <= 0.1 and try_commit_direction(ghost, state.maze, desired):
                ghost.queued_direction = DIR_NONE
            else:
                ghost.queued_direction = desired

    update_mover(ghost, state.maze, dt)


def update_ghosts(state: GameState, dt: float) -> None:
    """Update all ghosts for the current frame."""

    dt_ms = int(dt * 1000)
    update_ghost_modes(state, dt_ms)
    for ghost in state.ghosts:
        update_ghost(ghost, state, dt)


def detect_collisions(state: GameState) -> None:
    """Handle collisions between the player and ghosts."""

    player_pos = state.player.world_position()
    for ghost in state.ghosts:
        ghost_pos = ghost.world_position()
        dx = abs(player_pos[0] - ghost_pos[0])
        dy = abs(player_pos[1] - ghost_pos[1])
        if dx <= TILE_WIDTH * 0.5 and dy <= TILE_HEIGHT * 0.5:
            if ghost.mode == "frightened":
                state.ghost_combo += 1
                score_award = GHOST_BASE_SCORE * (2 ** (state.ghost_combo - 1))
                state.score += score_award
                ghost.mode = "scatter"
                ghost.tile = ghost.home_corner
                ghost.next_tile = ghost.home_corner
                ghost.direction = DIR_NONE
                ghost.progress = 0.0
                ghost.frightened_timer = 0
                ghost.capture_value = GHOST_BASE_SCORE
            else:
                handle_life_loss(state)
                return


# ---------------------------------------------------------------------------
# Player update logic
# ---------------------------------------------------------------------------


def update_player(state: GameState, dt: float) -> None:
    """Apply input, move the player, and handle pellet consumption."""

    if state.input_queue != DIR_NONE:
        state.player.queued_direction = state.input_queue
        state.input_queue = DIR_NONE

    prev_tile = (state.player.tile[0], state.player.tile[1])
    prev_progress = state.player.progress
    update_mover(state.player, state.maze, dt)

    if state.player.direction != DIR_NONE:
        state.player.facing = state.player.direction
    elif state.player.queued_direction != DIR_NONE:
        state.player.facing = state.player.queued_direction

    tile_changed = state.player.tile != prev_tile
    if tile_changed or state.player.progress <= 0.001 or prev_progress == 0.0:
        player_tile_consumption(state)

    state.player.mouth_timer += dt


# ---------------------------------------------------------------------------
# State machine update entry point
# ---------------------------------------------------------------------------


def update_state(state: GameState, dt: float) -> None:
    """Advance game logic for the current frame based on ``state.mode``."""

    if not state.running:
        return

    if state.mode == "TEST_PATTERN":
        state.test_pattern_timer = max(0, state.test_pattern_timer - int(dt * 1000))
        if state.test_pattern_timer <= 0:
            state.mode = "START"
            state.blink_timer = 0
        return

    if state.mode == "START":
        state.blink_timer += int(dt * 1000)
        if state.blink_timer >= START_PROMPT_FLASH_MS:
            state.blink_timer = 0
        return

    if state.mode == "READY":
        state.ready_timer -= int(dt * 1000)
        if state.ready_timer <= 0:
            state.mode = "PLAY"
        return

    if state.mode == "LEVEL_CLEAR":
        state.level_timer -= int(dt * 1000)
        if state.level_timer <= 0:
            start_next_level(state)
        return

    if state.mode == "GAME_OVER":
        state.game_over_blink += int(dt * 1000)
        if state.game_over_blink >= GAME_OVER_FLASH_MS:
            state.game_over_blink = 0
        return

    if state.mode != "PLAY":
        return

    update_player(state, dt)
    update_ghosts(state, dt)
    detect_collisions(state)
    update_bonus_fruit(state, dt)

    if state.frightened_ms > 0:
        state.frightened_ms = max(0, state.frightened_ms - int(dt * 1000))


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def draw_fruit_glyph(cx: int, cy: int, radius: int, fruit_index: int) -> None:
    """Draw a filled fruit sprite centred on ``(cx, cy)``."""

    fruit_index = int(clamp(fruit_index, 0, len(FRUIT_TYPES) - 1))
    _, _, body_pen = FRUIT_TYPES[fruit_index]

    stem_height = max(1, radius // 2)
    background_width = radius * 2 + 3
    background_height = radius * 2 + stem_height + 2
    draw_rect(
        cx - background_width // 2,
        cy - radius - stem_height - 1,
        background_width,
        background_height,
        PEN_BACKGROUND,
    )

    draw_circle(cx, cy, radius, body_pen)
    draw_rect(cx - 1, cy - radius - stem_height, 2, stem_height, PEN_FRUIT_STEM)
    draw_rect(cx + max(1, radius // 2), cy - radius // 2, 1, 1, PEN_TEXT)


def draw_maze(state: GameState) -> None:
    """Render maze walls and pellets."""

    screen.brush = PEN_BACKGROUND
    screen.clear()

    pellets = state.maze.pellets
    tiles = state.maze.tiles

    pellet_small_size = 1
    pellet_power_radius = max(2, min(TILE_WIDTH, TILE_HEIGHT) // 2)

    def is_wall_at(col: int, row: int) -> bool:
        if col < 0 or col >= MAZE_COLS or row < 0 or row >= MAZE_ROWS:
            return False
        return tiles[tile_index(col, row)] == TILE_WALL

    wall_core_w = max(2, TILE_WIDTH - 4)
    wall_core_h = max(2, TILE_HEIGHT - 4)
    wall_offset_x = (TILE_WIDTH - wall_core_w) // 2
    wall_offset_y = (TILE_HEIGHT - wall_core_h) // 2

    def draw_endcap(tile_left: int, tile_top: int, orientation: str, core_x: int, core_y: int) -> None:
        tile_right = tile_left + TILE_WIDTH
        tile_bottom = tile_top + TILE_HEIGHT

        if orientation in ("left", "right"):
            radius_y = max(1, wall_core_h // 2)
            radius_x = max(radius_y, min(TILE_WIDTH, radius_y + wall_offset_x + 3))
            centre_y = tile_top + TILE_HEIGHT // 2
            centre_x = core_x if orientation == "left" else core_x + wall_core_w - 1

            for dy in range(-radius_y, radius_y + 1):
                normalized = abs(dy) / radius_y if radius_y else 0.0
                if normalized > 1.0:
                    continue
                span = int(radius_x * math.sqrt(max(0.0, 1.0 - normalized * normalized)))
                y = centre_y + dy
                if y < tile_top or y >= tile_bottom:
                    continue

                if orientation == "left":
                    start = max(tile_left, centre_x - span)
                    end = min(tile_right, centre_x + 1)
                else:
                    start = max(tile_left, centre_x)
                    end = min(tile_right, centre_x + span + 1)

                if end > start:
                    draw_rect(start, y, end - start, 1, PEN_WALL)
        elif orientation in ("up", "down"):
            radius_x = max(1, wall_core_w // 2)
            radius_y = max(radius_x, min(TILE_HEIGHT, radius_x + wall_offset_y + 3))
            centre_x = tile_left + TILE_WIDTH // 2
            centre_y = core_y if orientation == "up" else core_y + wall_core_h - 1

            for dx in range(-radius_x, radius_x + 1):
                normalized = abs(dx) / radius_x if radius_x else 0.0
                if normalized > 1.0:
                    continue
                span = int(radius_y * math.sqrt(max(0.0, 1.0 - normalized * normalized)))
                x = centre_x + dx
                if x < tile_left or x >= tile_right:
                    continue

                if orientation == "up":
                    start = max(tile_top, centre_y - span)
                    end = min(tile_bottom, centre_y + 1)
                else:
                    start = max(tile_top, centre_y)
                    end = min(tile_bottom, centre_y + span + 1)

                if end > start:
                    draw_rect(x, start, 1, end - start, PEN_WALL)

    for row in range(MAZE_ROWS):
        for col in range(MAZE_COLS):
            idx = tile_index(col, row)
            tile_left = MAZE_ORIGIN_X + col * TILE_WIDTH
            tile_top = MAZE_ORIGIN_Y + row * TILE_HEIGHT

            if tiles[idx] == TILE_WALL:
                core_x = tile_left + wall_offset_x
                core_y = tile_top + wall_offset_y
                draw_rect(core_x, core_y, wall_core_w, wall_core_h, PEN_WALL)

                up = is_wall_at(col, row - 1)
                down = is_wall_at(col, row + 1)
                left = is_wall_at(col - 1, row)
                right = is_wall_at(col + 1, row)

                if up:
                    draw_rect(core_x, tile_top, wall_core_w, wall_offset_y + 1, PEN_WALL)
                if down:
                    draw_rect(core_x, core_y + wall_core_h - 1, wall_core_w, wall_offset_y + 1, PEN_WALL)
                if left:
                    draw_rect(tile_left, core_y, wall_offset_x + 1, wall_core_h, PEN_WALL)
                if right:
                    draw_rect(core_x + wall_core_w - 1, core_y, wall_offset_x + 1, wall_core_h, PEN_WALL)

                connections = up + down + left + right
                if connections == 1:
                    if left:
                        draw_endcap(tile_left, tile_top, "right", core_x, core_y)
                    elif right:
                        draw_endcap(tile_left, tile_top, "left", core_x, core_y)
                    elif up:
                        draw_endcap(tile_left, tile_top, "down", core_x, core_y)
                    elif down:
                        draw_endcap(tile_left, tile_top, "up", core_x, core_y)
                continue

            pellet = pellets[idx]
            centre_x = tile_left + TILE_WIDTH // 2
            centre_y = tile_top + TILE_HEIGHT // 2

            if pellet == PELLET_SMALL:
                draw_rect(centre_x, centre_y, pellet_small_size, pellet_small_size, PEN_PELLET)
            elif pellet == PELLET_POWER:
                draw_circle(centre_x, centre_y, pellet_power_radius, PEN_POWER)

            if state.fruit_active and not state.fruit_flash and state.fruit_tile == (col, row):
                fruit_radius = max(3, min(TILE_WIDTH, TILE_HEIGHT) // 3)
                draw_fruit_glyph(centre_x, centre_y, fruit_radius, state.fruit_type_index)


def draw_player(state: GameState) -> None:
    """Render Pac-Man with simple mouth animation."""

    x, y = state.player.world_position()
    centre_x = int(x)
    centre_y = int(y)
    radius = PLAYER_RENDER_RADIUS

    # Alternate mouth openness to mimic chomping.
    phase = int((state.player.mouth_timer * 8) % 4)
    mouth_fraction = 0.65 if phase < 2 else 0.25
    mouth_span = max(2, int(radius * mouth_fraction))

    facing = state.player.facing if state.player.facing != DIR_NONE else DIR_RIGHT
    facing_angle = 0.0
    if facing == DIR_LEFT:
        facing_angle = math.pi
    elif facing == DIR_UP:
        facing_angle = math.pi / 2
    elif facing == DIR_DOWN:
        facing_angle = -math.pi / 2

    mouth_angle = math.atan2(mouth_span, radius)
    body_pen = PEN_PLAYER if phase < 2 else PEN_PLAYER_ALT

    def angle_diff(a: float, b: float) -> float:
        delta = a - b
        while delta <= -math.pi:
            delta += 2 * math.pi
        while delta > math.pi:
            delta -= 2 * math.pi
        return delta

    for dy in range(-radius, radius + 1):
        span = int(math.sqrt(max(0, radius * radius - dy * dy)))
        row_y = centre_y + dy
        for dx in range(-span, span + 1):
            angle = math.atan2(-dy, dx)
            if abs(angle_diff(angle, facing_angle)) <= mouth_angle:
                continue
            draw_rect(centre_x + dx, row_y, 1, 1, body_pen)

    # No eye rendering keeps the wedge strongly visible on the badge display.


def draw_ghost(state: GameState, ghost: Ghost, index: int) -> None:
    """Render a single ghost sprite."""

    x, y = ghost.world_position()
    centre_x = int(x)
    centre_y = int(y)
    radius = GHOST_RENDER_RADIUS
    width = radius * 2
    left = centre_x - radius
    top = centre_y - radius
    head_centre_y = top + radius
    bottom = top + width

    if ghost.mode == "frightened":
        body_pen = PEN_GHOST_FLASH if ghost.flash else PEN_GHOST_FRIGHT
    else:
        body_pen = PEN_GHOST_COLOURS[index % len(PEN_GHOST_COLOURS)]

    draw_circle(centre_x, head_centre_y, radius, body_pen)
    draw_rect(left, head_centre_y, width, radius, body_pen)

    scallop_radius = max(2, radius // 3)
    scallop_count = 4
    spacing = width / scallop_count
    for i in range(scallop_count):
        scallop_cx = int(left + (i + 0.5) * spacing)
        draw_circle(scallop_cx, bottom, scallop_radius, PEN_BACKGROUND)

    if ghost.mode == "frightened":
        return

    eye_width = max(4, radius - 2)
    eye_height = max(5, radius)
    eye_top = top + radius // 3
    left_eye_x = centre_x - radius // 2 - eye_width // 2
    right_eye_x = centre_x + radius // 2 - eye_width // 2
    draw_rect(left_eye_x, eye_top, eye_width, eye_height, PEN_GHOST_EYE_WHITE)
    draw_rect(right_eye_x, eye_top, eye_width, eye_height, PEN_GHOST_EYE_WHITE)

    pupil_size = max(2, eye_width // 2)
    dir_x, dir_y = ghost.direction
    if dir_x == 0 and dir_y == 0 and ghost.queued_direction != DIR_NONE:
        dir_x, dir_y = ghost.queued_direction
    dir_x = int(clamp(dir_x, -1, 1))
    dir_y = int(clamp(dir_y, -1, 1))
    max_offset_x = max(0, (eye_width - pupil_size - 2) // 2)
    max_offset_y = max(0, (eye_height - pupil_size - 2) // 2)
    offset_x = dir_x * max_offset_x
    offset_y = dir_y * max_offset_y

    draw_rect(left_eye_x + 1 + offset_x, eye_top + 1 + offset_y, pupil_size, pupil_size, PEN_GHOST_EYE_PUPIL)
    draw_rect(right_eye_x + 1 + offset_x, eye_top + 1 + offset_y, pupil_size, pupil_size, PEN_GHOST_EYE_PUPIL)


def draw_life_icon(left: int, top: int, size: int, pen) -> None:
    centre_x = left + size // 2
    centre_y = top + size // 2
    radius = max(3, size // 2 - 1)

    draw_rect(left, top, size, size, PEN_BACKGROUND)

    mouth_angle = math.pi / 4
    for dy in range(-radius, radius + 1):
        span = int(math.sqrt(max(0, radius * radius - dy * dy)))
        row_y = centre_y + dy
        for dx in range(-span, span + 1):
            angle = math.atan2(-dy, dx)
            if abs(angle) <= mouth_angle:
                continue
            draw_rect(centre_x + dx, row_y, 1, 1, pen)


def draw_hud(state: GameState, show_stats: bool = True) -> None:
    """Render score, lives, level, and session high."""

    if show_stats:
        draw_text(f"Score: {state.score}", HUD_MARGIN, HUD_MARGIN, PEN_TEXT)

        level_text = f"Level: {state.level}"
        level_width, _ = measure_text(level_text)
        draw_text(level_text, WIDTH // 2 - int(level_width) // 2, HUD_MARGIN, PEN_TEXT)

        best_text = f"High: {state.session_high}"
        best_width, _ = measure_text(best_text)
        draw_text(best_text, WIDTH - int(best_width) - HUD_MARGIN, HUD_MARGIN, PEN_TEXT)

    life_size = PLAYER_DRAW_SIZE
    life_gap = 2
    max_lives = INITIAL_LIVES
    total_height = max_lives * life_size + (max_lives - 1) * life_gap
    life_start_y = max(HUD_MARGIN, (HEIGHT - total_height) // 2)
    life_x = max(0, HUD_MARGIN // 2)

    for slot in range(max_lives):
        pen = PEN_LIVES if slot < state.lives else PEN_LIFE_EMPTY
        top = life_start_y + slot * (life_size + life_gap)
        draw_life_icon(life_x, top, life_size, pen)

    if show_stats:
        history = state.fruit_history[-MAX_FRUIT_HISTORY:]
        if history:
            centre_y = HUD_MARGIN + HUD_LINE_HEIGHT * 2 + 2
            spacing = 12
            cx = WIDTH - HUD_MARGIN - spacing // 2
            for fruit_index in reversed(history):
                draw_fruit_glyph(cx, centre_y, 4, fruit_index)
                cx -= spacing
                if cx <= HUD_MARGIN:
                    break
    else:
        score_text = str(state.score)
        score_width, score_height = measure_text(score_text)
        score_width = math.ceil(score_width)
        score_height = math.ceil(score_height)
        x = WIDTH - score_width - HUD_MARGIN + 20
        max_x = WIDTH - score_width
        x = min(max_x, x)
        y = max(0, HUD_MARGIN - 20)
        bg_left = max(0, x - 2)
        bg_top = max(0, y - 1)
        bg_width = min(WIDTH - bg_left, score_width + 4)
        bg_height = min(HEIGHT - bg_top, score_height + 2)
        draw_rect(bg_left, bg_top, bg_width, bg_height, PEN_BACKGROUND)
        draw_text(score_text, x, y, PEN_TEXT)


def draw_overlay(text: str, subtext: str | None = None, y_offset: int = 0) -> None:
    """Render a centered overlay with optional secondary text."""

    title_scale = 1.2
    line_width, line_height = measure_text(text, TITLE_FONT, title_scale)
    x = WIDTH // 2 - int(line_width) // 2
    y = HEIGHT // 2 - HUD_LINE_HEIGHT * 4 + y_offset
    draw_text(text, x, y, PEN_PLAYER, TITLE_FONT, title_scale)

    if subtext:
        sub_scale = 1.0
        sub_width, _ = measure_text(subtext, HUD_FONT, sub_scale)
        draw_text(
            subtext,
            WIDTH // 2 - int(sub_width) // 2,
            y + int(line_height) + HUD_LINE_HEIGHT,
            PEN_TEXT,
            HUD_FONT,
            sub_scale,
        )


def render_test_pattern(state: GameState) -> None:
    """Render a diagnostic pattern to verify full-screen bounds."""

    screen.brush = PEN_BACKGROUND
    screen.clear()

    border_color = PEN_TEXT
    draw_rect(0, 0, WIDTH, 1, border_color)
    draw_rect(0, HEIGHT - 1, WIDTH, 1, border_color)
    draw_rect(0, 0, 1, HEIGHT, border_color)
    draw_rect(WIDTH - 1, 0, 1, HEIGHT, border_color)

    step = 20
    for x in range(0, WIDTH, step):
        color = PEN_PELLET if (x // step) % 2 == 0 else PEN_POWER
        draw_rect(x, 0, 1, min(12, HEIGHT), color)
        draw_rect(x, HEIGHT - min(12, HEIGHT), 1, min(12, HEIGHT), color)
    for y in range(0, HEIGHT, step):
        color = PEN_GHOST_COLOURS[(y // step) % len(PEN_GHOST_COLOURS)]
        draw_rect(0, y, min(12, WIDTH), 1, color)
        draw_rect(WIDTH - min(12, WIDTH), y, min(12, WIDTH), 1, color)

    draw_text(f"Width: {WIDTH}", 6, HEIGHT - HUD_LINE_HEIGHT * 2 - 4, PEN_TEXT)
    draw_text(f"Height: {HEIGHT}", 6, HEIGHT - HUD_LINE_HEIGHT - 2, PEN_TEXT)
    draw_text("Press A/C to continue", 6, 6, PEN_TEXT)


def render_start_screen(state: GameState) -> None:
    """Render the start screen with blinking prompt."""

    draw_maze(state)
    draw_hud(state)
    title = "Tufty Pac-Man"
    title_scale = 1.3
    title_width, _ = measure_text(title, TITLE_FONT, title_scale)
    draw_text(title, WIDTH // 2 - int(title_width) // 2 + 15, 50, PEN_PLAYER, TITLE_FONT, title_scale)

    prompt = "Press A or C to start"
    if state.blink_timer < START_PROMPT_FLASH_MS / 2:
        draw_text(prompt, HUD_MARGIN + 60, 135, PEN_TEXT)


def render_ready(state: GameState) -> None:
    """Render the maze plus a READY overlay."""

    draw_maze(state)
    draw_player(state)
    for index, ghost in enumerate(state.ghosts):
        draw_ghost(state, ghost, index)
    draw_hud(state)
    draw_overlay("READY!", "Get set...", y_offset=25)


def render_play(state: GameState) -> None:
    """Render active gameplay."""

    draw_maze(state)
    draw_player(state)
    for index, ghost in enumerate(state.ghosts):
        draw_ghost(state, ghost, index)
    draw_hud(state, show_stats=False)


def render_level_clear(state: GameState) -> None:
    """Render level clear overlay."""

    draw_maze(state)
    draw_hud(state)
    draw_overlay("LEVEL CLEAR", "Preparing next maze...")


def render_game_over(state: GameState) -> None:
    """Render game over screen with restart prompt."""

    draw_maze(state)
    draw_hud(state)
    message = "GAME OVER"
    prompt = "Press A or C to play again"
    if state.game_over_blink < GAME_OVER_FLASH_MS / 2:
        draw_overlay(message, prompt)
    else:
        draw_overlay(message)


def render_frame(state: GameState) -> None:
    """Composite main render dispatcher based on mode."""

    if state.mode == "TEST_PATTERN":
        render_test_pattern(state)
    elif state.mode == "START":
        render_start_screen(state)
    elif state.mode == "READY":
        render_ready(state)
    elif state.mode == "PLAY":
        render_play(state)
    elif state.mode == "LEVEL_CLEAR":
        render_level_clear(state)
    else:
        render_game_over(state)


# ---------------------------------------------------------------------------
# Main loop and bootstrap
# ---------------------------------------------------------------------------


APP_RUNTIME = {"state": None}


def _compute_dt_seconds() -> float:
    dt_ms = getattr(io, "ticks_delta", 0)
    try:
        dt = dt_ms / 1000.0
    except TypeError:
        dt = float(dt_ms) / 1000.0 if dt_ms else 0.0
    if dt < 0:
        dt += 4294.967
    if dt > MAX_DT_SECONDS:
        dt = MAX_DT_SECONDS
    return dt


def init() -> None:
    """Initialise game state for the runtime."""

    maze = Maze()
    state = GameState(maze)
    state.initialise_ghosts()
    state.update_speeds()
    if TEST_PATTERN_ENABLED:
        state.mode = "TEST_PATTERN"
        state.test_pattern_timer = TEST_PATTERN_DURATION_MS
    APP_RUNTIME["state"] = state
    screen.font = HUD_FONT


def update():
    """Runtime update callback for badgeware.run."""

    state = APP_RUNTIME.get("state")
    if state is None:
        return False

    if not state.running:
        screen.brush = PEN_BACKGROUND
        screen.clear()
        return False

    poll_inputs(state)
    if not state.running:
        screen.brush = PEN_BACKGROUND
        screen.clear()
        return False

    dt = _compute_dt_seconds()
    update_state(state, dt)
    render_frame(state)

    if not state.running:
        screen.brush = PEN_BACKGROUND
        screen.clear()
        return False

    return None


if __name__ == "__main__":
    run(update, init=init)
