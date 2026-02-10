# Figma MCP Server

An MCP server that lets Claude create editable designs in Figma through natural language prompts.

## Architecture

```
Claude Desktop ──[MCP/stdio]──► Python Server ◄──[HTTP/localhost:8300]──► Figma Plugin
                                (single process)
```

The Python server runs both the MCP protocol (over stdio for Claude) and an HTTP bridge (port 8300 for the Figma plugin) in a single process. The Figma plugin polls the HTTP bridge every 1.5 seconds for pending jobs.

## Setup

### Python Server

```bash
# Install dependencies
pip install -e .

# Run the server
figma-mcp
```

The server prints an auth token to stderr on startup — copy it for the plugin.

### Claude Desktop Configuration

Add to your Claude Desktop MCP config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "figma": {
      "command": "figma-mcp"
    }
  }
}
```

### Figma Plugin

```bash
cd plugin
npm install
npm run build
```

In Figma: Plugins → Development → Import plugin from manifest → select `plugin/manifest.json`.

Open the plugin, paste the auth token from the server output, and click Connect.

## MCP Tools

- **enqueue_ops** — Send a batch of design operations (CREATE_FRAME, CREATE_RECTANGLE, CREATE_ELLIPSE, CREATE_TEXT)
- **get_job_status** — Check if a job has been executed by the plugin
- **read_node_tree** — Read the current Figma page structure
- **list_jobs** — List all jobs and their statuses

## Ops DSL

Each op requires a unique `tempId`. Use `parentTempId` to nest elements inside a previously declared node.

```json
[
  {"op": "CREATE_FRAME", "tempId": "hero", "name": "Hero Section", "w": 1440, "h": 900, "fills": [{"r": 1, "g": 1, "b": 1}]},
  {"op": "CREATE_TEXT", "tempId": "heading", "parentTempId": "hero", "text": "Welcome", "fontSize": 64, "fontFamily": "Inter", "fontWeight": "Bold"}
]
```
