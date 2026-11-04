import unittest
from pydantic import ValidationError

from app.core.config import EXPLICIT_TEST_SECRET, Settings

VALID_AUTH = "valid-strong-neo4j-auth"


class TestConfigSettings(unittest.TestCase):
    def test_settings_valid_initialization(self):
        settings = Settings(
            APP_ENV="dev",
            NEO4J_PASSWORD=VALID_AUTH,
            SECRET_KEY="a" * 32,
        )
        self.assertEqual(settings.APP_ENV, "dev")
        self.assertEqual(settings.NEO4J_PASSWORD, VALID_AUTH)
        self.assertEqual(settings.SECRET_KEY, "a" * 32)

    def test_settings_refuses_placeholder_secret_key(self):
        placeholders = (
            "change_me_generate_on_the_instance",
            "CHANGE_ME_GENERATE_ON_THE_INSTANCE",
            "change-me-generate-on-the-instance",
            "your-secret-key-here-use-openssl-rand-hex-32",
            "replace-with-at-least-32-random-characters",
        )
        for placeholder in placeholders:
            with self.subTest(placeholder=placeholder):
                with self.assertRaises(ValidationError):
                    Settings(
                        APP_ENV="prod",
                        NEO4J_PASSWORD=VALID_AUTH,
                        SECRET_KEY=placeholder,
                    )

    def test_settings_refuses_short_secret_key(self):
        with self.assertRaises(ValidationError):
            Settings(
                APP_ENV="prod",
                NEO4J_PASSWORD=VALID_AUTH,
                SECRET_KEY="x" * 16,
            )

    def test_settings_refuses_placeholder_neo4j_password(self):
        placeholders = (
            "change_me_generate_on_the_instance",
            "CHANGE_ME_GENERATE_ON_THE_INSTANCE",
            "change-me-generate-on-the-instance",
            "your-neo4j-password-here",
            "replace-with-a-private-password",
        )
        for placeholder in placeholders:
            with self.subTest(placeholder=placeholder):
                with self.assertRaises(ValidationError):
                    Settings(
                        APP_ENV="prod",
                        NEO4J_PASSWORD=placeholder,
                        SECRET_KEY="a" * 32,
                    )

    def test_settings_refuses_short_neo4j_password(self):
        with self.assertRaises(ValidationError):
            Settings(
                APP_ENV="prod",
                NEO4J_PASSWORD="x" * 4,
                SECRET_KEY="a" * 32,
            )

    def test_settings_rejects_test_secret_outside_test_env(self):
        with self.assertRaises(ValidationError):
            Settings(
                APP_ENV="prod",
                NEO4J_PASSWORD=VALID_AUTH,
                SECRET_KEY=EXPLICIT_TEST_SECRET,
            )


if __name__ == "__main__":
    unittest.main()
