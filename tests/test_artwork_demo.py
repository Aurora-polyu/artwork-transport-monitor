from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest


class ArtworkDemoTests(unittest.TestCase):
    def test_artwork_demo_is_deterministic_and_software_only(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-m", "artwork_monitor", "--artwork-demo"],
            cwd=project_root,
            env={**os.environ, "PYTHONPATH": str(project_root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "software-only artwork workflow demo\n"
            "transition: Venus de Milo -> in\n"
            "transition: The Starry Night -> in\n"
            "final: Venus de Milo: in\n"
            "final: The Starry Night: in\n",
        )
