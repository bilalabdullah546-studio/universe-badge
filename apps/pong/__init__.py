"""Single-player Pong for the Tufty 2350 using the 2025 badgeware APIs."""

import urandom

from badgeware import screen, io, brushes, shapes, run, PixelFont


# Display configuration -------------------------------------------------------
SCREEN_WIDTH = screen.width
SCREEN_HEIGHT = screen.height

MAX_DT_MS = 50  # clamp delta to avoid wild physics when frames stall

PADDLE_WIDTH = 70
PADDLE_HEIGHT = 10
PADDLE_SPEED = 180.0  # pixels per second
PADDLE_Y = SCREEN_HEIGHT - 32
PADDLE_ACCEL_HOLD_MS = 150

BALL_RADIUS = 6
BALL_START_VX = 120.0
BALL_START_VY = -140.0
BALL_START_SPEED = (BALL_START_VX ** 2 + BALL_START_VY ** 2) ** 0.5

SPEED_INCREMENT = 12.0
SPEED_CAP = 260.0

HUD_MARGIN = 8
OVERLAY_TEXT_X_OFFSET = -20
OVERLAY_TEXT_LEFT_PADDING = 60

# Typography -----------------------------------------------------------------
HUD_FONT = PixelFont.load("/system/assets/fonts/ark.ppf")
TITLE_FONT = PixelFont.load("/system/assets/fonts/absolute.ppf")
PROMPT_FONT = PixelFont.load("/system/assets/fonts/ziplock.ppf")

screen.font = HUD_FONT
HUD_LINE_HEIGHT = screen.measure_text("Ay")[1] + 4
OVERLAY_LINE_SPACING = HUD_LINE_HEIGHT + 6

TITLE_TEXT = "Tufty Pong"
TITLE_PROMPT = "Press A/C to start"
TITLE_HINT = "B exits to menu"

# Colour palette -------------------------------------------------------------
BACKGROUND_COLOR = brushes.color(10, 10, 30)
PADDLE_COLOR = brushes.color(200, 220, 0)
BALL_COLOR = brushes.color(255, 240, 180)
HUD_TEXT_COLOR = brushes.color(240, 240, 240)
HUD_HIGHLIGHT_COLOR = brushes.color(255, 200, 80)
TITLE_COLOR = brushes.color(255, 250, 0)
OVERLAY_BG_COLOR = brushes.color(30, 30, 60)
OVERLAY_FRAME_COLOR = brushes.color(80, 80, 120)

# Input aliases --------------------------------------------------------------
BUTTON_LEFT = io.BUTTON_A
BUTTON_RIGHT = io.BUTTON_C
BUTTON_EXIT = io.BUTTON_B


# Game state -----------------------------------------------------------------
class GameState:
    TITLE = 0
    PLAY = 1
    MISS = 2
    GAME_OVER = 3


paddle = {
    "x": SCREEN_WIDTH / 2.0,
    "y": float(PADDLE_Y),
    "width": float(PADDLE_WIDTH),
    "height": float(PADDLE_HEIGHT),
    "speed": float(PADDLE_SPEED),
    "hold_start": None,
}

ball = {
    "x": SCREEN_WIDTH / 2.0,
    "y": SCREEN_HEIGHT / 2.0,
    "vx": float(BALL_START_VX),
    "vy": float(BALL_START_VY),
    "radius": float(BALL_RADIUS),
}

speed_ramp = {
    "increment": float(SPEED_INCREMENT),
    "cap": float(SPEED_CAP),
}

scoreboard = {
    "current": 0,
    "lives": 5,
    "session_best": 0,
}

round_result = {
    "miss_reason": "",
    "timestamp": io.ticks,
}

ball_speed_preserved = BALL_START_SPEED

input_state = {
    "last_direction": 0,
}

game_state = GameState.TITLE
tick_timer = io.ticks


# Helpers --------------------------------------------------------------------
def reset_tick_timer(now=None):
    global tick_timer
    tick_timer = now if now is not None else io.ticks


def clamp(value, lower, upper):
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def get_ball_speed():
    return (ball["vx"] ** 2 + ball["vy"] ** 2) ** 0.5


def set_ball_speed(target_speed):
    current_speed = get_ball_speed()
    if current_speed <= 0.0:
        return
    scale = target_speed / current_speed
    ball["vx"] *= scale
    ball["vy"] *= scale


def seed_random_velocity(direction_upwards=True, speed=None):
    horizontal_sign = -1 if urandom.getrandbits(1) else 1
    jitter = (urandom.getrandbits(8) / 255.0 - 0.5) * 60.0
    vx = (BALL_START_VX + jitter) * horizontal_sign
    vy = abs(BALL_START_VY)
    vy = -vy if direction_upwards else vy

    ball["vx"] = vx
    ball["vy"] = vy

    target_speed = speed if speed is not None else BALL_START_SPEED
    target_speed = clamp(target_speed, BALL_START_SPEED, speed_ramp["cap"])
    if target_speed > 0.0:
        set_ball_speed(target_speed)


def reset_paddle_state():
    paddle["x"] = SCREEN_WIDTH / 2.0
    paddle["y"] = float(PADDLE_Y)
    paddle["hold_start"] = None
    input_state["last_direction"] = 0


def reset_ball_state(direction_upwards=True, speed=None):
    ball["x"] = SCREEN_WIDTH / 2.0
    ball["y"] = SCREEN_HEIGHT / 2.0
    seed_random_velocity(direction_upwards=direction_upwards, speed=speed)


def reset_scoreboard(preserve_best=True):
    if not preserve_best:
        scoreboard["session_best"] = 0
    scoreboard["current"] = 0
    scoreboard["lives"] = 5


def stage_new_round(direction_upwards=True, speed_override=None):
    reset_paddle_state()
    reset_ball_state(direction_upwards=direction_upwards, speed=speed_override)
    reset_tick_timer()


def apply_speed_ramp():
    current_speed = get_ball_speed()
    if current_speed <= 0.0 or current_speed >= speed_ramp["cap"]:
        return
    target_speed = min(current_speed + speed_ramp["increment"], speed_ramp["cap"])
    scale = target_speed / current_speed
    ball["vx"] *= scale
    ball["vy"] *= scale


def mark_round_result(reason):
    round_result["miss_reason"] = reason
    round_result["timestamp"] = io.ticks


# Gameplay management -------------------------------------------------------
def compute_frame_dt(now):
    global tick_timer

    elapsed = now - tick_timer
    if elapsed < 0:
        elapsed = 0
    if elapsed > MAX_DT_MS:
        elapsed = MAX_DT_MS

    tick_timer = now
    return elapsed / 1000.0


def get_paddle_direction():
    left = BUTTON_LEFT in io.held or BUTTON_LEFT in io.pressed
    right = BUTTON_RIGHT in io.held or BUTTON_RIGHT in io.pressed

    if left and not right:
        return -1
    if right and not left:
        return 1
    return 0


def start_new_game():
    global game_state, ball_speed_preserved

    reset_scoreboard(preserve_best=True)
    round_result["miss_reason"] = ""
    ball_speed_preserved = BALL_START_SPEED
    stage_new_round(direction_upwards=True)
    game_state = GameState.PLAY


def update_title_state(_dt):
    if BUTTON_EXIT in io.pressed:
        return "/system/apps/menu"

    if BUTTON_LEFT in io.pressed or BUTTON_RIGHT in io.pressed:
        start_new_game()

    return None


def draw_title_state():
    draw_playfield_base()

    screen.font = TITLE_FONT
    screen.brush = TITLE_COLOR
    title_width, title_height = screen.measure_text(TITLE_TEXT)
    screen.text(TITLE_TEXT, (SCREEN_WIDTH - title_width) // 2, SCREEN_HEIGHT // 2 - title_height - 20)

    if (io.ticks // 400) % 2 == 0:
        screen.font = PROMPT_FONT
        screen.brush = HUD_TEXT_COLOR
        prompt_width, _ = screen.measure_text(TITLE_PROMPT)
        screen.text(TITLE_PROMPT, (SCREEN_WIDTH - prompt_width) // 2, SCREEN_HEIGHT // 2 + 4)

    screen.font = HUD_FONT
    screen.brush = HUD_TEXT_COLOR
    hint_width, _ = screen.measure_text(TITLE_HINT)
    screen.text(TITLE_HINT, (SCREEN_WIDTH - hint_width) // 2, SCREEN_HEIGHT // 2 + 28)

    best_text = f"Session best: {scoreboard['session_best']}"
    best_width, _ = screen.measure_text(best_text)
    screen.text(best_text, (SCREEN_WIDTH - best_width) // 2, SCREEN_HEIGHT - HUD_LINE_HEIGHT - HUD_MARGIN)


def update_play_state(dt):
    global game_state, ball_speed_preserved

    if BUTTON_EXIT in io.pressed:
        return "/system/apps/menu"

    direction = get_paddle_direction()

    if direction != input_state["last_direction"]:
        paddle["hold_start"] = None
    input_state["last_direction"] = direction

    if direction != 0:
        now_ticks = io.ticks
        if paddle["hold_start"] is None:
            paddle["hold_start"] = now_ticks
        hold_ms = now_ticks - paddle["hold_start"]
        speed_multiplier = 1.0 + (0.35 if hold_ms >= PADDLE_ACCEL_HOLD_MS else 0.0)
        displacement = direction * paddle["speed"] * speed_multiplier * dt
        half_width = paddle["width"] / 2.0
        paddle["x"] = clamp(paddle["x"] + displacement, half_width, SCREEN_WIDTH - half_width)
    else:
        paddle["hold_start"] = None

    prev_y = ball["y"]

    ball["x"] += ball["vx"] * dt
    ball["y"] += ball["vy"] * dt

    radius = ball["radius"]

    if ball["x"] - radius <= 0:
        ball["x"] = radius
        ball["vx"] = abs(ball["vx"])
    elif ball["x"] + radius >= SCREEN_WIDTH:
        ball["x"] = SCREEN_WIDTH - radius
        ball["vx"] = -abs(ball["vx"])

    if ball["y"] - radius <= 0:
        ball["y"] = radius
        ball["vy"] = abs(ball["vy"])

    paddle_top = paddle["y"]
    paddle_half = paddle["width"] / 2.0

    crossed_plane = prev_y + radius <= paddle_top <= ball["y"] + radius
    within_bounds = abs(ball["x"] - paddle["x"]) <= paddle_half + radius

    if crossed_plane and within_bounds and ball["vy"] > 0:
        ball["y"] = paddle_top - radius
        ball["vy"] = -abs(ball["vy"])

        if paddle_half > 0:
            offset_ratio = clamp((ball["x"] - paddle["x"]) / paddle_half, -1.0, 1.0)
            ball["vx"] += offset_ratio * 60.0

        apply_speed_ramp()
        scoreboard["current"] = min(scoreboard["current"] + 1, 9999)
        if scoreboard["current"] > scoreboard["session_best"]:
            scoreboard["session_best"] = scoreboard["current"]
        ball_speed_preserved = clamp(get_ball_speed(), BALL_START_SPEED, speed_ramp["cap"])

    if ball["y"] - radius > SCREEN_HEIGHT:
        ball_speed_preserved = clamp(get_ball_speed(), BALL_START_SPEED, speed_ramp["cap"])
        scoreboard["lives"] = max(0, scoreboard["lives"] - 1)
        if scoreboard["current"] > scoreboard["session_best"]:
            scoreboard["session_best"] = scoreboard["current"]
        mark_round_result("ball_missed")
        if scoreboard["lives"] > 0:
            game_state = GameState.MISS
        else:
            game_state = GameState.GAME_OVER
        return None

    ball_speed_preserved = clamp(get_ball_speed(), BALL_START_SPEED, speed_ramp["cap"])
    return None


def draw_playfield_base():
    screen.brush = BACKGROUND_COLOR
    screen.clear()


def draw_paddle_shape():
    screen.brush = PADDLE_COLOR
    width = int(paddle["width"])
    height = int(paddle["height"])
    left = int(paddle["x"] - paddle["width"] / 2.0)
    top = int(paddle["y"])
    screen.draw(shapes.rounded_rectangle(left, top, width, height, 4))


def draw_ball_shape():
    screen.brush = BALL_COLOR
    screen.draw(shapes.circle(int(ball["x"]), int(ball["y"]), int(ball["radius"])))


def draw_hud():
    screen.font = HUD_FONT

    screen.brush = HUD_TEXT_COLOR
    score_text = f"Score: {scoreboard['current']}"
    screen.text(score_text, HUD_MARGIN, HUD_MARGIN)

    lives_text = f"Lives: {scoreboard['lives']}"
    lives_width, _ = screen.measure_text(lives_text)
    screen.text(lives_text, (SCREEN_WIDTH - lives_width) // 2, HUD_MARGIN)

    best_text = f"Best: {scoreboard['session_best']}"
    best_width, _ = screen.measure_text(best_text)
    if scoreboard["session_best"] > 0 and scoreboard["current"] == scoreboard["session_best"]:
        screen.brush = HUD_HIGHLIGHT_COLOR
    else:
        screen.brush = HUD_TEXT_COLOR
    screen.text(best_text, SCREEN_WIDTH - best_width - HUD_MARGIN, HUD_MARGIN)
    screen.brush = HUD_TEXT_COLOR


def draw_play_state():
    draw_playfield_base()
    draw_paddle_shape()
    draw_ball_shape()
    draw_hud()


def draw_overlay(title, lines):
    original_font = screen.font

    max_width = 0
    line_height = HUD_LINE_HEIGHT

    if title:
        screen.font = TITLE_FONT
        title_width, title_height = screen.measure_text(title)
        max_width = max(max_width, title_width)
    else:
        title_height = 0

    screen.font = HUD_FONT
    for line in lines:
        width, _ = screen.measure_text(line)
        max_width = max(max_width, width)

    box_width = max_width + OVERLAY_TEXT_LEFT_PADDING * 2
    box_height = title_height + len(lines) * line_height + 24
    origin_x = (SCREEN_WIDTH - box_width) // 2
    origin_y = (SCREEN_HEIGHT - box_height) // 2

    screen.brush = OVERLAY_FRAME_COLOR
    screen.draw(shapes.rounded_rectangle(origin_x - 2, origin_y - 2, box_width + 4, box_height + 4, 6))
    screen.brush = OVERLAY_BG_COLOR
    screen.draw(shapes.rounded_rectangle(origin_x, origin_y, box_width, box_height, 6))

    cursor_y = origin_y + 8
    if title:
        screen.font = TITLE_FONT
        screen.brush = HUD_HIGHLIGHT_COLOR
        title_width, _ = screen.measure_text(title)
        screen.text(title, origin_x + (box_width - title_width) // 2, cursor_y)
        cursor_y += title_height + 8

    screen.font = HUD_FONT
    screen.brush = HUD_TEXT_COLOR
    for line in lines:
        width, _ = screen.measure_text(line)
        line_x = origin_x + (box_width - width) // 2
        screen.text(line, line_x, cursor_y)
        cursor_y += line_height

    screen.font = original_font


def update_miss_state(_dt):
    global game_state

    if BUTTON_EXIT in io.pressed:
        return "/system/apps/menu"

    if BUTTON_LEFT in io.pressed or BUTTON_RIGHT in io.pressed:
        round_result["miss_reason"] = ""
        stage_new_round(direction_upwards=True, speed_override=ball_speed_preserved)
        game_state = GameState.PLAY

    return None


def _format_reason_text(raw_reason):
    if not raw_reason:
        return ""
    if not isinstance(raw_reason, str):
        return ""
    words = raw_reason.replace("_", " ").split()
    if not words:
        return ""

    def _title_case(word):
        if not word:
            return ""
        first = word[0:1].upper()
        rest = word[1:].lower()
        return first + rest

    return " ".join(_title_case(word) for word in words if word)


def draw_miss_state():
    draw_playfield_base()
    draw_hud()

    reason = _format_reason_text(round_result.get("miss_reason"))
    lines = []
    if reason:
        lines.append(f"Reason: {reason}")
    lines.extend(
        [
            f"Score: {scoreboard['current']}",
            f"Lives left: {scoreboard['lives']}",
            f"Best: {scoreboard['session_best']}",
            "Press A/C to continue",
            "Press B to exit",
        ]
    )
    draw_overlay("Ball Missed!", lines)


def update_game_over_state(_dt):
    global game_state, ball_speed_preserved

    if BUTTON_EXIT in io.pressed:
        return "/system/apps/menu"

    if BUTTON_LEFT in io.pressed or BUTTON_RIGHT in io.pressed:
        reset_scoreboard(preserve_best=True)
        stage_new_round(direction_upwards=True)
        ball_speed_preserved = BALL_START_SPEED
        round_result["miss_reason"] = ""
        game_state = GameState.PLAY

    return None


def draw_game_over_state():
    draw_playfield_base()
    draw_hud()

    reason = _format_reason_text(round_result.get("miss_reason"))
    lines = []
    if reason:
        lines.append(f"Reason: {reason}")
    lines.extend(
        [
            f"Score: {scoreboard['current']}",
            f"Best: {scoreboard['session_best']}",
            "Press A/C to play again",
            "Press B to exit",
        ]
    )
    draw_overlay("Game Over", lines)


def update():
    now = io.ticks
    dt = compute_frame_dt(now)

    if game_state == GameState.TITLE:
        exit_path = update_title_state(dt)
        draw_title_state()
        return exit_path

    if game_state == GameState.PLAY:
        exit_path = update_play_state(dt)
        draw_play_state()
        return exit_path

    if game_state == GameState.MISS:
        exit_path = update_miss_state(dt)
        draw_miss_state()
        return exit_path

    if game_state == GameState.GAME_OVER:
        exit_path = update_game_over_state(dt)
        draw_game_over_state()
        return exit_path

    # Fallback to title if state becomes unknown
    draw_title_state()
    return None


def init():
    global game_state, ball_speed_preserved

    game_state = GameState.TITLE
    reset_scoreboard(preserve_best=True)
    round_result["miss_reason"] = ""
    stage_new_round(direction_upwards=True)
    ball_speed_preserved = BALL_START_SPEED
    reset_tick_timer()


if __name__ == "__main__":
    run(update, init=init)
