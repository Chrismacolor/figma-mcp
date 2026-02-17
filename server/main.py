import asyncio
import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from .auth import init_auth_token
from .http_routes import init_routes
from .job_queue import JobQueue
from .mcp_tools import register_tools

HTTP_PORT = int(os.environ.get("FIGMA_MCP_PORT", "8400"))


def create_app() -> tuple[FastMCP, FastAPI, JobQueue]:
    queue = JobQueue()

    # MCP server (stdio)
    mcp = FastMCP("figma-mcp", instructions=(
        "You are a Figma design assistant. Use enqueue_ops to create designs in Figma. "
        "Each op needs a unique tempId. Use parentTempId to nest elements. "
        "After enqueuing, use get_job_status to check if the plugin executed the ops. "
        "Use read_node_tree to see what's currently on the Figma canvas."
    ))
    register_tools(mcp, queue)

    # FastAPI app (HTTP for plugin polling)
    api = FastAPI(title="figma-mcp-bridge")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_router = init_routes(queue)
    api.include_router(api_router)

    @api.get("/health")
    async def health():
        return {"status": "ok"}

    return mcp, api, queue


async def _reaper_loop(queue: JobQueue):
    """Periodically reap stale jobs and clean up old completed/failed jobs."""
    while True:
        await asyncio.sleep(10)
        reaped = queue.reap_stale_jobs()
        if reaped:
            print(f"Reaped {len(reaped)} stale job(s): {reaped}", file=sys.stderr)
        cleaned = queue.cleanup_old_jobs()
        if cleaned:
            print(f"Cleaned up {cleaned} old job(s)", file=sys.stderr)


async def run_async():
    mcp, api, queue = create_app()

    init_auth_token()

    config = uvicorn.Config(
        api,
        host="127.0.0.1",
        port=HTTP_PORT,
        log_level="warning",
    )
    http_server = uvicorn.Server(config)

    print(f"HTTP bridge listening on http://127.0.0.1:{HTTP_PORT}", file=sys.stderr)
    print("MCP server ready on stdio", file=sys.stderr)

    await asyncio.gather(
        mcp.run_async(transport="stdio"),
        http_server.serve(),
        _reaper_loop(queue),
    )


def main():
    asyncio.run(run_async())


if __name__ == "__main__":
    main()
