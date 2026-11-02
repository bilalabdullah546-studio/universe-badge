"""Regression tests for the badge apps' secrets import path handling.

The apps import MicroPython-only badgeware modules at import time. Extracting
just each credential helper keeps these focused tests runnable under CPython.
"""
import ast
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_FUNCTIONS = {
    "wifi": (REPO_ROOT / "apps" / "wifi" / "__init__.py", "load_wifi_credentials"),
    "stocks": (REPO_ROOT / "apps" / "stocks" / "__init__.py", "get_wifi_credentials"),
    "weather": (REPO_ROOT / "apps" / "weather" / "__init__.py", "get_wifi_credentials"),
}


def load_credentials_function(app_name):
    source_path, function_name = APP_FUNCTIONS[app_name]
    tree = ast.parse(source_path.read_text())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == function_name
    )
    isolated_module = ast.Module(body=[function], type_ignores=[])
    namespace = {
        "sys": sys,
        "WIFI_SSID": None,
        "WIFI_PASSWORD": None,
        "GITHUB_USERNAME": None,
        "WEATHER_LOCATION": None,
    }
    exec(compile(isolated_module, str(source_path), "exec"), namespace)
    return namespace[function_name], namespace


class CredentialImportPathTests(unittest.TestCase):
    def setUp(self):
        self.original_path = list(sys.path)

    def tearDown(self):
        sys.path[:] = self.original_path

    def test_missing_config_does_not_accumulate_root_path(self):
        real_import = __import__

        def missing_secrets(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "secrets":
                raise ImportError("device secrets.py is missing")
            return real_import(name, globals, locals, fromlist, level)

        for app_name in APP_FUNCTIONS:
            with self.subTest(app=app_name):
                load, namespace = load_credentials_function(app_name)
                with patch("builtins.__import__", side_effect=missing_secrets):
                    self.assertFalse(load())
                    self.assertFalse(load())

                self.assertEqual(sys.path, self.original_path)
                self.assertIsNone(namespace["WIFI_SSID"])
                self.assertIsNone(namespace["WIFI_PASSWORD"])

    def test_successful_import_restores_path(self):
        real_import = __import__
        fake_secrets = types.ModuleType("secrets")
        fake_secrets.WIFI_SSID = "test-network"
        fake_secrets.WIFI_PASSWORD = "test-password"
        fake_secrets.GITHUB_USERNAME = "test-user"
        fake_secrets.WEATHER_LOCATION = "Test City"

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "secrets":
                return fake_secrets
            return real_import(name, globals, locals, fromlist, level)

        for app_name in APP_FUNCTIONS:
            with self.subTest(app=app_name):
                load, namespace = load_credentials_function(app_name)
                with patch("builtins.__import__", side_effect=fake_import):
                    self.assertTrue(load())

                self.assertEqual(sys.path, self.original_path)
                self.assertEqual(namespace["WIFI_SSID"], "test-network")
                self.assertEqual(namespace["WIFI_PASSWORD"], "test-password")
                if app_name == "wifi":
                    self.assertEqual(namespace["GITHUB_USERNAME"], "test-user")
                if app_name == "weather":
                    self.assertEqual(namespace["WEATHER_LOCATION"], "Test City")

    def test_unexpected_import_exception_still_restores_path(self):
        real_import = __import__

        def broken_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "secrets":
                raise RuntimeError("secrets module is broken")
            return real_import(name, globals, locals, fromlist, level)

        for app_name in APP_FUNCTIONS:
            with self.subTest(app=app_name):
                load, _ = load_credentials_function(app_name)
                with patch("builtins.__import__", side_effect=broken_import):
                    with self.assertRaises(RuntimeError):
                        load()

                self.assertEqual(sys.path, self.original_path)


if __name__ == "__main__":
    unittest.main()
