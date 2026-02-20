# Figma MCP Companion

Fine-grained canvas control for AI-assisted Figma design. Create, edit, and manipulate individual design nodes through natural conversation — works with Claude Desktop, Cursor, VS Code Copilot, Windsurf, and any MCP-compatible tool.

> "Make me a card component with a hero image, title, description, and a blue CTA button."

The AI builds it directly on your Figma canvas, node by node.

<img width="1432" height="959" alt="Claude creating a design in Figma via the MCP bridge" src="https://github.com/user-attachments/assets/4c976e47-89eb-40b1-bcde-e5eb338e7e80" />

---

## How It Complements the Official Figma MCP

The [official Figma MCP server](https://developers.figma.com/docs/figma-mcp-server/) and this project solve different parts of the design workflow. They are designed to work together.

| | Official Figma MCP | This Project |
|---|---|---|
| **Write approach** | `generate_figma_design` — captures live browser UI and converts it into editable Figma frames | Creates individual nodes (frames, rectangles, text, ellipses), sets properties, builds layouts from scratch |
| **Read approach** | `get_design_context`, `get_metadata`, `get_variable_defs`, `get_screenshot` — rich design context extraction | `read_node_tree` — structured snapshot of the canvas; `take_screenshot` — PNG export of any node |
| **Best for** | Design-to-code pipelines, capturing running UI back into Figma, design system integration via Code Connect | Building new designs from scratch, fine-grained edits to individual nodes, rapid prototyping on the canvas |
| **Requires** | Dev Mode seat (paid plan) | Free — runs locally with a development plugin |
| **Rate limits** | Figma API limits apply | None — it's your local machine |

### Why use both?

The official MCP excels at **extracting design context for code generation** and **capturing finished UI back into Figma** as editable frames. This companion fills the gap for **precise, node-level canvas control** — creating designs from scratch, tweaking individual properties, and iterating on layouts without leaving your editor.

A typical combined workflow:

1. **Read** an existing design with the official MCP — "look at this login screen and understand the layout, spacing, and tokens"
2. **Build** a variation with this companion — "now create a signup screen following the same patterns, with an extra name field and a social login section"
3. **Screenshot** your creation to verify it visually — "take a screenshot so I can see how it looks"
4. **Iterate** with fine-grained edits — "make the CTA button wider and bump the font to 18px"
5. **Capture** the finished UI with the official MCP's `generate_figma_design` to bring production code back to the canvas

Neither tool alone covers the full workflow. Together, your AI can read existing designs, build new ones node by node, visually verify them, and bridge between code and canvas — all without leaving your editor.

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
    "figma-companion": {
      "command": "/full/path/to/figma-mcp/.venv/bin/figma-mcp-companion",
      "env": {
        "FIGMA_MCP_TOKEN": "pick-a-stable-token"
      }
    }
  }
}
```

**Claude Code** (stdio or HTTP):

Option A — stdio (server starts/stops with each Claude Code session):

```bash
claude mcp add figma-companion -e FIGMA_MCP_TOKEN=pick-a-stable-token -- /full/path/to/figma-mcp/.venv/bin/figma-mcp-companion
```

Option B — HTTP (start the server yourself, keeps running between sessions):

```bash
# In one terminal:
source .venv/bin/activate
FIGMA_MCP_TOKEN="pick-a-stable-token" figma-mcp-companion

# Then register it:
claude mcp add --transport http figma-companion http://localhost:8400/mcp
```

> To use alongside the official Figma MCP, add both — they complement each other. The official MCP reads design context and captures browser UI; this companion builds and edits individual nodes on the canvas.

**Cursor / VS Code Copilot / Windsurf** (HTTP):

Start the server manually first:

```bash
source .venv/bin/activate
FIGMA_MCP_TOKEN="pick-a-stable-token" figma-mcp-companion
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
- **Combine with the official MCP.** Point the AI at an existing design with the official Figma MCP, then ask it to build a variation using this companion. The AI inherits the design language automatically.
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
