import os
import tempfile
import unittest
from unittest.mock import patch

from apps.pokedex import fetch_sprites


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

    def test_successful_download_atomically_publishes_file(self):
        with tempfile.TemporaryDirectory() as output_dir:
            def write_download(command, **kwargs):
                with open(command[-1], "wb") as output:
                    output.write(b"complete png payload")
                return type("Result", (), {"returncode": 0})()

            with patch.object(fetch_sprites.subprocess, "run", side_effect=write_download):
                result = fetch_sprites.fetch_sprite(25, output_dir, shiny=True)

            final_path = os.path.join(output_dir, "shiny", "25.png")
            self.assertEqual(result, (25, True, True))
            with open(final_path, "rb") as downloaded:
                self.assertEqual(downloaded.read(), b"complete png payload")
            self.assertFalse(os.path.exists(final_path + ".part"))

    def test_existing_file_is_not_downloaded_again(self):
        with tempfile.TemporaryDirectory() as output_dir:
            final_dir = os.path.join(output_dir, "sprites")
            os.makedirs(final_dir)
            final_path = os.path.join(final_dir, "7.png")
            with open(final_path, "wb") as existing:
                existing.write(b"existing file")

            with patch.object(fetch_sprites.subprocess, "run") as run:
                result = fetch_sprites.fetch_sprite(7, output_dir)

            self.assertEqual(result, (7, False, True))
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
