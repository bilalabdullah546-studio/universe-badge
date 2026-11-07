import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


class AlreadyConnectedWlan:
    def __init__(self):
        self.connect_calls = 0
        self.active_calls = []

    def active(self, enabled):
        self.active_calls.append(enabled)

    def isconnected(self):
        return True

    def connect(self, ssid, password):
        self.connect_calls += 1


def load_wlan_start(relative_path):
    source_path = ROOT / relative_path
    tree = ast.parse(source_path.read_text(), filename=str(source_path))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "wlan_start"
    )
    wlan = AlreadyConnectedWlan()
    namespace = {
        "wlan": None,
        "ticks_start": None,
        "connected": False,
        "WIFI_PASSWORD": "test-password",
        "WIFI_SSID": "test-ssid",
        "WIFI_TIMEOUT": 60,
        "io": SimpleNamespace(ticks=1000),
        "network": SimpleNamespace(STA_IF=0, WLAN=lambda _interface: wlan),
    }
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace, wlan


class WifiInitialStateTests(unittest.TestCase):
    def test_weather_marks_existing_connection_as_connected(self):
        namespace, wlan = load_wlan_start("apps/weather/__init__.py")
        self.assertTrue(namespace["wlan_start"]())
        self.assertTrue(namespace["connected"])
        self.assertEqual(wlan.active_calls, [True])
        self.assertEqual(wlan.connect_calls, 0)

    def test_stocks_marks_existing_connection_as_connected(self):
        namespace, wlan = load_wlan_start("apps/stocks/__init__.py")
        self.assertTrue(namespace["wlan_start"]())
        self.assertTrue(namespace["connected"])
        self.assertEqual(wlan.active_calls, [True])
        self.assertEqual(wlan.connect_calls, 0)


if __name__ == "__main__":
    unittest.main()
