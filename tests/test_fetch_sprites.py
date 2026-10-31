import os
import struct
import tempfile
import unittest
import zlib
from unittest.mock import patch

from apps.pokedex import fetch_sprites


def make_png():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        fetch_sprites.PNG_SIGNATURE
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )


class FetchSpriteTests(unittest.TestCase):
    def test_failed_download_does_not_leave_partial_final_file(self):
        with tempfile.TemporaryDirectory() as output_dir:
            def write_partial(command, **kwargs):
                with open(command[-1], "wb") as output:
                    output.write(b"partial png data")
                return type("Result", (), {"returncode": 22})()

            with patch.object(fetch_sprites.subprocess, "run", side_effect=write_partial):
                result = fetch_sprites.fetch_sprite(1, output_dir)

            final_path = os.path.join(output_dir, "sprites", "1.png")
            self.assertEqual(result, (1, False, False))
            self.assertFalse(os.path.exists(final_path))
            self.assertFalse(os.path.exists(final_path + ".part"))

    def test_successful_download_atomically_publishes_valid_png(self):
        png = make_png()
        with tempfile.TemporaryDirectory() as output_dir:
            def write_download(command, **kwargs):
                with open(command[-1], "wb") as output:
                    output.write(png)
                return type("Result", (), {"returncode": 0})()

            with patch.object(fetch_sprites.subprocess, "run", side_effect=write_download):
                result = fetch_sprites.fetch_sprite(25, output_dir, shiny=True)

            final_path = os.path.join(output_dir, "shiny", "25.png")
            self.assertEqual(result, (25, True, True))
            with open(final_path, "rb") as downloaded:
                self.assertEqual(downloaded.read(), png)
            self.assertFalse(os.path.exists(final_path + ".part"))

    def test_existing_valid_png_is_not_downloaded_again(self):
        with tempfile.TemporaryDirectory() as output_dir:
            final_dir = os.path.join(output_dir, "sprites")
            os.makedirs(final_dir)
            final_path = os.path.join(final_dir, "7.png")
            with open(final_path, "wb") as existing:
                existing.write(make_png())

            with patch.object(fetch_sprites.subprocess, "run") as run:
                result = fetch_sprites.fetch_sprite(7, output_dir)

            self.assertEqual(result, (7, False, True))
            run.assert_not_called()

    def test_existing_partial_file_is_refetched_and_replaced(self):
        png = make_png()
        with tempfile.TemporaryDirectory() as output_dir:
            final_dir = os.path.join(output_dir, "sprites")
            os.makedirs(final_dir)
            final_path = os.path.join(final_dir, "8.png")
            with open(final_path, "wb") as existing:
                existing.write(b"partial png data")

            def write_download(command, **kwargs):
                with open(command[-1], "wb") as output:
                    output.write(png)
                return type("Result", (), {"returncode": 0})()

            with patch.object(fetch_sprites.subprocess, "run", side_effect=write_download):
                result = fetch_sprites.fetch_sprite(8, output_dir)

            self.assertEqual(result, (8, False, True))
            with open(final_path, "rb") as downloaded:
                self.assertEqual(downloaded.read(), png)
            self.assertFalse(os.path.exists(final_path + ".part"))

    def test_success_status_with_invalid_response_is_not_published(self):
        with tempfile.TemporaryDirectory() as output_dir:
            def write_invalid_response(command, **kwargs):
                with open(command[-1], "wb") as output:
                    output.write(b"<html>proxy error</html>")
                return type("Result", (), {"returncode": 0})()

            with patch.object(fetch_sprites.subprocess, "run", side_effect=write_invalid_response):
                result = fetch_sprites.fetch_sprite(9, output_dir)

            final_path = os.path.join(output_dir, "sprites", "9.png")
            self.assertEqual(result, (9, False, False))
            self.assertFalse(os.path.exists(final_path))
            self.assertFalse(os.path.exists(final_path + ".part"))


if __name__ == "__main__":
    unittest.main()
