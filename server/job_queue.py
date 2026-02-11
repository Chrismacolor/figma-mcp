import asyncio
import time
import uuid
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Job:
    def __init__(self, ops: list[dict]) -> None:
        self.id = str(uuid.uuid4())
        self.ops = ops
        self.status = JobStatus.PENDING
        self.created_at = time.time()
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.done_event = asyncio.Event()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "createdAt": self.created_at,
            "result": self.result,
            "error": self.error,
        }

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "opCount": len(self.ops),
            "createdAt": self.created_at,
            "error": self.error,
        }


class ReadRequest:
    def __init__(self, depth: int = 2) -> None:
        self.id = str(uuid.uuid4())
        self.depth = depth
        self.response: dict | None = None
        self.event = asyncio.Event()


class JobQueue:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._pending_read: ReadRequest | None = None
        self.last_plugin_poll: float = 0.0

    def plugin_connected(self) -> bool:
        """True if plugin polled within the last 10 seconds."""
        return (time.time() - self.last_plugin_poll) < 10.0

    def record_poll(self) -> None:
        self.last_plugin_poll = time.time()

    def create_job(self, ops: list[dict]) -> Job:
        job = Job(ops)
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        return [j.to_summary() for j in self._jobs.values()]

    def next_pending(self) -> Job | None:
        for job in self._jobs.values():
            if job.status == JobStatus.PENDING:
                job.status = JobStatus.IN_PROGRESS
                return job
        return None

    def complete_job(self, job_id: str, result: dict) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.status != JobStatus.IN_PROGRESS:
            return False
        job.status = JobStatus.COMPLETED
        job.result = result
        job.done_event.set()
        return True

    def fail_job(self, job_id: str, error: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.status != JobStatus.IN_PROGRESS:
            return False
        job.status = JobStatus.FAILED
        job.error = error
        job.done_event.set()
        return True

    def create_read_request(self, depth: int = 2) -> ReadRequest:
        req = ReadRequest(depth)
        self._pending_read = req
        return req

    def get_pending_read(self) -> ReadRequest | None:
        return self._pending_read

    def fulfill_read_request(self, req_id: str, data: dict) -> bool:
        req = self._pending_read
        if not req or req.id != req_id:
            return False
        req.response = data
        req.event.set()
        self._pending_read = None
        return True
