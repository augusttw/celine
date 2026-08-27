# Celine

<div align="center">

**An autonomous, local-first digital agent runtime engineered for secure execution, multi-provider LLM orchestration, and stateful memory.**

[Português](README.pt-BR.md) | **English**

</div>

---

## Overview

**Celine** is an independent, local-first autonomous agent runtime written in Python. Designed with a strict focus on privacy, capability, and developer ergonomics, Celine operates through a native Terminal User Interface (TUI) or headless CLI, isolating all sessions, operational memory, custom skills, and API credentials within `~/.celine`.

By strictly decoupling code from runtime state, personal context and secrets are never committed to version control.

```
┌─────────────────────────────────────────────────────────────┐
│                       Celine Runtime                        │
├──────────────────────────────┬──────────────────────────────┤
│  Terminal User Interface     │  Headless CLI & Eval Engine  │
│  (prompt-toolkit + Rich)     │  (behavior & health checks)  │
├──────────────────────────────┴──────────────────────────────┤
│                     Core Agent Engine                       │
│  Context Manager · Session Store · Long-Term Memory · Soul  │
├──────────────────────────────┬──────────────────────────────┤
│     Native Tool Registry     │   Multi-Provider Catalog     │
│  Files · Shell · Web · Git   │  NVIDIA · OpenAI · Ollama…   │
└──────────────────────────────┴──────────────────────────────┘
```

---

## Key Features

- 🛡️ **Zero-Leak Local State**: All runtime state, sessions, interaction logs, and credentials reside strictly in `~/.celine/` (or `$CELINE_HOME`) with restricted filesystem permissions (`0600` for auth files).
- 🖥️ **Native Terminal UI**: Built on `prompt-toolkit` and `rich`, featuring real-time token streaming, active thinking state indicators, duration metrics, and smooth command dispatching.
- 🔌 **Provider-Agnostic Engine**: Seamlessly switch between NVIDIA NIM, OpenAI, OpenRouter, DeepSeek, Qwen/DashScope, Groq, local Ollama endpoints, or custom OpenAI-compatible providers.
- ⚙️ **Extensible Tool Registry**: Built-in native capabilities for filesystem operations, terminal command execution, Git status/diff analysis, web fetching, and memory indexing.
- 🧠 **Context & Long-Term Memory**: Structured memory storage with explicit consent validation, cross-session search, automatic context ranking/compaction, and secret-leak rejection.
- 🩺 **Diagnostic & Evaluation Suite**: Native utilities (`celine doctor`, `celine evaluate`, `celine status`) to verify system health, runtime assets, and behavioral contracts.

---

## Installation

### Prerequisites

- **OS**: Linux, macOS, or Windows (WSL2 recommended).
- **Python**: 3.11 or higher.
- **Git**: Installed and available in `$PATH`.
- **uv**: Fast Python package installer and resolver ([Installation Guide](https://docs.astral.sh/uv/getting-started/installation/)).
- **LLM Provider**: API key for a supported cloud provider or a running [Ollama](https://ollama.com/) local instance.

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/augusttw/celine.git
   cd celine
   ```

2. **Install in editable mode via `uv`**:
   ```bash
   uv tool install --force --editable .
   ```
   > *Note: Editable installation ensures code modifications take effect immediately without duplicating the runtime environment.*

3. **Initialize the local profile**:
   ```bash
   celine install
   ```

---

## Configuration & Authentication

Celine loads API keys via environment variables or encrypted/restricted local stores. Credentials are never written to `config.yaml` or tracked in Git.

### Supported Providers & Environment Variables

| Provider | Environment Variable |
| :--- | :--- |
| **NVIDIA NIM** | `NVIDIA_API_KEY` or `NVIDIA_NIM_API_KEY` |
| **OpenAI** | `OPENAI_API_KEY` |
| **OpenRouter** | `OPENROUTER_API_KEY` |
| **Qwen / DashScope** | `DASHSCOPE_API_KEY` or `QWEN_API_KEY` |
| **DeepSeek** | `DEEPSEEK_API_KEY` |
| **Groq** | `GROQ_API_KEY` |
| **Ollama** | *(None required for local endpoint)* |

### Setting Environment Variables

Export the variable in your shell profile (`~/.bashrc`, `~/.zshrc`, or equivalent):

```bash
export NVIDIA_API_KEY="your-api-key-here"
```

Alternatively, store credentials securely in `~/.celine/auth.json` (chmod `0600`):

```json
{
  "nvidia-nim": {
    "api_key": "your-api-key-here"
  }
}
```

### Health Check

Verify your installation, file permissions, and provider connectivity:

```bash
celine doctor
celine status
```

---

## Usage

### Launching the Agent

```bash
# Launch interactive TUI
celine

# Execute a single-turn query via CLI (headless)
celine chat -q "Analyze the repository structure and list top modules"
```

### Interactive TUI Commands

Inside the interactive terminal interface, control runtime behavior using slash commands:

| Command | Description |
| :--- | :--- |
| `/model` | Refresh catalog and list all available models |
| `/model refresh` | Force remote model list retrieval from active provider |
| `/model <id>` | Switch and persist active model (e.g., `/model meta/llama-3.1-70b-instruct`) |
| `/provider list` | Display available LLM providers |
| `/provider <name>` | Switch active provider (e.g., `/provider nvidia-nim`) |
| `/session list` | List historical conversation sessions |
| `/session new` | Initialize a clean conversation session |
| `/session switch <id>` | Switch context to a specific session ID |
| `/memory list` | Display persisted long-term memory entries |
| `/memory search <query>` | Query the semantic/keyword memory index |
| `/memory add <text>` | Explicitly record an entry into long-term memory |
| `/retry` | Re-execute the previous turn with current configuration |
| `/clear` | Clear screen and redraw interface |
| `/exit` | Terminate session and exit runtime |

---

## CLI Reference

```bash
celine                        # Launch interactive TUI
celine chat -q "<prompt>"     # Run headless single query
celine install [--options]    # Initialize/update ~/.celine profile
celine doctor                 # Diagnose profile, assets, and provider endpoints
celine evaluate [--live]      # Execute behavioral contracts and test assertions
celine presence status        # Inspect desktop presence and background states
celine presence notify ...    # Send system notification
celine home                   # Print resolved isolated profile path
celine status                 # Print JSON status of provider, model, and session
```

---

## Project Structure

```text
celine/
├── src/
│   ├── celine/
│   │   ├── app.py              # CLI entry point and argument parsing
│   │   ├── config.py           # Configuration schema and profile management
│   │   ├── runtime.py          # Interactive loop and headless execution
│   │   ├── evaluation.py       # Behavioral evaluation and assertions
│   │   ├── profile.py          # Profile installer and doctor diagnostics
│   │   ├── skill_isolation.py  # Sandboxing and skill isolation logic
│   │   ├── core/               # Agent loop, context ranking, memory, and sessions
│   │   ├── providers/          # LLM providers, auth validation, and model catalogs
│   │   ├── tools/              # Native tool implementations (files, shell, web, git)
│   │   ├── ui/                 # Rich/prompt-toolkit rendering, banners, and streaming
│   │   └── assets/             # Core system prompts, skins, and widgets
│   └── celine_companion/       # Desktop presence and notification hooks
├── tests/                      # Automated test suite and visual snapshots
└── ~/.celine/                  # Isolated local runtime state (never committed)
```

---

## Development & Testing

Run unit tests and evaluate behavioral contracts:

```bash
# Run unit test suite
uv run --project . python -m unittest discover -s tests -v

# Run static evaluation
celine evaluate

# Run live provider evaluation
celine evaluate --live
```

---

## Maintenance & Updates

To update an existing installation:

```bash
git pull --ff-only
uv tool install --force --editable .
celine doctor
```

Updating source code leaves `~/.celine/` untouched, preserving existing sessions, memory entries, and authentication keys.

---

## Security Policy

- **Credential Isolation**: Never place API keys inside `config.yaml`, markdown files, or commits. Keep keys in environment variables or `~/.celine/auth.json`.
- **Permissions**: Verify that `~/.celine/auth.json` maintains restricted read permissions (`chmod 600`).
- **Review Diffs**: Always inspect `git status` and `git diff` prior to publishing changes.
- **Backup**: To migrate your personal agent state, back up `~/.celine` to an encrypted, private destination.

---

## License & Contribution

Contributions and improvements are welcome. Please ensure new features include relevant unit tests and pass `celine doctor` and `celine evaluate` before opening a pull request.
