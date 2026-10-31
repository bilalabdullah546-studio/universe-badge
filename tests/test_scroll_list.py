import importlib.util
import sys
import types
import unittest
from pathlib import Path


# Load this badge app module with lightweight runtime stubs so its navigation
# logic can be tested on CPython without the device's badgeware runtime.
badgeware = types.ModuleType("badgeware")
badgeware.PixelFont = type(
    "PixelFont", (), {"load": staticmethod(lambda _path: object())}
)
badgeware.screen = types.SimpleNamespace()
badgeware.brushes = types.SimpleNamespace(color=lambda *args: object())
badgeware.shapes = types.SimpleNamespace()
badgeware.io = types.SimpleNamespace(
    BUTTON_UP=1,
    BUTTON_DOWN=2,
    BUTTON_A=3,
    BUTTON_C=4,
    BUTTON_B=5,
    pressed=set(),
    held=set(),
    ticks=0,
)
sys.modules["badgeware"] = badgeware

module_path = Path(__file__).parents[1] / "apps" / "files" / "scroll_list.py"
spec = importlib.util.spec_from_file_location("badge_scroll_list", module_path)
scroll_list_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scroll_list_module)
ScrollList = scroll_list_module.ScrollList


class ScrollListTests(unittest.TestCase):
    def test_empty_list_ignores_up_and_down(self):
        listing = ScrollList()
        listing.on_button_down()
        listing.on_button_down()
        listing.on_button_up()
        self.assertIsNone(listing.index)

    def test_non_empty_wraparound_is_unchanged(self):
        listing = ScrollList(contents=["first", "second"])
        listing.on_button_down()
        self.assertEqual(listing.index, 0)
        listing.on_button_up()
        self.assertEqual(listing.index, 1)
        listing.on_button_down()
        self.assertEqual(listing.index, 0)


if __name__ == "__main__":
    unittest.main()
