import asyncio

from pydantic import ValidationError

from .job_queue import JobQueue
from .ops_schema import serialize_ops, validate_ops


def register_tools(mcp, queue: JobQueue) -> None:

    @mcp.tool()
    async def enqueue_ops(ops: list[dict]) -> str:
        """Enqueue a batch of Figma design operations for the plugin to execute.

        Each op must have an "op" field (CREATE_FRAME, CREATE_RECTANGLE, CREATE_ELLIPSE,
        or CREATE_TEXT) and a unique "tempId" string.

        Parent referencing (two options, use one per op):
        - "parentTempId": reference a tempId declared earlier IN THIS BATCH
        - "parentNodeId": reference a real Figma node ID (e.g. "16:2") from a previous
          job's result tempIdMap — use this to add children to existing nodes across batches

        Common fields: tempId, parentTempId, parentNodeId, name, x, y, fills [{r,g,b,a}].
        Frame fields: w, h, cornerRadius, layoutMode (NONE/HORIZONTAL/VERTICAL),
                      itemSpacing, paddingLeft/Right/Top/Bottom,
                      primaryAxisAlignItems, counterAxisAlignItems, clipsContent.
        Rectangle fields: w, h, cornerRadius, opacity.
        Ellipse fields: w, h, opacity.
        Text fields: text, fontSize, fontFamily, fontWeight (string like "Bold" or
                     numeric like 700), textAlignHorizontal,
                     textAutoResize, w, h, lineHeight, letterSpacing, opacity.

        Returns the job ID on success, or a validation error message.
        """
        try:
            batch = validate_ops(ops)
        except (ValidationError, ValueError) as e:
            return f"Validation error: {e}"

        serialized = serialize_ops(batch)
        job = queue.create_job(serialized)
        return f"Job created: {job.id} ({len(serialized)} ops)"

    @mcp.tool()
    async def get_job_status(job_id: str) -> str:
        """Get the status of a previously enqueued job.

        Returns job status (pending, in_progress, completed, failed),
        result data including tempId-to-nodeId mappings, or error message.
        """
        job = queue.get_job(job_id)
        if job is None:
            return f"Job not found: {job_id}"
        return str(job.to_dict())

    @mcp.tool()
    async def list_jobs() -> str:
        """List all jobs and their statuses."""
        jobs = queue.list_jobs()
        if not jobs:
            return "No jobs."
        return str(jobs)

    @mcp.tool()
    async def read_node_tree(depth: int = 2) -> str:
        """Read the current Figma page's node tree.

        Requests the plugin to serialize the current page structure up to the
        specified depth. Waits up to 30 seconds for the plugin to respond.

        Returns node tree with id, name, type, x, y, width, height, and children.
        """
        req = queue.create_read_request(depth)

        try:
            await asyncio.wait_for(req.event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            return "Timeout: plugin did not respond within 30 seconds. Is the Figma plugin connected?"

        return str(req.response)
