import os
import socket
import sys
import threading
import time

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from .auth import init_auth_token
from .http_routes import init_routes
from .job_queue import JobQueue
from .mcp_tools import register_tools

HTTP_PORT = int(os.environ.get("FIGMA_MCP_PORT", "8400"))


def _create_mcp(queue: JobQueue) -> FastMCP:
    mcp = FastMCP("figma-mcp-companion", instructions=(
        "You are Figma MCP Companion — a tool for fine-grained, node-level canvas control. "
        "You create, edit, and delete individual Figma nodes (frames, rectangles, ellipses, text). "
        "\n\n"
        "WHEN TO USE THIS vs THE OFFICIAL FIGMA MCP:\n"
        "- Use THIS companion to build new designs from scratch, edit individual node properties "
        "(colors, sizes, fonts, layout), or delete nodes. This works on the LIVE canvas through "
        "a Figma plugin.\n"
        "- Use the official Figma MCP for reading rich design context (get_design_context), "
        "extracting design tokens and variables (get_variable_defs), Code Connect mappings, "
        "and capturing running browser UI as Figma frames (generate_figma_design).\n"
        "\n"
        "INTEROP: Node IDs returned by the official MCP (e.g. from get_metadata) are real Figma "
        "node IDs. You can pass them directly to UPDATE_NODE or DELETE_NODE via the nodeId field, "
        "or use them as parentNodeId when creating child nodes. This lets you read a design with "
        "the official MCP and then edit it with this companion.\n"
        "\n"
        "WORKFLOW:\n"
        "1. Use enqueue_ops to send a batch of create/update/delete operations.\n"
        "2. Use get_job_status to wait for the plugin to execute them.\n"
        "3. Use read_node_tree to see what's on the canvas (for quick inspection).\n"
        "4. Use take_screenshot to visually verify the result.\n"
        "Each op needs a unique tempId. Use parentTempId to nest elements within the same batch, "
        "or parentNodeId to add children to existing nodes."
    ))
    register_tools(mcp, queue)
    return mcp


def _create_api(queue: JobQueue) -> FastAPI:
    api = FastAPI(title="figma-mcp-companion")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.include_router(init_routes(queue))

    @api.get("/health")
    def health():
        return {"status": "ok"}

    return api


def _run_http(api: FastAPI, port: int) -> None:
    """Run the HTTP bridge in this thread. Binds with SO_REUSEADDR to avoid stale port issues."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.set_inheritable(False)

    config = uvicorn.Config(
        api,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        fd=sock.fileno(),
    )
    server = uvicorn.Server(config)
    server.run()


def _run_reaper(queue: JobQueue) -> None:
    """Periodically reap stale jobs and clean up old completed/failed jobs."""
    while True:
        time.sleep(10)
        reaped = queue.reap_stale_jobs()
        if reaped:
            print(f"Reaped {len(reaped)} stale job(s): {reaped}", file=sys.stderr)
        cleaned = queue.cleanup_old_jobs()
        if cleaned:
            print(f"Cleaned up {cleaned} old job(s)", file=sys.stderr)


def main():
    queue = JobQueue()
    mcp = _create_mcp(queue)
    api = _create_api(queue)

    init_auth_token()

    # Start HTTP bridge in a daemon thread — dies when main thread exits
    http_thread = threading.Thread(target=_run_http, args=(api, HTTP_PORT), daemon=True)
    http_thread.start()

    # Start reaper in a daemon thread
    reaper_thread = threading.Thread(target=_run_reaper, args=(queue,), daemon=True)
    reaper_thread.start()

    print(f"HTTP bridge listening on http://127.0.0.1:{HTTP_PORT}", file=sys.stderr)
    print("MCP (stdio) transport: ready", file=sys.stderr)

    # MCP owns the process lifecycle — when it exits, daemon threads die
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
