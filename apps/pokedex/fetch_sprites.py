#!/usr/bin/env python3
"""Download Gen 1 Pokemon sprites for the badge Pokedex app.

Fetches normal and shiny sprites (64x64 PNG) from PokeAPI via wsrv.nl proxy.
Sprites are Nintendo/Game Freak/The Pokemon Company's intellectual property
and are NOT included in this repository. This script fetches them for
personal use on your badge.

Usage:
    python3 fetch_sprites.py              # Download to ./sprites/ and ./shiny/
    python3 fetch_sprites.py /Volumes/BADGER  # Download directly to badge
"""

import os
import sys
import struct
import zlib
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://wsrv.nl/?url=https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{path}{id}.png&w=80&h=80&output=png"
MAX_POKEMON = 151
WORKERS = 10
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def is_valid_png(file_path):
    """Return True only for a structurally complete PNG with valid chunk CRCs."""
    try:
        with open(file_path, "rb") as sprite:
            if sprite.read(8) != PNG_SIGNATURE:
                return False

            file_size = os.fstat(sprite.fileno()).st_size
            saw_ihdr = False
            saw_idat = False
            decompressor = zlib.decompressobj()

            while True:
                header = sprite.read(8)
                if len(header) != 8:
                    return False

                chunk_length = struct.unpack(">I", header[:4])[0]
                chunk_type = header[4:]
                remaining = file_size - sprite.tell()
                if chunk_length > remaining - 4:
                    return False

                chunk_data = sprite.read(chunk_length)
                crc_bytes = sprite.read(4)
                if len(chunk_data) != chunk_length or len(crc_bytes) != 4:
                    return False

                expected_crc = struct.unpack(">I", crc_bytes)[0]
                actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
                if actual_crc != expected_crc:
                    return False

                if not saw_ihdr:
                    if chunk_type != b"IHDR" or chunk_length != 13:
                        return False
                    saw_ihdr = True
                elif chunk_type == b"IHDR":
                    return False

                if chunk_type == b"IDAT":
                    saw_idat = True
                    try:
                        decompressor.decompress(chunk_data)
                    except zlib.error:
                        return False

                if chunk_type == b"IEND":
                    if chunk_length != 0 or not saw_idat:
                        return False
                    return (
                        decompressor.eof
                        and not decompressor.unused_data
                        and not decompressor.unconsumed_tail
                        and sprite.read(1) == b""
                    )
    except (OSError, OverflowError, struct.error, zlib.error):
        return False


def fetch_sprite(pokemon_id, output_dir, shiny=False):
    path = "shiny/" if shiny else ""
    subdir = "shiny" if shiny else "sprites"
    out_dir = os.path.join(output_dir, subdir)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{pokemon_id}.png")

    if is_valid_png(out_path):
        return pokemon_id, shiny, True

    url = BASE_URL.format(id=pokemon_id, path=path)
    temp_path = out_path + ".part"
    try:
        result = subprocess.run(
            ["curl", "-sf", url, "-o", temp_path],
            capture_output=True, timeout=30,
        )
        if result.returncode != 0 or not is_valid_png(temp_path):
            try:
                os.remove(temp_path)
            except FileNotFoundError:
                pass
            return pokemon_id, shiny, False

        # Publish only a fully validated image; preserve any old file until
        # the replacement is ready so interrupted downloads never become cache hits.
        os.replace(temp_path, out_path)
        return pokemon_id, shiny, True
    except Exception:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
        return pokemon_id, shiny, False


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    tasks = []
    for pid in range(1, MAX_POKEMON + 1):
        tasks.append((pid, False))  # normal
        tasks.append((pid, True))   # shiny

    total = len(tasks)
    done = 0
    failed = []

    print(f"Fetching {total} sprites ({MAX_POKEMON} normal + {MAX_POKEMON} shiny)...")

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(fetch_sprite, pid, output_dir, is_shiny): (pid, is_shiny)
            for pid, is_shiny in tasks
        }
        for future in as_completed(futures):
            pid, is_shiny, ok = future.result()
            done += 1
            label = "shiny" if is_shiny else "normal"
            if not ok:
                failed.append((pid, label))
                print(f"  FAILED: {label} #{pid}")
            if done % 50 == 0:
                print(f"  {done}/{total} complete...")

    print(f"\nDone! {done - len(failed)}/{total} sprites downloaded.")
    if failed:
        print(f"{len(failed)} failed: {failed}")

    # Verify
    sprites_dir = os.path.join(output_dir, "sprites")
    shiny_dir = os.path.join(output_dir, "shiny")
    normal_count = len(os.listdir(sprites_dir)) if os.path.isdir(sprites_dir) else 0
    shiny_count = len(os.listdir(shiny_dir)) if os.path.isdir(shiny_dir) else 0
    print(f"Normal: {normal_count}, Shiny: {shiny_count}")


if __name__ == "__main__":
    main()
