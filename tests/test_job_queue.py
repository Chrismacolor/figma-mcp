import asyncio
import time

from server.job_queue import (
    JOB_TTL,
    STALE_JOB_TIMEOUT,
    JobQueue,
    JobStatus,
)


class TestCreateAndGet:
    def test_create_job_returns_pending(self):
        q = JobQueue()
        job = q.create_job([{"op": "CREATE_FRAME", "tempId": "f1"}])
        assert job.status == JobStatus.PENDING
        assert len(job.id) == 36  # UUID format

    def test_get_job_found(self):
        q = JobQueue()
        job = q.create_job([])
        assert q.get_job(job.id) is job

    def test_get_job_not_found(self):
        q = JobQueue()
        assert q.get_job("nonexistent") is None


class TestListJobs:
    def test_empty(self):
        q = JobQueue()
        assert q.list_jobs() == []

    def test_populated(self):
        q = JobQueue()
        q.create_job([])
        q.create_job([])
        summaries = q.list_jobs()
        assert len(summaries) == 2
        assert all("id" in s and "status" in s for s in summaries)


class TestNextPending:
    def test_transitions_to_in_progress(self):
        q = JobQueue()
        job = q.create_job([])
        fetched = q.next_pending()
        assert fetched is job
        assert fetched.status == JobStatus.IN_PROGRESS
        assert fetched.dispatched_at is not None

    def test_returns_none_when_empty(self):
        q = JobQueue()
        assert q.next_pending() is None

    def test_skips_in_progress(self):
        q = JobQueue()
        q.create_job([])
        q.next_pending()  # transitions first job to IN_PROGRESS
        assert q.next_pending() is None


class TestCompleteJob:
    def test_success(self):
        q = JobQueue()
        job = q.create_job([])
        q.next_pending()
        assert q.complete_job(job.id, {"nodes": []})
        assert job.status == JobStatus.COMPLETED
        assert job.result == {"nodes": []}
        assert job.done_event.is_set()

    def test_wrong_status(self):
        q = JobQueue()
        job = q.create_job([])
        # Job is still PENDING, not IN_PROGRESS
        assert q.complete_job(job.id, {}) is False


class TestFailJob:
    def test_success(self):
        q = JobQueue()
        job = q.create_job([])
        q.next_pending()
        assert q.fail_job(job.id, "something broke")
        assert job.status == JobStatus.FAILED
        assert job.error == "something broke"
        assert job.done_event.is_set()

    def test_wrong_status(self):
        q = JobQueue()
        job = q.create_job([])
        assert q.fail_job(job.id, "err") is False


class TestDoneEvent:
    async def test_event_fires_on_complete(self):
        q = JobQueue()
        job = q.create_job([])
        q.next_pending()

        async def completer():
            await asyncio.sleep(0.05)
            q.complete_job(job.id, {"ok": True})

        task = asyncio.create_task(completer())
        await asyncio.wait_for(job.done_event.wait(), timeout=2.0)
        assert job.done_event.is_set()
        await task


class TestReapStaleJobs:
    def test_reaps_old_in_progress(self):
        q = JobQueue()
        job = q.create_job([])
        q.next_pending()
        # Simulate stale dispatch
        job.dispatched_at = time.time() - STALE_JOB_TIMEOUT - 1
        reaped = q.reap_stale_jobs()
        assert job.id in reaped
        assert job.status == JobStatus.FAILED
        assert "Timed out" in job.error


class TestCleanupOldJobs:
    def test_removes_old_completed(self):
        q = JobQueue()
        job = q.create_job([])
        q.next_pending()
        q.complete_job(job.id, {})
        # Simulate old creation time
        job.created_at = time.time() - JOB_TTL - 1
        removed = q.cleanup_old_jobs()
        assert removed == 1
        assert q.get_job(job.id) is None


class TestPluginConnected:
    def test_initially_disconnected(self):
        q = JobQueue()
        assert q.plugin_connected() is False

    def test_connected_after_poll(self):
        q = JobQueue()
        q.record_poll()
        assert q.plugin_connected() is True

    def test_disconnected_after_timeout(self):
        q = JobQueue()
        q.last_plugin_poll = time.time() - 11
        assert q.plugin_connected() is False


class TestReadRequest:
    def test_lifecycle(self):
        q = JobQueue()
        req = q.create_read_request(depth=3)
        assert q.get_pending_read() is req
        assert req.depth == 3

        assert q.fulfill_read_request(req.id, {"tree": "data"})
        assert req.response == {"tree": "data"}
        assert req.event.is_set()
        assert q.get_pending_read() is None

    def test_wrong_id(self):
        q = JobQueue()
        q.create_read_request()
        assert q.fulfill_read_request("wrong-id", {}) is False


class TestScreenshotRequest:
    def test_fulfill_lifecycle(self):
        q = JobQueue()
        req = q.create_screenshot_request(node_id="1:2", scale=2.0)
        assert q.get_pending_screenshot() is req

        assert q.fulfill_screenshot_request(req.id, "base64data==")
        assert req.base64 == "base64data=="
        assert req.event.is_set()
        assert q.get_pending_screenshot() is None

    def test_fail_lifecycle(self):
        q = JobQueue()
        req = q.create_screenshot_request()
        assert q.fail_screenshot_request(req.id, "render error")
        assert req.error == "render error"
        assert req.event.is_set()
        assert q.get_pending_screenshot() is None

    def test_wrong_id_fulfill(self):
        q = JobQueue()
        q.create_screenshot_request()
        assert q.fulfill_screenshot_request("wrong", "data") is False

    def test_wrong_id_fail(self):
        q = JobQueue()
        q.create_screenshot_request()
        assert q.fail_screenshot_request("wrong", "err") is False
