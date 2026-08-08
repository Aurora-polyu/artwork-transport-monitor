import os
import unittest
from pathlib import Path

from artwork_monitor import RuntimeProfile, Settings


class SettingsTests(unittest.TestCase):
    def test_all_runtime_profiles_parse(self) -> None:
        for profile in ("test", "demo", "hardware", "full-team"):
            with self.subTest(profile=profile):
                self.assertEqual(
                    Settings.from_env({"ARTWORK_MONITOR_PROFILE": profile}).profile.value,
                    profile,
                )

    def test_environment_overrides_safe_defaults(self) -> None:
        project_root = Path(self._get_temp_dir()) / "project"
        settings = Settings.from_env(
            {
                "ARTWORK_MONITOR_PROFILE": "full_team",
                "ARTWORK_MONITOR_PROJECT_ROOT": str(project_root),
                "ARTWORK_MONITOR_RUNTIME_DIR": "runtime",
                "ARTWORK_MONITOR_DATABASE_PATH": "state.sqlite3",
                "ARTWORK_MONITOR_LOG_DIR": "csv",
                "ARTWORK_MONITOR_HOST": "0.0.0.0",
                "ARTWORK_MONITOR_PORT": "8123",
                "ARTWORK_MONITOR_FLASK_SECRET": "configured-by-test",
                "ARTWORK_MONITOR_EMAIL_HOST": "mail.example.invalid",
                "ARTWORK_MONITOR_EMAIL_PORT": "2525",
            }
        )

        self.assertIs(settings.profile, RuntimeProfile.FULL_TEAM)
        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 8123)
        self.assertEqual(settings.flask_secret_key, "configured-by-test")
        self.assertEqual(settings.email_host, "mail.example.invalid")
        self.assertEqual(settings.email_port, 2525)
        self.assertEqual(settings.runtime_dir, (project_root / "runtime").resolve())
        self.assertEqual(settings.database_path, (project_root / "runtime" / "state.sqlite3").resolve())
        self.assertEqual(settings.log_dir, (project_root / "runtime" / "csv").resolve())

    def test_default_paths_are_project_relative_not_cwd(self) -> None:
        original_cwd = Path.cwd()
        temporary_cwd = Path(self._get_temp_dir())
        try:
            os.chdir(temporary_cwd)
            settings = Settings.from_env({"ARTWORK_MONITOR_PROFILE": "test"})
        finally:
            os.chdir(original_cwd)

        self.assertEqual(settings.runtime_dir, settings.project_root / "instance")
        self.assertEqual(settings.database_path, settings.runtime_dir / "artwork_monitor.sqlite3")
        self.assertEqual(settings.log_dir, settings.runtime_dir / "transport_logs")
        self.assertNotEqual(settings.project_root, temporary_cwd.resolve())

    def _get_temp_dir(self) -> str:
        import tempfile

        return tempfile.mkdtemp()
