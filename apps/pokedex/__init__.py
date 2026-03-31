import sys
import os

sys.path.insert(0, "/system/apps/pokedex")
os.chdir("/system/apps/pokedex")

from badgeware import io, brushes, shapes, Image, run, PixelFont, screen, Matrix, file_exists
import random
import math
import network
from urllib.urequest import urlopen
import gc
import json


# Colours
white = brushes.color(235, 245, 255)
faded = brushes.color(235, 245, 255, 100)
red = brushes.color(220, 50, 50)
dark_red = brushes.color(150, 30, 30)
black = brushes.color(0, 0, 0)
dark_bg = brushes.color(15, 15, 25)

# Type colours
TYPE_COLOURS = {
    "normal": (168, 168, 120),
    "fire": (240, 80, 48),
    "water": (104, 144, 240),
    "grass": (120, 200, 80),
    "electric": (248, 208, 48),
    "ice": (152, 216, 216),
    "fighting": (192, 48, 40),
    "poison": (160, 64, 160),
    "ground": (224, 192, 104),
    "flying": (168, 144, 240),
    "psychic": (248, 88, 136),
    "bug": (168, 184, 32),
    "rock": (184, 160, 56),
    "ghost": (112, 88, 152),
    "dragon": (112, 56, 248),
    "dark": (112, 88, 72),
    "steel": (184, 184, 208),
    "fairy": (238, 153, 172),
}

small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")

WIFI_TIMEOUT = 30
POKEMON_URL = "https://pokeapi.co/api/v2/pokemon/{id}"
SPRITE_URL = "https://wsrv.nl/?url=https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{id}.png&w=64&h=64&output=png"

WIFI_PASSWORD = None
WIFI_SSID = None
wlan = None
connected = False
ticks_start = None

# State
current_id = 25  # Start with Pikachu
pokemon_data = None
pokemon_sprite = None
fetching = False
fetch_task = None
stat_scroll = 0
view_mode = 0  # 0 = main view, 1 = stats view

STAT_NAMES = ["hp", "attack", "defence", "sp.atk", "sp.def", "speed"]
STAT_KEYS = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]
MAX_POKEMON = 151  # Gen 1


def get_wifi_details():
    global WIFI_PASSWORD, WIFI_SSID
    if WIFI_SSID is not None:
        return True
    try:
        sys.path.insert(0, "/")
        from secrets import WIFI_PASSWORD, WIFI_SSID
        sys.path.pop(0)
    except ImportError:
        WIFI_PASSWORD = None
        WIFI_SSID = None
    return WIFI_SSID is not None


def wlan_start():
    global wlan, ticks_start, connected
    if ticks_start is None:
        ticks_start = io.ticks
    if connected:
        return True
    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if wlan.isconnected():
            connected = True
            return True
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    connected = wlan.isconnected()
    if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
        return connected
    return False


def cache_path(pokemon_id, ext):
    return f"/pokemon_{pokemon_id}.{ext}"


def async_fetch_to_disk(url, file):
    if file_exists(file):
        return
    try:
        response = urlopen(url, headers={"User-Agent": "Pokedex Badge"})
        data = bytearray(512)
        total = 0
        with open(file, "wb") as f:
            while True:
                if (length := response.readinto(data)) == 0:
                    break
                total += length
                f.write(data[:length])
                yield
        del data
        del response
    except Exception as e:
        # Clean up partial file
        try:
            os.remove(file)
        except:
            pass
        raise RuntimeError(f"Fetch {url} failed: {e}") from e


def fetch_pokemon(pokemon_id):
    global pokemon_data, pokemon_sprite

    # Fetch data
    data_file = cache_path(pokemon_id, "json")
    yield from async_fetch_to_disk(
        POKEMON_URL.format(id=pokemon_id), data_file
    )
    r = json.loads(open(data_file, "r").read())
    pokemon_data = {
        "name": r["name"].upper(),
        "id": r["id"],
        "types": [t["type"]["name"] for t in r["types"]],
        "stats": {s["stat"]["name"]: s["base_stat"] for s in r["stats"]},
        "height": r["height"],
        "weight": r["weight"],
    }
    del r
    gc.collect()

    # Fetch sprite
    sprite_file = cache_path(pokemon_id, "png")
    yield from async_fetch_to_disk(
        SPRITE_URL.format(id=pokemon_id), sprite_file
    )
    pokemon_sprite = Image.load(sprite_file)


def type_brush(type_name):
    rgb = TYPE_COLOURS.get(type_name, (168, 168, 120))
    return brushes.color(*rgb)


def draw_type_badge(type_name, x, y):
    label = type_name.upper()
    screen.font = small_font
    w, h = screen.measure_text(label)
    screen.brush = type_brush(type_name)
    screen.draw(shapes.rounded_rectangle(x, y, w + 6, h + 2, 3))
    screen.brush = white
    screen.text(label, x + 3, y + 1)
    return w + 8


def draw_stat_bar(name, value, x, y, max_val=255):
    bar_width = 50
    fill = int((value / max_val) * bar_width)

    screen.font = small_font
    screen.brush = faded
    screen.text(name, x, y)

    # Bar background
    screen.brush = brushes.color(40, 40, 50)
    screen.draw(shapes.rounded_rectangle(x + 42, y + 1, bar_width, 6, 2))

    # Bar fill — colour based on value
    if value >= 100:
        screen.brush = brushes.color(100, 220, 100)
    elif value >= 60:
        screen.brush = brushes.color(220, 200, 60)
    else:
        screen.brush = brushes.color(220, 80, 60)
    screen.draw(shapes.rounded_rectangle(x + 42, y + 1, fill, 6, 2))

    # Value text
    screen.brush = white
    screen.text(str(value), x + 95, y)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    screen.text(text, 80 - (w / 2), y)


def draw_main_view():
    # Pokeball red header bar
    screen.brush = red
    screen.draw(shapes.rectangle(0, 0, 160, 14))
    screen.brush = dark_red
    screen.draw(shapes.rectangle(0, 13, 160, 1))

    # Pokédex title + number
    screen.font = large_font
    screen.brush = white
    if pokemon_data:
        num_str = f"#{pokemon_data['id']:03d}"
        screen.text(num_str, 3, 1)
        name = pokemon_data["name"]
        w, _ = screen.measure_text(name)
        screen.text(name, 157 - w, 1)
    else:
        center_text("POKEDEX", 1)

    # Sprite area
    if pokemon_sprite:
        screen.blit(pokemon_sprite, 5, 18)
    else:
        # Loading spinner
        screen.brush = faded
        squircle = shapes.squircle(0, 0, 8, 4)
        for i in range(3):
            squircle.transform = Matrix().translate(37, 50).rotate(
                (io.ticks + i * 5000) / 40).scale(1 + i / 1.5)
            screen.draw(squircle)

    if pokemon_data:
        # Type badges
        x = 72
        y = 20
        for t in pokemon_data["types"]:
            x += draw_type_badge(t, x, y)

        # Height / Weight
        screen.font = small_font
        screen.brush = faded
        h_m = pokemon_data["height"] / 10
        w_kg = pokemon_data["weight"] / 10
        screen.text(f"{h_m:.1f}m", 72, 32)
        screen.text(f"{w_kg:.1f}kg", 110, 32)

        # Mini stats preview
        y_start = 44
        for i, (name, key) in enumerate(zip(STAT_NAMES, STAT_KEYS)):
            val = pokemon_data["stats"].get(key, 0)
            draw_stat_bar(name, val, 72, y_start + i * 11)

    # Nav hint at bottom
    screen.brush = brushes.color(80, 80, 100)
    screen.draw(shapes.rectangle(0, 112, 160, 8))
    screen.font = small_font
    screen.brush = faded
    screen.text("A:prev  B:rand  C:next", 12, 112)


def draw_connecting():
    screen.brush = dark_bg
    screen.draw(shapes.rectangle(0, 0, 160, 120))

    screen.font = large_font
    screen.brush = red
    center_text("POKEDEX", 20)

    screen.font = small_font
    screen.brush = faded

    dots = "." * (int(io.ticks / 500) % 4)
    center_text(f"Connecting{dots}", 50)


def draw_no_wifi():
    screen.brush = dark_bg
    screen.draw(shapes.rectangle(0, 0, 160, 120))

    screen.font = large_font
    screen.brush = red
    center_text("POKEDEX", 10)

    screen.font = small_font
    screen.brush = white
    center_text("No WiFi configured!", 35)
    screen.brush = faded
    center_text("Edit secrets.py to", 55)
    center_text("set WIFI_SSID and", 67)
    center_text("WIFI_PASSWORD", 79)


def update():
    global current_id, fetch_task, fetching, pokemon_data, pokemon_sprite, connected

    # Clear screen
    screen.brush = dark_bg
    screen.draw(shapes.rectangle(0, 0, 160, 120))

    # Input handling
    changed = False
    if io.BUTTON_C in io.pressed:
        current_id = (current_id % MAX_POKEMON) + 1
        changed = True
    if io.BUTTON_A in io.pressed:
        current_id = ((current_id - 2) % MAX_POKEMON) + 1
        changed = True
    if io.BUTTON_B in io.pressed:
        current_id = random.randint(1, MAX_POKEMON)
        changed = True

    # Force refresh on A+C hold
    if io.BUTTON_A in io.held and io.BUTTON_C in io.held:
        changed = True
        # Delete cache
        try:
            os.remove(cache_path(current_id, "json"))
            os.remove(cache_path(current_id, "png"))
        except:
            pass

    if changed:
        pokemon_data = None
        pokemon_sprite = None
        fetch_task = None
        fetching = False
        gc.collect()

    # WiFi + fetch logic
    if not get_wifi_details():
        draw_no_wifi()
        return

    if not wlan_start():
        if not connected:
            draw_connecting()
            return

    connected = True

    # Kick off fetch if needed
    if not pokemon_data and not fetching:
        fetching = True
        fetch_task = fetch_pokemon(current_id)

    if fetch_task:
        try:
            next(fetch_task)
        except StopIteration:
            fetch_task = None
            fetching = False
        except Exception:
            fetch_task = None
            fetching = False

    draw_main_view()


if __name__ == "__main__":
    run(update)
