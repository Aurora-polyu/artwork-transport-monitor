from __future__ import annotations

from datetime import datetime
import unittest

from artwork_monitor.adapters.simulated import (
    PassthroughImagePreprocessor,
    SequenceCameraSource,
    SequenceDetector,
)
from artwork_monitor.application import ArtworkWorkflow
from artwork_monitor.domain import ArtworkStatus, HONG_KONG, InferenceResult
from artwork_monitor.ports import CameraFrame


def workflow_for(
    frame_count: int,
    results: tuple[InferenceResult | None, ...],
) -> ArtworkWorkflow:
    return ArtworkWorkflow(
        camera_source=SequenceCameraSource(
            CameraFrame(f"frame-{number}") for number in range(frame_count)
        ),
        preprocessor=PassthroughImagePreprocessor(),
        detector=SequenceDetector(results),
        clock=lambda: datetime(2026, 8, 9, 10, 30, tzinfo=HONG_KONG),
    )


class ArtworkWorkflowTests(unittest.TestCase):
    def test_first_accepted_detection_toggles_once_per_session(self) -> None:
        workflow = workflow_for(
            10, (InferenceResult(0, 0.99), InferenceResult(0, 0.99))
        )

        workflow.start()
        steps = workflow.run_to_exhaustion()

        transitions = [step.transition for step in steps if step.transition is not None]
        self.assertEqual(len(transitions), 1)
        assert transitions[0] is not None
        self.assertEqual(transitions[0].label_index, 0)
        self.assertEqual(transitions[0].status, ArtworkStatus.IN)
        self.assertEqual(
            workflow.states()[0].time_in, datetime(2026, 8, 9, 10, 30, tzinfo=HONG_KONG)
        )

    def test_new_session_allows_the_artwork_to_toggle_again(self) -> None:
        workflow = workflow_for(
            10, (InferenceResult(1, 0.99), InferenceResult(1, 0.99))
        )

        workflow.start()
        for _ in range(5):
            workflow.process_next_frame()
        workflow.stop()
        workflow.start()
        for _ in range(5):
            workflow.process_next_frame()

        self.assertEqual(workflow.states()[1].status, ArtworkStatus.OUT)
        self.assertEqual(
            workflow.states()[1].time_out,
            datetime(2026, 8, 9, 10, 30, tzinfo=HONG_KONG),
        )

    def test_starting_again_while_active_resets_duplicate_suppression(self) -> None:
        workflow = workflow_for(
            10, (InferenceResult(0, 0.99), InferenceResult(0, 0.99))
        )

        workflow.start()
        for _ in range(5):
            workflow.process_next_frame()
        workflow.start()
        workflow.run_to_exhaustion()

        self.assertEqual(workflow.states()[0].status, ArtworkStatus.OUT)

    def test_unknown_none_and_inactive_detection_do_not_change_artwork_state(
        self,
    ) -> None:
        workflow = workflow_for(
            25,
            (
                None,
                InferenceResult(2, 1.0),
                InferenceResult(99, 1.0),
                InferenceResult(0, 0.94),
            ),
        )

        for _ in range(5):
            workflow.process_next_frame()
        workflow.start()
        workflow.run_to_exhaustion()

        self.assertTrue(
            all(
                state.status is ArtworkStatus.OUT
                for state in workflow.states().values()
            )
        )

    def test_separate_workflows_do_not_share_artwork_state(self) -> None:
        changed = workflow_for(5, (InferenceResult(0, 0.99),))
        untouched = workflow_for(0, ())

        changed.start()
        changed.run_to_exhaustion()

        self.assertEqual(changed.states()[0].status, ArtworkStatus.IN)
        self.assertEqual(untouched.states()[0].status, ArtworkStatus.OUT)
