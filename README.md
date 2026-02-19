# Figma MCP Server

Let AI create, edit, and screenshot Figma designs through natural conversation. Works with Claude Desktop, Cursor, VS Code Copilot, Windsurf, and any MCP-compatible tool.

> "Make me a card component with a hero image, title, description, and a blue CTA button."

The AI builds it directly on your Figma canvas.

<img width="1432" height="959" alt="Claude creating a design in Figma via the MCP bridge" src="https://github.com/user-attachments/assets/4c976e47-89eb-40b1-bcde-e5eb338e7e80" />

---

## How It Complements the Official Figma MCP

Figma's official MCP server and this project solve opposite sides of the same workflow. They are designed to work together.

| | Official Figma MCP | This Project |
|---|---|---|
| **Direction** | Figma → Code (read designs, generate code) | Code/AI → Figma (create and edit designs) |
| **Strengths** | Inspect layouts, extract design tokens, get screenshots for code generation, Code Connect | Create nodes, update properties, delete elements, build entire layouts from scratch |
| **Requires** | Dev Mode seat (paid plan) | Free — runs locally with a development plugin |
| **Rate limits** | 10–20 calls/min, 200–600/day | None — it's your local machine |

### Why use both?

**The official MCP reads. This one writes.** Together they close the loop:

1. **Read** an existing design with the official MCP — "look at this login screen and understand the layout, spacing, and tokens"
2. **Write** a variation with this server — "now build a signup screen following the same patterns, with an extra name field and a social login section"
3. **Screenshot** your creation to verify it visually — "take a screenshot so I can see how it looks"
4. **Read** the result again with the official MCP to generate production code

Neither tool alone covers the full design-to-code-to-design cycle. Used together, your AI can read existing designs, create new ones, visually verify them, and generate production-ready code — all without leaving your editor.

---

## Quick Start

### 1. Install the server

```bash
git clone https://github.com/Chrismacolor/figma-mcp.git
cd figma-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 2. Connect your AI tool

**Claude Desktop** (stdio):

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "figma": {
      "command": "/full/path/to/figma-mcp/.venv/bin/figma-mcp",
      "env": {
        "FIGMA_MCP_TOKEN": "pick-a-stable-token"
      }
    }
  }
}
```

**Cursor / VS Code Copilot / Windsurf** (HTTP):

Start the server manually first:

```bash
source .venv/bin/activate
FIGMA_MCP_TOKEN="pick-a-stable-token" figma-mcp
```

Then add this MCP server URL in your editor's settings:

```
http://localhost:8400/mcp
```

> Setting `FIGMA_MCP_TOKEN` gives you a stable auth token across restarts. If omitted, a random token is generated each startup and printed to the console.

### 3. Install the Figma plugin

```bash
cd plugin && npm install && npm run build
```

In Figma: **Plugins → Development → Import plugin from manifest** → select `plugin/manifest.json`.

Open the plugin, paste your auth token, and click **Connect**. Keep the plugin panel open while using your AI tool.

---

## What It Can Do

### Create designs from natural language

Ask your AI to build UI and it sends structured operations to Figma:

- **Frames** with auto-layout, padding, spacing, corner radius, shadows, and clipping
- **Rectangles and ellipses** with fills, strokes, and opacity
- **Text nodes** with font family, weight, size, alignment, line height, and letter spacing
- **Nested layouts** — child elements reference their parents to build complex component trees

### Edit existing designs

The AI can read the canvas, find nodes by ID, and update any property — recolor a button, change text content, resize a frame, toggle visibility, or delete elements entirely.

### Screenshot your work

The `take_screenshot` tool exports any node (or the current selection) as a PNG and returns it directly to the AI. This lets the AI visually verify what it created and iterate — "the button looks too small, make it wider and bump the font size."

### Read the canvas

`read_node_tree` returns a structured snapshot of every node on the current page — IDs, names, types, positions, sizes, fills, text content, font properties, and layout settings. The AI uses this to understand what already exists before making changes.

---

## Tips for Best Results

- **Be specific about layout.** "A 360px wide card with 24px padding, vertically stacked, 16px gap between items" gives better results than "make a card."
- **Build in batches.** Create the outer frame first, check the result, then add children. This gives the AI a chance to course-correct.
- **Use screenshots to iterate.** After the AI builds something, ask it to take a screenshot and critique its own work. It will often catch spacing or sizing issues and fix them.
- **Combine with the official MCP.** Point the AI at an existing design with the official Figma MCP, then ask it to build a variation using this server. The AI inherits the design language automatically.
- **Keep the plugin open.** The Figma plugin must be open and connected for operations to execute. If the AI reports the plugin is disconnected, switch to Figma and check the plugin panel.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FIGMA_MCP_TOKEN` | Random per startup | Stable bearer token shared between server and plugin |
| `FIGMA_MCP_PORT` | `8400` | HTTP port for the plugin bridge and MCP HTTP endpoint |

---

## How It Works

```
Your AI Tool ──[MCP stdio or HTTP]──► Python Server ◄──[HTTP polling]──► Figma Plugin
                                      (single process)                    (runs inside Figma)
                                      ├─ MCP tools
                                      ├─ HTTP bridge
                                      └─ Job queue
```

1. Your AI calls an MCP tool (e.g., "create a frame") → the server queues a job
2. The Figma plugin polls the server every 1.5s → picks up the job
3. The plugin executes operations against the live Figma document
4. Results (node IDs, screenshots, errors) flow back through the same bridge
5. The AI receives the result and can continue building

Everything runs locally. No data leaves your machine.
