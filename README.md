# Agents Team — AI-Powered Development Pipeline

> An autonomous AI development team that takes a feature description and plans, architects, codes, tests, and verifies software — for iOS, Android, and Django — with near-zero API cost.

Built as an open demonstration that the way we build software has changed. This project is not a product — it is a statement: AI teams can handle POCs, internal tooling, and boilerplate work so human engineers can focus on what actually requires human judgment.

---

## How It Works

```
Human (Product Owner)
  ↓  feature description (plain English)
Orchestrator  (cloud LLM — haiku tier)      PRD · backlog · sprint plan · sprint review
  ↓  sprint plan
Architect     (qwen2.5-coder:14b — Ollama)  architecture document per sprint
  ↓  per user story
Coder         (qwen2.5-coder:14b — Ollama)  implementation files
  ↓
Test Writer   (qwen2.5-coder:14b — Ollama)  unit + integration tests
  ↓
Verifier      (qwen2.5-coder:7b  — Ollama)  build · lint · test → pass / fail
  ↓  on fail (max 3 retries)
Coder  ←  targeted error report
```

Only the **Orchestrator** uses a paid cloud model (haiku-tier, ~$0.02–0.08 per sprint). Every other agent runs locally on Ollama — **free**.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | [python.org](https://www.python.org/downloads/) |
| Node.js 18+ | Required for the web UI |
| [Ollama](https://ollama.ai) | Local LLM runtime |
| Cloud LLM API key | Only used by the Orchestrator |

### Pull the required Ollama models

```bash
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5-coder:7b
```

Make sure Ollama is running before starting the pipeline:

```bash
ollama serve
```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/abielcode/agents_team.git
cd agents_team
```

### 2. Set up the Python environment

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 3. Set your cloud LLM API key

```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

Or create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your-api-key-here
```

### 4. (Optional) Adjust team configuration

Edit `backend/config/team_config.json` to change models, token limits, or cost guards.

---

## Usage — CLI (Phase 1)

### Full run: task → PRD → backlog → sprint → code

```bash
python cli.py \
  --platform ios \
  --task "Add a login screen with email and password fields" \
  --project ~/path/to/MyiOSApp
```

### Dry run (no real build tools — LLM-only verification)

```bash
python cli.py \
  --platform ios \
  --task "Add push notifications" \
  --project ~/path/to/MyiOSApp \
  --dry-run
```

### Continue to the next sprint

```bash
python cli.py \
  --platform ios \
  --project ~/path/to/MyiOSApp \
  --prd .agents_team/prd.json \
  --backlog .agents_team/backlog.json \
  --sprint 2 \
  --completed US001 US002 US003
```

### All CLI options

| Option | Description |
|---|---|
| `--platform` | `ios` \| `android` \| `django` (required) |
| `--project` | Path to the target project directory (required) |
| `--task` | Free-form feature description (required if no `--prd`) |
| `--prd` | Path to an existing `prd.json` |
| `--backlog` | Path to an existing `backlog.json` |
| `--sprint-plan` | Path to an existing sprint plan JSON |
| `--sprint` | Sprint number to run (default: 1) |
| `--prev-arch` | Path to the previous sprint architecture JSON |
| `--completed` | Story IDs already completed (space-separated) |
| `--dry-run` | Skip real build/lint/test tools |

### Output artifacts

Each run writes artifacts to `<project>/.agents_team/`:

```
.agents_team/
├── prd.json                     structured Product Requirements Document
├── backlog.json                 full product backlog (epics + stories)
├── sprint_1_plan.json           sprint 1 scope + rationale
├── sprint_1_architecture.json   sprint 1 architecture document
└── sprint_1_review.json         sprint 1 review + next sprint proposal
```

---

## Usage — Web Interface (Phase 2)

The web interface provides a full project management UI with live agent streaming.

### Start the backend

```bash
source .venv/bin/activate
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`.  
Interactive API docs: `http://localhost:8000/docs`

### Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The web app will be available at `http://localhost:5173`.

### Web interface pages

| Page | Description |
|---|---|
| **Project Setup** | Create and manage projects |
| **PRD Builder** | Build a structured PRD from a plain-English description |
| **Product Backlog** | View and manage epics and user stories |
| **Sprint Board** | Kanban board — run sprints and watch agents work in real time |
| **Agent Console** | Live token streaming from every agent during execution |
| **Sprint Review** | Sprint summary, completed stories, flagged items |
| **Team Config** | Adjust model assignments, token limits, and cost guards |

### Live streaming

The Sprint Board streams agent output in real time over WebSocket (`/ws/sprint/{sprint_id}`). You can watch the Coder write code, the Verifier run the build, and the sprint summary appear — token by token — without refreshing the page.

---

## Pipeline Phases

| Phase | Agent | What Happens |
|---|---|---|
| INIT | — | Load config, detect platform, scan project |
| PLANNING | Orchestrator | PRD refinement → backlog → sprint plan |
| ARCHITECTURE | Architect | Sprint architecture document |
| CODING | Coder | Story-by-story implementation |
| TESTING | Test Writer | Unit + integration test generation |
| VERIFYING | Verifier | Build + lint + test → pass or retry |
| DONE / RETRY | — | Pass → next story · Fail → retry (max 3×) |

---

## Cost Model

| Agent | Provider | Approximate Cost |
|---|---|---|
| Orchestrator | Cloud LLM (haiku tier) | ~$0.02–0.08 per sprint |
| Architect | Ollama (local) | Free |
| Coder | Ollama (local) | Free |
| Test Writer | Ollama (local) | Free |
| Verifier | Ollama (local) | Free |

Cost guards (configurable in `team_config.json`):
- **Warn** at $0.10 cloud LLM spend per sprint
- **Hard stop** at $0.50 cloud LLM spend per sprint

Prompt caching is enabled on the Orchestrator to further reduce token costs on repeated calls.

---

## Project Structure

```
agents_team/
├── cli.py                        CLI entry point (Phase 1)
├── requirements.txt
├── backend/
│   ├── agents/                   5 agents: orchestrator, architect, coder, test_writer, verifier
│   ├── api/                      FastAPI app + REST routes + WebSocket
│   │   └── routes/               projects, prd, backlog, sprints, agents, costs
│   ├── core/                     gateway (cloud+Ollama), pipeline, cost_tracker, reporter
│   ├── db/                       SQLite models (SQLAlchemy + aiosqlite)
│   ├── platforms/                ios, android, django + build output parsers
│   ├── tools/                    codebase_scanner, git_guard, xcodegen_sync
│   └── config/
│       └── team_config.json      model assignments, token limits, cost guards
└── frontend/
    └── src/
        ├── pages/                ProjectSetup, PRDBuilder, ProductBacklog, SprintBoard,
        │                         SprintReview, AgentConsole, TeamConfig
        ├── components/           Layout, Sidebar, CostMeter, StatusBadge,
        │                         StreamingOutput, SprintRunModal
        ├── hooks/                useWebSocket.js
        ├── api/                  client.js
        └── store.js
```

---

## Why Local LLMs Matter

Running AI agents locally is not just about cost — it is about sustainability.

Former Google CEO Eric Schmidt warned the U.S. Congress that AI infrastructure will require **92 additional gigawatts** of electricity in the United States alone by 2030. That is the equivalent of dozens of nuclear power plants.

Every API call you offload from a cloud data center to a local model reduces that aggregate demand. The hybrid approach in this project — cloud AI for judgment, local AI for execution — is a small but reproducible demonstration that powerful AI pipelines can be built with a fraction of the energy footprint.

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you would like to change.

---

## License

This project is licensed under the **GNU General Public License v3.0**.  
See the [LICENSE](LICENSE) file for details.

You are free to use, modify, and distribute this software under the terms of the GPL v3. Any derivative work must also be distributed under the same license.

---

## Author

Built by [@abielcode](https://github.com/abielcode) as an open-source demonstration that AI development teams can be practical, affordable, and environmentally responsible.
