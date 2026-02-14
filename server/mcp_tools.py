import asyncio

from pydantic import ValidationError

from .job_queue import JobQueue
from .ops_schema import serialize_ops, validate_ops


def register_tools(mcp, queue: JobQueue) -> None:

    def _plugin_warning() -> str:
        if not queue.plugin_connected():
            return " WARNING: Figma plugin has not polled recently — it may be disconnected."
        return ""

    @mcp.tool()
    async def enqueue_ops(ops: list[dict]) -> str:
        """Enqueue a batch of Figma design operations for the plugin to execute.

        Each op must have an "op" field and a unique "tempId" string.

        Op types: CREATE_FRAME, CREATE_RECTANGLE, CREATE_ELLIPSE, CREATE_TEXT,
                  UPDATE_NODE, DELETE_NODE.

        Parent referencing (two options, use one per op):
        - "parentTempId": reference a tempId declared earlier IN THIS BATCH
        - "parentNodeId": reference a real Figma node ID (e.g. "16:2") from a previous
          job's result tempIdMap — use this to add children to existing nodes across batches

        Common fields: tempId, parentTempId, parentNodeId, name, x, y,
                      fills [{r,g,b,a}], stroke {r,g,b,a,weight,align}, opacity.
        Frame fields: w, h, cornerRadius, layoutMode (NONE/HORIZONTAL/VERTICAL),
                      itemSpacing, paddingLeft/Right/Top/Bottom,
                      primaryAxisAlignItems, counterAxisAlignItems, clipsContent,
                      dropShadow {color{r,g,b,a}, offset{x,y}, radius}.
        Rectangle fields: w, h, cornerRadius.
        Ellipse fields: w, h.
        Text fields: text, fontSize, fontFamily, fontWeight (string like "Bold" or
                     numeric like 700), textAlignHorizontal,
                     textAutoResize, w, h, lineHeight, letterSpacing.
        UPDATE_NODE fields: nodeId (required), plus any property to change (name, x, y,
                     w, h, fills, opacity, text, fontSize, etc.)
        DELETE_NODE fields: nodeId (required) — removes the node from the canvas.

        Returns the job ID. Use get_job_status to wait for the result.
        """
        try:
            batch = validate_ops(ops)
        except (ValidationError, ValueError) as e:
            return f"Validation error: {e}"

        serialized = serialize_ops(batch)
        job = queue.create_job(serialized)
        return f"Job created: {job.id} ({len(serialized)} ops).{_plugin_warning()}"

    @mcp.tool()
    async def get_job_status(job_id: str, wait: int = 15) -> str:
        """Get the status of a previously enqueued job.

        Waits up to `wait` seconds (default 15) for a pending/in_progress job to
        finish before returning. Returns job status, tempId-to-nodeId mappings
        on success, or error message on failure.
        """
        job = queue.get_job(job_id)
        if job is None:
            return f"Job not found: {job_id}"

        if job.status.value in ("pending", "in_progress") and wait > 0:
            try:
                await asyncio.wait_for(job.done_event.wait(), timeout=float(wait))
            except asyncio.TimeoutError:
                pass

        info = job.to_dict()
        msg = str(info)
        if not queue.plugin_connected() and job.status.value in ("pending", "in_progress"):
            msg += " WARNING: Plugin not connected — job may be stuck."
        return msg

    @mcp.tool()
    async def list_jobs() -> str:
        """List all jobs and their statuses."""
        jobs = queue.list_jobs()
        if not jobs:
            return "No jobs."
        connected = queue.plugin_connected()
        result = str(jobs)
        if not connected:
            result += " WARNING: Plugin not connected."
        return result

    MAX_TREE_CHARS = 50000

    @mcp.tool()
    async def read_node_tree(depth: int = 3) -> str:
        """Read the current Figma page's node tree.

        Returns node tree with id, name, type, x, y, width, height, fills,
        opacity, cornerRadius, text content, fontSize, fontWeight, and children
        up to the specified depth (default 3).

        Response is capped at ~50K chars. Use lower depth for large pages.
        Waits up to 30 seconds for the plugin to respond.
        """
        if not queue.plugin_connected():
            return "Plugin not connected. Open the Figma plugin and click Connect."

        req = queue.create_read_request(depth)

        try:
            await asyncio.wait_for(req.event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            return "Timeout: plugin did not respond within 30 seconds. Is the Figma plugin connected?"

        result = str(req.response)
        if len(result) > MAX_TREE_CHARS:
            return result[:MAX_TREE_CHARS] + f"\n... TRUNCATED (total {len(result)} chars). Use lower depth to see full tree."
        return result
