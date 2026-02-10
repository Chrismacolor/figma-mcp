from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from .auth import require_auth
from .job_queue import JobQueue

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

_queue: JobQueue | None = None


def init_routes(queue: JobQueue) -> APIRouter:
    global _queue
    _queue = queue
    return router


class CompleteBody(BaseModel):
    result: dict


class ErrorBody(BaseModel):
    error: str


class ReadResponseBody(BaseModel):
    data: dict


@router.get("/jobs/next")
async def get_next_job():
    assert _queue is not None
    job = _queue.next_pending()
    if job is None:
        return Response(status_code=204)
    return {"id": job.id, "ops": job.ops}


@router.post("/jobs/{job_id}/complete")
async def complete_job(job_id: str, body: CompleteBody):
    assert _queue is not None
    if _queue.complete_job(job_id, body.result):
        return {"ok": True}
    return Response(status_code=404, content='{"error": "job not found or not in_progress"}')


@router.post("/jobs/{job_id}/error")
async def error_job(job_id: str, body: ErrorBody):
    assert _queue is not None
    if _queue.fail_job(job_id, body.error):
        return {"ok": True}
    return Response(status_code=404, content='{"error": "job not found or not in_progress"}')


@router.get("/read-request")
async def get_read_request():
    assert _queue is not None
    req = _queue.get_pending_read()
    if req is None:
        return Response(status_code=204)
    return {"id": req.id, "depth": req.depth}


@router.post("/read-request/{req_id}/response")
async def submit_read_response(req_id: str, body: ReadResponseBody):
    assert _queue is not None
    if _queue.fulfill_read_request(req_id, body.data):
        return {"ok": True}
    return Response(status_code=404, content='{"error": "read request not found"}')
