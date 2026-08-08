import subprocess
import sys
import unittest
from pathlib import Path


class ImportTests(unittest.TestCase):
    def test_package_import_is_hardware_independent_and_side_effect_free(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-c", "import artwork_monitor; print(artwork_monitor.__version__)"],
            cwd=project_root,
            env={"PYTHONPATH": str(project_root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "0.1.0")
