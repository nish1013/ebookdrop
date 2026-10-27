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
    worker = Worker(jobs, RecordingRemovals(), clock)
    checks = []

    for step in (0, 30, 30, 59, 1):
        clock.advance(timedelta(seconds=step))
        worker.tick()
        checks.append(jobs.stuck_checks)

    assert checks == [1, 1, 2, 2, 3]


class RecordingRemovals:
    def __init__(self) -> None:
        self.polls = 0
        self.cleanups = 0
        self.sweeps = 0

    def poll(self) -> int:
        self.polls += 1
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
    worker = Worker(RecordingJobs(), removals, clock)
    runs = []

    for step in (timedelta(0), timedelta(hours=23), timedelta(hours=1), timedelta(0)):
        clock.advance(step)
        worker.tick()
        runs.append((removals.polls, removals.cleanups, removals.sweeps))

    assert runs == [(1, 1, 1), (2, 1, 1), (3, 2, 2), (4, 2, 2)]
