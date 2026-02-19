import asyncio
import time
import uuid
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


STALE_JOB_TIMEOUT = 30.0  # seconds before an IN_PROGRESS job is considered stale
JOB_TTL = 300.0  # seconds to keep completed/failed jobs before cleanup


class Job:
    def __init__(self, ops: list[dict]) -> None:
        self.id = str(uuid.uuid4())
        self.ops = ops
        self.status = JobStatus.PENDING
        self.created_at = time.time()
        self.dispatched_at: float | None = None
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


class ScreenshotRequest:
    def __init__(self, node_id: str = "", scale: float = 1.0) -> None:
        self.id = str(uuid.uuid4())
        self.node_id = node_id
        self.scale = scale
        self.base64: str | None = None
        self.error: str | None = None
        self.event = asyncio.Event()


class JobQueue:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._pending_read: ReadRequest | None = None
        self._pending_screenshot: ScreenshotRequest | None = None
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
                job.dispatched_at = time.time()
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

    def reap_stale_jobs(self) -> list[str]:
        """Reset IN_PROGRESS jobs that have been dispatched longer than
        STALE_JOB_TIMEOUT back to FAILED. Returns IDs of reaped jobs."""
        now = time.time()
        reaped: list[str] = []
        for job in self._jobs.values():
            if (
                job.status == JobStatus.IN_PROGRESS
                and job.dispatched_at is not None
                and (now - job.dispatched_at) > STALE_JOB_TIMEOUT
            ):
                job.status = JobStatus.FAILED
                job.error = f"Timed out: plugin did not respond within {int(STALE_JOB_TIMEOUT)}s"
                job.done_event.set()
                reaped.append(job.id)
        return reaped

    def cleanup_old_jobs(self) -> int:
        """Remove completed/failed jobs older than JOB_TTL. Returns count removed."""
        now = time.time()
        to_remove = [
            jid
            for jid, job in self._jobs.items()
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED)
            and (now - job.created_at) > JOB_TTL
        ]
        for jid in to_remove:
            del self._jobs[jid]
        return len(to_remove)

    def has_pending_read(self) -> bool:
        """True if a read request is currently in-flight."""
        return self._pending_read is not None

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

    def has_pending_screenshot(self) -> bool:
        return self._pending_screenshot is not None

    def create_screenshot_request(self, node_id: str = "", scale: float = 1.0) -> ScreenshotRequest:
        req = ScreenshotRequest(node_id, scale)
        self._pending_screenshot = req
        return req

    def get_pending_screenshot(self) -> ScreenshotRequest | None:
        return self._pending_screenshot

    def fulfill_screenshot_request(self, req_id: str, base64_data: str) -> bool:
        req = self._pending_screenshot
        if not req or req.id != req_id:
            return False
        req.base64 = base64_data
        req.event.set()
        self._pending_screenshot = None
        return True

    def fail_screenshot_request(self, req_id: str, error: str) -> bool:
        req = self._pending_screenshot
        if not req or req.id != req_id:
            return False
        req.error = error
        req.event.set()
        self._pending_screenshot = None
        return True
