import os
import runpy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from dotenv import load_dotenv

from .environment import env_bool, optional_positive_int, required_env


class EnvironmentTests(SimpleTestCase):
    def test_required_env_rejects_missing_empty_or_whitespace(self):
        for values in ({}, {"TEST_SECRET": ""}, {"TEST_SECRET": " "}):
            with self.subTest(values=values):
                with patch.dict(os.environ, values, clear=True):
                    with self.assertRaisesMessage(ImproperlyConfigured, "TEST_SECRET"):
                        required_env("TEST_SECRET")

    def test_required_env_preserves_secret_characters(self):
        with patch.dict(os.environ, {"TEST_SECRET": "test-${VALUE}-#&$"}):
            self.assertEqual(required_env("TEST_SECRET"), "test-${VALUE}-#&$")

    def test_booleans_are_parsed_explicitly(self):
        for value, expected in (
            ("True", True), (" true ", True), ("1", True), ("YES", True),
            ("on", True), ("False", False), (" false ", False), ("0", False),
            ("NO", False), ("off", False),
        ):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"TEST_DEBUG": value}):
                    self.assertIs(env_bool("TEST_DEBUG"), expected)

    def test_boolean_defaults_to_false_and_rejects_invalid_values(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(env_bool("TEST_DEBUG"))
            self.assertTrue(env_bool("TEST_DEBUG", default=True))
        for value in ("", "maybe", "2"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"TEST_DEBUG": value}):
                    with self.assertRaisesMessage(ImproperlyConfigured, "TEST_DEBUG"):
                        env_bool("TEST_DEBUG")

    def test_optional_user_id(self):
        for value, expected in (("", None), (" ", None), ("1", 1), (" 27 ", 27)):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"USER_ID": value}):
                    self.assertEqual(optional_positive_int("USER_ID"), expected)
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(optional_positive_int("USER_ID"))

    def test_invalid_user_id_is_rejected(self):
        for value in ("0", "-1", "ana", "1.5"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"USER_ID": value}):
                    with self.assertRaisesMessage(ImproperlyConfigured, "USER_ID"):
                        optional_positive_int("USER_ID")

    def test_dotenv_preserves_process_values_and_does_not_interpolate_secrets(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "DJANGO_SECRET_KEY=file-key\n"
                "TEST_API_KEY='literal-${OTHER_VALUE}'\n"
                "DEBUG=True\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"DJANGO_SECRET_KEY": "process-key", "OTHER_VALUE": "expanded"},
                clear=True,
            ):
                load_dotenv(path, override=False, interpolate=False)
                self.assertEqual(os.environ["DJANGO_SECRET_KEY"], "process-key")
                self.assertEqual(os.environ["TEST_API_KEY"], "literal-${OTHER_VALUE}")
                self.assertTrue(env_bool("DEBUG"))


class SettingsEnvironmentTests(SimpleTestCase):
    def load_settings(self, values):
        path = Path(__file__).with_name("settings.py")
        with patch.dict(os.environ, values, clear=True):
            with patch("dotenv.load_dotenv") as loader:
                settings = runpy.run_path(
                    str(path), run_name="SpendingAdmin._settings_test"
                )
        loader.assert_called_once_with(
            path.parent.parent / ".env", override=False, interpolate=False
        )
        return settings

    def test_settings_use_environment_and_typed_values(self):
        values = self.load_settings({
            "DJANGO_SECRET_KEY": "settings-test-key",
            "DEBUG": "False",
            "ALLOWED_HOSTS": " localhost, example.com, ,127.0.0.1 ",
            "GEMINI_API_KEY": "test-api-key",
            "GEMINI_MODEL": " configured-model ",
            "USER_ID": "8",
        })

        self.assertEqual(values["SECRET_KEY"], "settings-test-key")
        self.assertFalse(values["DEBUG"])
        self.assertEqual(
            values["ALLOWED_HOSTS"], ["localhost", "example.com", "127.0.0.1"]
        )
        self.assertEqual(values["GEMINI_API_KEY"], "test-api-key")
        self.assertEqual(values["GEMINI_MODEL"], "configured-model")
        self.assertEqual(values["USER_ID"], 8)
        self.assertEqual(values["TIME_ZONE"], "America/Mexico_City")

    def test_optional_chat_configuration_is_not_required_for_django(self):
        values = self.load_settings({
            "DJANGO_SECRET_KEY": "settings-test-key", "DEBUG": "True",
        })

        self.assertEqual(values["GEMINI_API_KEY"], "")
        self.assertEqual(values["GEMINI_MODEL"], "")
        self.assertIsNone(values["USER_ID"])

    def test_missing_secret_fails_without_printing_secret_values(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "DJANGO_SECRET_KEY"):
            self.load_settings({"DEBUG": "True"})

    def test_debug_defaults_to_false_with_explicit_hosts(self):
        values = self.load_settings({
            "DJANGO_SECRET_KEY": "settings-test-key",
            "ALLOWED_HOSTS": "example.com",
        })
        self.assertFalse(values["DEBUG"])

    def test_debug_false_requires_nonempty_hosts(self):
        for hosts in ("", " , "):
            with self.subTest(hosts=hosts):
                with self.assertRaisesMessage(ImproperlyConfigured, "ALLOWED_HOSTS"):
                    self.load_settings({
                        "DJANGO_SECRET_KEY": "settings-test-key",
                        "DEBUG": "False",
                        "ALLOWED_HOSTS": hosts,
                    })
