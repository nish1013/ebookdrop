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
    worker = Worker(jobs, clock)
    checks = []

    for step in (0, 30, 30, 59, 1):
        clock.advance(timedelta(seconds=step))
        worker.tick()
        checks.append(jobs.stuck_checks)

    assert checks == [1, 1, 2, 2, 3]
