from __future__ import annotations

import unittest

from artwork_monitor.adapters.simulated import (
    PassthroughImagePreprocessor,
    SequenceCameraSource,
    SequenceDetector,
)
from artwork_monitor.domain import InferenceResult
from artwork_monitor.ports import CameraFrame


class ArtworkAdapterTests(unittest.TestCase):
    def test_scripted_camera_and_detector_are_finite_and_resettable(self) -> None:
        source = SequenceCameraSource((CameraFrame("first"), CameraFrame("second")))
        detector = SequenceDetector((InferenceResult(0, 0.99), None))
        preprocessor = PassthroughImagePreprocessor()

        first = source.next_frame()
        assert first is not None
        self.assertEqual(first.frame_id, "first")
        self.assertEqual(preprocessor.prepare(first).frame_id, "first")
        self.assertEqual(
            detector.infer(preprocessor.prepare(first)), InferenceResult(0, 0.99)
        )
        self.assertIsNone(detector.infer(preprocessor.prepare(first)))
        self.assertIsNone(detector.infer(preprocessor.prepare(first)))
        self.assertIsNotNone(source.next_frame())
        self.assertIsNone(source.next_frame())

        source.reset()
        detector.reset()

        self.assertEqual(source.next_frame(), CameraFrame("first"))
        self.assertEqual(
            detector.infer(preprocessor.prepare(first)), InferenceResult(0, 0.99)
        )

    def test_camera_frame_identifier_must_not_be_empty(self) -> None:
        with self.assertRaises(ValueError):
            CameraFrame("")
