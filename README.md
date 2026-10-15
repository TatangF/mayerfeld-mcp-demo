# mayerfeld-mcp-demo

A hands-on demo of the **Model Context Protocol (MCP)** for **mayerfeld.consulting**: a sandboxed MCP file server, a minimal client that shows the raw protocol, a **Gemini Flash agent** (Google's free API tier) that chooses which tools to call on its own, and a **Gradio web interface** to test everything from a browser.

> ⚠️ **Throwaway data only.** The server only exposes `MCP_SANDBOX_DIR` (default `./sandbox`) and rejects any path outside it. Never point it at real files, and only send disposable data to the free API tier (see [Limits of the free tier](#limits-of-the-free-tier-gemini)).

## Architecture

```mermaid
flowchart LR
    U["👤 User"]
    UI["🌐 Gradio UI<br/>ui.py · service.py<br/>password-protected"]

    subgraph HOST["🖥️ HOST (agent.py + client.py)"]
        direction TB
        LLM["🧠 Gemini Flash<br/>Google AI Studio free tier"]
        CLI["🔌 MCP client<br/>ClientSession"]
    end

    subgraph SRV["🧰 MCP SERVER: mayerfeld-files (server.py)"]
        direction TB
        T1["list_files"]
        T2["read_file"]
        T3["write_file<br/>hidden in read-only mode"]
        T4["search_files"]
        G["🛡️ _safe() + limits<br/>no path outside sandbox<br/>allowed extensions · size cap"]
    end

    FS[("📁 sandbox/<br/>throwaway data")]

    U -->|"browser"| UI
    U -->|"command line"| LLM
    UI -->|"agent tab"| LLM
    UI -->|"tools tab"| CLI
    LLM <-->|"function_call / result"| CLI
    CLI <-->|"MCP · JSON-RPC over stdio<br/>tools/list · tools/call"| SRV
    T1 --> G
    T2 --> G
    T3 --> G
    T4 --> G
    G --> FS
```

| Component | File | Role |
|---|---|---|
| **Web interface** | `src/mayerfeld_mcp/ui.py` | Gradio screens: tool tester, agent, sandbox viewer. Display only |
| **Service layer** | `src/mayerfeld_mcp/service.py` | Logic and security for the UI: validation, rate limit, launch checks, redaction |
| **Host / agent** | `src/mayerfeld_mcp/agent.py` | Loop: sends the tools and the request to Gemini, runs each `function_call` through MCP |
| **MCP client** | `ClientSession` (`mcp` SDK) | Keeps the connection to the server: `initialize`, `tools/list`, `tools/call` |
| **LLM-free client** | `src/mayerfeld_mcp/client.py` | Same protocol, no model. Also builds the server launch parameters |
| **MCP server** | `src/mayerfeld_mcp/server.py` | Exposes the tools over stdio, with path guard, extension allow-list, size cap, read-only mode |
| **Sandbox** | `sandbox/` | Fake data read and written by the tools |

### One agent turn, step by step

```mermaid
sequenceDiagram
    actor U as User
    participant A as Agent (host + MCP client)
    participant G as Gemini Flash
    participant S as MCP server
    participant F as sandbox/

    U->>A: Summarize taches.md
    A->>S: initialize then tools/list
    S-->>A: tools (names, descriptions, JSON schemas)
    A->>G: request + function declarations
    G-->>A: function_call read_file(path=taches.md)
    A->>S: tools/call read_file
    S->>F: read (path validated)
    F-->>S: file content
    S-->>A: tool result
    A->>G: function_response
    G-->>A: final answer as text
    A-->>U: display
```

The protocol does not pick the tool: **the model does**, based on the names, descriptions and schemas it receives. Every tool call is printed on `stderr` as `[outil] name(args)` (and shown in the UI trace).

## Repository layout

```
mayerfeld-mcp-demo/
├── src/mayerfeld_mcp/
│   ├── server.py      # MCP server (FastMCP): tools + guards
│   ├── client.py      # minimal MCP client + server launch parameters
│   ├── agent.py       # Gemini agent wired to the server
│   ├── service.py     # UI logic + security (testable without a browser)
│   └── ui.py          # Gradio interface
├── sandbox/           # fake demo data
├── tests/             # end-to-end, security, service and UI tests
├── docs/FICHE_TECHNIQUE_DEMO.md
├── .github/workflows/ci.yml
├── .env.example
└── pyproject.toml
```

## Quick start

Requirements: Python ≥ 3.10.

```bash
python -m venv .venv
```

Activate the virtual environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

Then install and test:

```bash
pip install -e ".[dev,agent,ui]"
pytest -q
```

You should see **19 passed**. Run everything from the repository root, so the server finds `sandbox/`.

## Demo 1: raw protocol (no LLM, no API key)

```bash
python -m mayerfeld_mcp.client
```

## Demo 2: Gemini Flash agent (free tier)

1. **Create an API key** in [Google AI Studio](https://aistudio.google.com) (menu "Get API key").
2. **Set up the environment**:
   ```bash
   cp .env.example .env        # Windows: copy .env.example .env
   # then fill in GEMINI_API_KEY and GEMINI_MODEL in .env
   ```
3. **Pick a Flash model.** Model names change often. Check the [models list](https://ai.google.dev/gemini-api/docs/models) and the [pricing page](https://ai.google.dev/gemini-api/docs/pricing) to confirm it is available on the free tier, then set `GEMINI_MODEL`. The default (`gemini-2.5-flash`) may have been retired: on a 404 error, change this variable.
4. **Run the agent**:
   ```bash
   mayerfeld-mcp-agent "List my files and summarize taches.md"
   ```
   If the command is not found, use: `python -m mayerfeld_mcp.agent "..."`.

## Demo 3: web interface (Gradio)

```bash
mayerfeld-mcp-ui
```

Then open <http://127.0.0.1:7860>. If the command is not found, use `python -m mayerfeld_mcp.ui`.

| Tab | What it does |
|---|---|
| **1 · MCP tools (no AI)** | Runs `tools/list`, shows each tool's JSON schema, lets you call a tool with JSON arguments (`tools/call`) |
| **2 · Gemini agent** | Sends a request to the agent and shows the answer plus the **trace of every real tool call** |
| **3 · Sandbox** | Lists and opens the files in `sandbox/`, to check the real effects of the tools |

The checkbox at the top (**read-only mode, on by default**) removes `write_file` from the server, so neither you nor the model can write.

### Security measures

| Measure | Where | Effect |
|---|---|---|
| Local-only by default | `ui.py` | Listens on `127.0.0.1`; `share=True` (public Gradio link) is never used |
| Password for network exposure | `service.validate_launch` | If `UI_HOST` is not local, `UI_USERNAME` and `UI_PASSWORD` are mandatory (8+ characters), otherwise the launch is refused |
| Read-only mode | `server.py` | `write_file` is not registered, so it cannot be called or suggested to the model |
| Path guard | `server._safe` | Any path resolving outside `sandbox/` is rejected (including `../` and symlinks) |
| Write limits | `server.py` | Only `.txt .md .json .csv`, at most 100 KB |
| Input validation | `service.py` | Prompt length cap, JSON-object-only arguments, tool name checked against the discovered list |
| Rate limit | `service.RateLimiter` | 10 agent calls per minute, to protect the free quota |
| Secret hygiene | `service.redact` | The API key is never displayed and is masked in error messages; `.env` is git-ignored |

The built-in password is a basic protection for a demo: it sends credentials over plain HTTP. If you expose the UI beyond your machine, put it behind HTTPS (reverse proxy) and a stronger authentication.

**Prompt injection:** a file the agent reads can contain instructions aimed at the model ("now write...", "now read..."). Read-only mode and the guards above limit the damage, which is why read-only is the default in the UI.

### How to check the tools really work

- The **`[outil] ...` lines** (terminal) or the **trace** (UI) prove a tool was actually called. Without them, the model answered on its own.
- **Check the side effects** in the Sandbox tab, or with `Create a file test.txt containing: hello MCP`.
- **Check the refusals**: ask `Read the file ../pyproject.toml`. The server must reject it.

### Limits of the free tier (Gemini)

- **Quotas** depend on the model, apply per project and can change. Exact values are on the [official rate-limits page](https://ai.google.dev/gemini-api/docs/rate-limits); figures quoted by third-party articles disagree. A `429` or `RESOURCE_EXHAUSTED` error means the quota is reached.
- **Privacy**: according to secondary sources, content sent on the free tier may be used to improve Google products. Check the official terms, and only send disposable data.
- **Key safety**: never commit `.env` (already in `.gitignore`), and keep `.env.example` free of real values.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | (empty) | Google AI Studio key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Flash model name (check availability) |
| `MCP_SANDBOX_DIR` | `./sandbox` | Folder exposed by the server |
| `MCP_READ_ONLY` | `0` | `1` hides `write_file` (CLI client and agent) |
| `UI_HOST` / `UI_PORT` | `127.0.0.1` / `7860` | Where the UI listens |
| `UI_USERNAME` / `UI_PASSWORD` | (empty) | Required when `UI_HOST` is not local |

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `GEMINI_API_KEY manquante` | `.env` is not at the repository root, or the key is empty |
| Error `404` from the Gemini API | The model in `GEMINI_MODEL` no longer exists: pick a current Flash model |
| Error `429` / `RESOURCE_EXHAUSTED` | Free-tier quota reached: wait or change model |
| `Lancement refusé : UI_HOST=...` | You bound the UI to the network without `UI_USERNAME` / `UI_PASSWORD` |
| `ImportError` on `mcp.server.fastmcp` | You installed `mcp` 2.x: reinstall with `pip install -e ".[dev,agent,ui]"` (pinned to `<2`) |
| `ModuleNotFoundError: gradio` | Install the UI extra: `pip install -e ".[ui]"` |
| Garbled accents on Windows | Set `$env:PYTHONUTF8=1` (PowerShell), then rerun |
| `pytest: not found` | The virtual environment is not activated |

## Using the server from another MCP client

Stdio command: `python -m mayerfeld_mcp.server`, with the `MCP_SANDBOX_DIR` (and optionally `MCP_READ_ONLY`) environment variables. The configuration format depends on the client: check your client's current documentation.

## Tests and status

| Item | Status |
|---|---|
| Server and tools (discovery, read, write, search) | ✅ tested |
| Sandbox escape, bad extension, oversize write blocked | ✅ tested |
| Read-only mode hides `write_file` | ✅ tested |
| UI service layer (validation, rate limit, launch checks, redaction) | ✅ tested |
| UI starts, password enforced (401 without credentials), tools usable over HTTP | ✅ tested (script, Linux) |
| Agent loop with a **fake** Gemini client | ✅ tested |
| Real Gemini API call with a real key (CLI) | ✅ tested manually |
| Real Gemini call **from the web UI** | ⚠️ to check manually |
| UI rendering in a browser (layout, Windows) | ⚠️ to check manually |

## Versions

- `mcp>=1.2,<2`: the Python SDK v2 renames `FastMCP` to `MCPServer` and changes other APIs. Tested: 1.30.0.
- `google-genai>=2,<3`: tested: 2.30.1.
- `gradio>=6,<7`: tested: 6.30.0.

## Limitations

- **stdio transport only** (local). A remote deployment would need an HTTP transport, proper authentication and a security review.
- The UI starts one server process per action (simple and stateless, slightly slower).
- No per-action human confirmation before `write_file`: read-only mode is the safeguard.

## License

MIT License. See [LICENSE](LICENSE).
