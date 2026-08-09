from __future__ import annotations

import math
import unittest

from artwork_monitor.domain import (
    ArtworkStatus,
    InferenceResult,
    interpret_detection,
    legacy_artworks,
)


class ArtworkDomainTests(unittest.TestCase):
    def test_known_legacy_artwork_is_accepted_at_threshold(self) -> None:
        detection = interpret_detection(InferenceResult(label_index=0, confidence=0.95))

        assert detection is not None
        self.assertEqual(detection.identity.name, "Venus de Milo")
        self.assertEqual(detection.identity.lot, "Lot 2")
        self.assertEqual(detection.identity.label_index, 0)

    def test_unknown_none_and_low_confidence_results_are_not_accepted(self) -> None:
        self.assertIsNone(interpret_detection(None))
        self.assertIsNone(interpret_detection(InferenceResult(label_index=2, confidence=1.0)))
        self.assertIsNone(interpret_detection(InferenceResult(label_index=99, confidence=1.0)))
        self.assertIsNone(interpret_detection(InferenceResult(label_index=1, confidence=0.949)))

    def test_legacy_artworks_start_out(self) -> None:
        states = legacy_artworks()

        self.assertEqual({label: state.status for label, state in states.items()}, {
            0: ArtworkStatus.OUT,
            1: ArtworkStatus.OUT,
        })
        self.assertIsNone(states[0].time_in)
        self.assertIsNone(states[1].time_out)

    def test_invalid_inference_data_is_rejected(self) -> None:
        for label_index, confidence in ((True, 0.95), ("0", 0.95), (0, math.nan), (0, math.inf)):
            with self.subTest(label_index=label_index, confidence=confidence):
                with self.assertRaises(ValueError):
                    InferenceResult(label_index=label_index, confidence=confidence)
