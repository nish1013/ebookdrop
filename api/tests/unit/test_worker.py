from datetime import timedelta

from ebookdrop.worker import Worker
from tests.conftest import FakeClock


class RecordingJobs:
    def __init__(self) -> None:
        self.stuck_checks = 0

    def poll(self) -> int:
        return 0

    def fail_stuck(self) -> int:
        self.stuck_checks += 1
        return 0


def test_p2_runs_once_a_minute_in_the_worker() -> None:
    clock = FakeClock()
    jobs = RecordingJobs()
    worker = Worker(jobs, RecordingRemovals(), RecordingLibraries(), clock)
    checks = []

    for step in (0, 30, 30, 59, 1):
        clock.advance(timedelta(seconds=step))
        worker.tick()
        checks.append(jobs.stuck_checks)

    assert checks == [1, 1, 2, 2, 3]


class RecordingRemovals:
    def __init__(self, steps: list[str] | None = None) -> None:
        self.polls = 0
        self.cleanups = 0
        self.sweeps = 0
        self.steps = [] if steps is None else steps

    def poll(self) -> int:
        self.polls += 1
        self.steps.append("p4")
        return 0

    def clean_failed(self) -> int:
        self.cleanups += 1
        return 0

    def sweep_staging(self) -> int:
        self.sweeps += 1
        return 0


def test_p4_runs_on_each_tick_and_p5_with_the_staging_sweep_once_a_day() -> None:
    clock = FakeClock()
    removals = RecordingRemovals()
    worker = Worker(RecordingJobs(), removals, RecordingLibraries(), clock)
    runs = []

    for step in (timedelta(0), timedelta(hours=23), timedelta(hours=1), timedelta(0)):
        clock.advance(step)
        worker.tick()
        runs.append((removals.polls, removals.cleanups, removals.sweeps))

    assert runs == [(1, 1, 1), (2, 1, 1), (3, 2, 2), (4, 2, 2)]


class BrokenCleanupRemovals(RecordingRemovals):
    def clean_failed(self) -> int:
        raise OSError("disk busy")


def test_a_failed_p5_leaves_the_staging_sweep_and_the_polls_running() -> None:
    removals = BrokenCleanupRemovals()
    worker = Worker(RecordingJobs(), removals, RecordingLibraries(), FakeClock())

    worker.tick()

    assert (removals.sweeps, removals.polls) == (1, 1)


class RecordingLibraries:
    def __init__(self, steps: list[str] | None = None) -> None:
        self.steps = [] if steps is None else steps

    def poll(self) -> int:
        self.steps.append("p6")
        return 1


def test_p6_runs_on_each_tick_before_p4_and_counts_as_taken() -> None:
    steps: list[str] = []
    worker = Worker(
        RecordingJobs(),
        RecordingRemovals(steps),
        RecordingLibraries(steps),
        FakeClock(),
    )

    taken = [worker.tick(), worker.tick()]

    assert steps == ["p6", "p4", "p6", "p4"]
    assert taken == [1, 1]
