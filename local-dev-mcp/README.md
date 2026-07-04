# local-dev-mcp

A **local [MCP](https://modelcontextprotocol.io) server** that gives Notion AI
(or any MCP-compatible client) the same kind of hands-on access to your machine
that **Claude Code** has: the filesystem, a real terminal, git, project
analysis, processes, the network, databases, containers, archives, your editor,
and — where a display exists — the GUI.

The AI stays the "brain"; this server is the **bridge** to your operating system
and developer tooling. Once connected, you can talk to the agent in natural
language and it can read and write code, run builds and tests, drive git, fix
errors, query databases, and automate day-to-day development chores.

> ⚠️ **This is a powerful tool.** By default it trusts the machine it runs on.
> Read [Security](#security) and lock it down for your environment.

---

## Features (78 tools across 14 modules)

| Module | Highlights |
| --- | --- |
| **filesystem** | read / write / edit / append / delete, copy, move, mkdir, rmdir, list, file info, project `tree` |
| **search** | find files by glob, search file contents by regex (ripgrep-accelerated) |
| **terminal** | run commands (stdout/stderr/exit code); background & interactive **sessions** with stdin, multiple in parallel |
| **git** | status, diff, add, commit/amend, log, branch, checkout, merge, rebase, cherry-pick, stash, blame, pull, push, tag, plus raw `git_run` |
| **process** | list processes, inspect by PID, kill (psutil or `ps`) |
| **system** | OS info, env vars, disk usage, memory, network interfaces |
| **network** | HTTP(S) requests, file downloads (stdlib, no deps) |
| **browser** | fetch a web page and extract readable text |
| **database** | SQLite (built-in) + PostgreSQL / MySQL / MSSQL (optional drivers), schema inspection |
| **docker** | `docker ps/images/logs/run`, compose, `kubectl` |
| **workspace** | detect project type, list dependencies, code stats, find TODO/FIXME |
| **ide** | detect editors, open project / file, jump to a line (VS Code, Cursor, Sublime, JetBrains, vim) |
| **archive** | create / list / extract zip & tar(.gz/.bz2/.xz); extract rar & 7z via CLI |
| **gui** | screenshot, mouse move/click/drag, type text, hotkeys, clipboard, launch apps (needs a display + optional libs) |

Every tool returns structured JSON and fails softly: if a required CLI or
optional library is missing, the tool returns a clear message instead of
crashing the server.

---

## Requirements

- **Python 3.10+**
- The `mcp` package (the only hard dependency)
- Optional CLIs for the tools you care about: `git`, `rg` (ripgrep), `docker`,
  `kubectl`, `unrar`, `7z`, an editor launcher, ...
- Optional Python extras (see [`requirements-optional.txt`](requirements-optional.txt))
  for richer process/system stats, database drivers and GUI automation.

## Installation

```bash
git clone <your-fork-url>
cd local-dev-mcp

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install -r requirements.txt      # core
pip install -r requirements-optional.txt   # optional extras (psutil, GUI, DB drivers)
```

## Running

```bash
# stdio transport (what MCP clients launch)
python server.py

# or an HTTP transport for remote/manual testing
python server.py --transport streamable-http --host 127.0.0.1 --port 8000
```

## Connecting it to Notion AI

Notion AI Enterprise supports connecting **custom MCP servers** from the agent's
**Tools and access** settings. Point it at this server. Because Notion reaches
your machine from the cloud, a local server must be exposed over HTTPS (e.g. via
`cloudflared` or `ngrok`), and you should set an auth token first:

```bash
# generate a token once
python -c "import secrets; print(secrets.token_urlsafe(32))"

# run the server with the token (Windows PowerShell: $env:LOCAL_DEV_MCP_AUTH_TOKEN="...")
LOCAL_DEV_MCP_AUTH_TOKEN=<token> python server.py --transport streamable-http --port 8000

# in another terminal, expose it
cloudflared tunnel --url http://localhost:8000
```

The MCP endpoint is the public URL with `/mcp` appended. Add it in the agent's
**Tools and access → connectors**, and provide the token as an
`Authorization: Bearer <token>` header. If the connector only accepts a bare
URL (no header field), embed the secret in the URL instead:
`https://<public-host>/mcp?key=<token>`.

Then add the server's URL in the agent's **Tools and access → MCP servers**
section and grant the capabilities you want. (Notion custom-agent permissions,
triggers, and tool connections are configured from the agent settings UI, not
from the server itself.)

### Connecting it to a desktop MCP client (Claude Desktop, etc.)

Add an entry like this to the client's MCP config:

```json
{
  "mcpServers": {
    "local-dev": {
      "command": "python",
      "args": ["/absolute/path/to/local-dev-mcp/server.py"],
      "env": {
        "LOCAL_DEV_MCP_ROOTS": "/home/me/projects",
        "LOCAL_DEV_MCP_ALLOW_GUI": "false"
      }
    }
  }
}
```

---

## Configuration

All configuration is via environment variables (see [`.env.example`](.env.example)):

| Variable | Default | Meaning |
| --- | --- | --- |
| `LOCAL_DEV_MCP_ROOTS` | *(empty = unrestricted)* | `os.pathsep`-separated allow-list of directories. Every path is confined to these roots. |
| `LOCAL_DEV_MCP_ROOTS_FILE` | *(auto)* | Path to an allow-list file (one directory per line, `#` comments). A file at `~/.local-dev-mcp/allowed_roots.txt` is also loaded automatically. |
| `LOCAL_DEV_MCP_ALLOW_WRITE` | `true` | Allow file writes/edits. |
| `LOCAL_DEV_MCP_ALLOW_DELETE` | `true` | Allow deletes. |
| `LOCAL_DEV_MCP_ALLOW_TERMINAL` | `true` | Allow command execution & process control. |
| `LOCAL_DEV_MCP_ALLOW_NETWORK` | `true` | Allow HTTP requests / downloads. |
| `LOCAL_DEV_MCP_ALLOW_GUI` | `true` | Allow GUI automation. |
| `LOCAL_DEV_MCP_ALLOW_DATABASE` | `true` | Allow database tools. |
| `LOCAL_DEV_MCP_COMMAND_TIMEOUT` | `120` | Default per-command timeout (seconds). |
| `LOCAL_DEV_MCP_MAX_OUTPUT_BYTES` | `200000` | Cap on captured stdout/stderr. |
| `LOCAL_DEV_MCP_MAX_READ_BYTES` | `2000000` | Cap on file reads. |
| `LOCAL_DEV_MCP_DEFAULT_CWD` | *(process CWD)* | Default working directory for commands. |
| `LOCAL_DEV_MCP_AUTH_TOKEN` | *(none)* | Shared secret for HTTP/SSE transports. When set, requests must send `Authorization: Bearer <token>` or `X-API-Key: <token>`. |
| `LOCAL_DEV_MCP_ALLOWED_HOSTS` | *(empty = off)* | Comma-separated Host-header allow-list (DNS-rebinding protection). Empty disables host checks so the server works behind a tunnel; set it to pin hosts. |
| `LOCAL_DEV_MCP_LOG_LEVEL` | `INFO` | Logging verbosity (logs go to stderr). |

---

## Security

This server can read/write files, run arbitrary commands and control your
desktop. Treat it like an SSH session that an AI drives on your behalf.

Recommended hardening:

- Set `LOCAL_DEV_MCP_ROOTS` to the specific project directories you want the
  agent to touch. Everything outside is rejected with a `PermissionError`.
- Disable capabilities you don't need (`ALLOW_GUI=false`, `ALLOW_DELETE=false`, ...).
- Run it as a **non-privileged user**, ideally inside a container or VM.
- Never expose the network transport on a public interface without
  authentication. Set `LOCAL_DEV_MCP_AUTH_TOKEN` to a long random secret;
  unauthenticated requests then get `401`. When you serve it through a tunnel
  (e.g. `cloudflared`/`ngrok`), the token is what stops anyone with the URL
  from controlling your machine.
- Environment variables may contain secrets; `system_env_vars` returns their
  values, so keep the transport private.

---

## Architecture

```
local-dev-mcp/
├── server.py          # entry point: builds FastMCP and registers all tools
├── config.py          # env-driven configuration + path policy
├── requirements.txt
├── tools/             # one module per capability, each with register(mcp)
│   ├── filesystem.py  terminal.py  git.py     search.py
│   ├── process.py     system.py    network.py browser.py
│   ├── database.py    docker.py    workspace.py ide.py
│   └── archive.py     gui.py
├── utils/             # logger, TTL cache, subprocess/formatting helpers
└── tests/             # pytest suite (+ end-to-end MCP handshake smoke test)
```

Each tool module keeps its logic in plain, testable functions and exposes a
thin `register(mcp)` wrapper that declares the MCP tools. `tools/__init__.py`
wires them all together via `register_all(mcp)`.

## Development

```bash
pip install pytest
pytest            # runs unit tests + a full server build/handshake smoke test
```

## License

MIT
