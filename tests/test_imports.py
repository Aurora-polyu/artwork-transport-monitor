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

    def test_software_only_artwork_workflow_imports_without_optional_runtime_modules(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        blocked_imports = "cv2,tflite_runtime,picamera,RPi,socket"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import builtins; original = builtins.__import__; blocked = set(" + repr(blocked_imports.split(",")) + "); "
                "builtins.__import__ = lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError(name)) "
                "if name.split('.')[0] in blocked else original(name, *args, **kwargs); "
                "import threading; before = threading.active_count(); "
                "from artwork_monitor.adapters.simulated import PassthroughImagePreprocessor, SequenceCameraSource, SequenceDetector; "
                "from artwork_monitor.application import ArtworkWorkflow; "
                "from artwork_monitor.domain import InferenceResult; "
                "from artwork_monitor.ports import CameraFrame; "
                "workflow = ArtworkWorkflow(camera_source=SequenceCameraSource([CameraFrame('one')] * 5), "
                "preprocessor=PassthroughImagePreprocessor(), detector=SequenceDetector([InferenceResult(0, 0.99)])); "
                "workflow.start(); workflow.run_to_exhaustion(); "
                "assert threading.active_count() == before; print('ok')",
            ],
            cwd=project_root,
            env={"PYTHONPATH": str(project_root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ok")
