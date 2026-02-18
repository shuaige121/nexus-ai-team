# User Testing Report — NEXUS AI-Team

**Date**: 2026-02-19  
**Tester**: QA Simulation (Claude Opus 4.6)  
**Scope**: Dashboard functional test, data consistency, workflow simulation, API integration, E2E gap analysis  
**Project**: ~/Desktop/nexus-ai-team  
**Branch**: main (current working tree)

---

## Summary: 2 of 11 scenarios fully functional end-to-end

The NEXUS AI-Team project has an impressive frontend dashboard (`dashboard/chain-of-command.html`) with well-structured forms, modals, org chart rendering, context monitoring, approval queue, and SOP viewer. However, it is a **self-contained client-side application** with zero network calls to any backend. Every action resolves within in-memory JavaScript state. The dashboard backend API (`dashboard/backend/`) exists and works but is never called by the HTML dashboard. The gateway (`gateway/main.py`) requires Redis and PostgreSQL to function, and fails to initialize its pipeline without them.

The project has two completely independent systems that do not talk to each other:
1. **chain-of-command.html** -- a standalone interactive prototype (no fetch/axios/XHR calls at all)
2. **dashboard/backend/** -- a FastAPI app serving mock data from Python dicts (MOCK_AGENTS, MOCK_CONTRACTS, etc.)

---

## Test 1: Dashboard HTML Functional Test

### Load Test
- **Result**: PASS -- The file loads without errors. No JS syntax errors detected.
- All 1936 lines parse correctly. CSS is valid. The single `<script>` block (lines 920-1936) contains well-structured JavaScript.
- No external dependencies (no CDN imports, no npm bundles). Fully self-contained single-file app.

### Interactive Elements Audit

| Element | Wired Up? | Actually Works? | Notes |
|---------|-----------|-----------------|-------|
| Org Chart node click | Yes | Yes (client-side) | Populates sidebar detail panel from `COC_DATA` |
| Sidebar tabs (Detail/SOPs/Log) | Yes | Yes | `switchSidebarTab()` toggles display |
| SOP dropdown selector | Yes | Yes | `renderSop()` renders from embedded `SOP_DATA` |
| Log filter buttons | Yes | Yes | `filterLog()` filters `activityLog` array |
| "Create Department" button | Yes | Yes (client-side only) | Opens modal, `submitCreateDept()` generates JSON, adds to `approvalQueue`, logs simulated workflow |
| "Request Tool" button | Yes | Yes (client-side only) | Opens modal, `submitToolRequest()` generates JSON, adds to queue |
| "Hire Employee" button | Yes | Yes (client-side only) | Opens modal, `submitHireRequest()` generates JSON, simulates HR processing |
| "Issue Contract" button | Yes | Yes (client-side only) | Opens modal, `previewContract()` generates JSON preview, `issueContract()` logs |
| "Simulate Alert" button | Yes | Yes | `simulateContextAlert()` sets ceo=85%, hr_manager=91%, re-renders monitor |
| Approval Queue Approve/Reject | Yes | Yes (client-side) | `approveItem()` updates in-memory state, adds dept to org chart if dept creation |
| Context bars click-to-edit | Yes | Yes | `editContext()` uses `prompt()` dialog, updates `contextData` |
| Handoff button | Yes | Yes (simulated) | `triggerHandoff()` sets context to 35% after 3s timeout |
| "Refresh" context | Yes | Yes | `refreshContextBars()` adds random deltas |
| Header clock | Yes | Yes | `startClock()` updates every second |
| Toast notifications | Yes | Yes | `showToast()` creates DOM elements with auto-dismiss |

### JSON Output Test
- **Create Department** generates structured JSON with: type, dept_id, name, purpose, headcount, budget_type, tools_required, skills_required, timestamps. Logged to `console.log`. **PASS**.
- **Request Tool** generates: type, tool_name, requesting_dept, purpose, scope, priority, candidates. **PASS**.
- **Hire Employee** generates: type, agent_id (auto-generated), role, department, reason, skills_required, reports_to, jd_path. **PASS**.
- **Issue Contract** generates: contract_id, issued_by, assigned_to, objective, priority, deadline, deliverables, path. Has "Preview JSON" button that renders into `.json-output` div. **PASS**.

### Org Chart vs chain-of-command.yaml
The HTML embeds `COC_DATA` directly in JavaScript (lines 924-985). Comparing with `company/chain-of-command.yaml`:

| Field | YAML | HTML Embedded | Match? |
|-------|------|---------------|--------|
| Board role/type/level | Board of Directors / human / 0 | Same | Yes |
| Board powers (5) | approve_department_creation, etc. | Same | Yes |
| CEO role/level/model | CEO / 1 / capable | Same | Yes |
| CEO powers (6) | issue_contracts, etc. | Same | Yes |
| CEO constraints (3) | Never reads code, etc. | Same | Yes |
| CEO context_threshold | 0.80 | 0.80 | Yes |
| CEO assistants | enabled, spawn_trigger, max_count:3 | Same | Yes |
| HR department | builtin, active, hr_manager, level 2 | Same | Yes |
| IT department | builtin, active, it_manager, level 2 | Same | Yes |
| Context thresholds | 0.80 / 0.90 | 0.80 / 0.90 | Yes |
| Handoff protocol (7 steps) | 7 steps | Same | Yes |

**Verdict**: The embedded data is a faithful 1:1 copy of the YAML. **PASS**.

### Operational vs Showcase Assessment
**VERDICT: Interactive prototype / showcase.** The dashboard is a polished, self-contained demo. It has no `fetch()`, `axios`, `XMLHttpRequest`, or `WebSocket` calls. All data lives in JS variables. All "actions" modify in-memory arrays and re-render the DOM. Nothing persists across page reloads. Nothing reaches a server.

---

## Test 2: Data Consistency

### chain-of-command.yaml vs org.yaml

These two files describe **completely different organizational structures**:

| Aspect | chain-of-command.yaml | org.yaml |
|--------|-----------------------|----------|
| Departments | 2 (HR, IT) + board/ceo hierarchy | 6 (executive, hr, engineering, qa, it, product) |
| CEO reporting | reports_to: board | reports_to: board |
| HR manager ID | hr_manager | hr_lead |
| IT manager ID | it_manager | it_admin |
| IT reports to | ceo | hr_lead (!) |
| Engineering dept | Does not exist | eng_manager, frontend_dev, backend_dev, devops |
| QA dept | Does not exist | qa_lead, qa_tester |
| Product dept | Does not exist | pm, designer |
| Agent count | 4 (board, ceo, hr_manager, it_manager) | 14 positions |

**Critical conflicts**:
1. **IT reporting line**: In `chain-of-command.yaml`, IT reports to CEO. In `org.yaml`, `it_admin` reports to `hr_lead`. This is a fundamental structural disagreement.
2. **Naming mismatch**: `hr_manager` (chain-of-command.yaml) vs `hr_lead` (org.yaml). Same for IT.
3. **Missing departments**: `chain-of-command.yaml` only has HR and IT as departments. `org.yaml` has 6 departments. The dashboard HTML only renders the chain-of-command.yaml version.

### Mock Data (dashboard/backend/mock_data.py) vs Both YAMLs

The mock data defines a **third** organizational structure:
- 5 departments: executive, hr, engineering, research, marketing
- 11 agents with specific model assignments
- Uses `eng_director` (not `eng_manager`), `research_lead` and `marketing_lead` (neither exists in either YAML)

**Verdict**: Three different org structures exist across three data sources. None are in sync. **FAIL**.

### SOP Consistency

| SOP File | References | Exists? |
|----------|-----------|---------|
| create-department.md | `company/departments/{dept_id}.yaml` | Directory exists but is empty |
| create-department.md | `agents/jds/{manager_id}.md` | Path convention differs: actual JDs are at `agents/{id}/JD.md` or `company/agents/{id}/JD.md` |
| create-department.md | `company/org.yaml` | Exists |
| create-department.md | `company/chain-of-command.yaml` | Exists |
| create-department.md | `logs/hr-activity.log` | Does NOT exist |
| hire-employee.md | `agents/jds/{agent_id}.md` | Path convention differs from actual structure |
| hire-employee.md | `company/templates/jd-template.md` | Actual file is `company/templates/jd_template.md` (underscore not hyphen) |
| hire-employee.md | `logs/handoffs.log` | Does NOT exist |
| add-tool.md | `equipment/{tool_id}.yaml` | Directory exists, has manager.py and registry.yaml, but no individual tool .yaml files |
| add-tool.md | `logs/it-activity.log` | Does NOT exist |

**Missing referenced files**:
- `logs/hr-activity.log` -- referenced in create-department SOP
- `logs/handoffs.log` -- referenced in hire-employee SOP
- `logs/it-activity.log` -- referenced in add-tool SOP
- JD path convention: SOPs say `agents/jds/{id}.md` but actual structure is `agents/{id}/JD.md`
- Template path: SOP says `company/templates/jd-template.md`, actual file is `company/templates/jd_template.md`

**Verdict**: SOPs have multiple broken file references. **FAIL**.

---

## Test 3: User Workflow Simulation

### Scenario A: User wants to create a Marketing department

**Step 1 - Dashboard action**: User clicks "Create Department" button. Modal opens with fields for name, ID, purpose, headcount, budget, tools, skills.

**Step 2 - JSON generated**:
```json
{
  "type": "create_department",
  "dept_id": "marketing",
  "name": "Marketing Team",
  "purpose": "Content creation, social media, brand management",
  "headcount": 2,
  "budget_type": "none",
  "tools_required": [],
  "skills_required": "content writing, SEO",
  "requested_by": "board",
  "requested_at": "HH:MM"
}
```

**Step 3 - Where does it go?**:
- The JSON is `console.log()`-ed and stored in the client-side `approvalQueue[]` array.
- It is displayed in the "Approval Queue" panel.
- The user can click "Approve" which calls `approveItem()`.
- On approval, the department is added to `COC_DATA.departments` in-memory and the org chart re-renders.
- **It never reaches any server.** There is no `fetch()` call.

**Step 4 - Can HR actually create the department?**:
- The dashboard backend has `POST /api/departments` which creates a department in `MOCK_ORG` (in-memory Python dict). But the HTML dashboard never calls this endpoint.
- There is no code that writes to `company/departments/{dept_id}.yaml` (the directory is empty).
- There is no code that updates `company/org.yaml` or `company/chain-of-command.yaml` on disk.
- The HR agent's JD (`agents/hr/JD.md`) exists but there is no automated code path from the dashboard to the HR agent.

**Step 5 - Does org.yaml get updated?**: No. Nothing writes to disk.

**Verdict**: Frontend simulation only. No backend execution. **FRONTEND ONLY**.

### Scenario B: An agent's context hits 85%

**Step 1 - Detection**: The "Simulate Alert" button manually sets context values. The `renderContextMonitor()` function checks `contextData[id].pct >= 80` and displays alert banners. There is NO real context measurement -- the values are hardcoded initial state (`ceo: 62, hr_manager: 45, it_manager: 38`) plus random deltas on "Refresh".

**Step 2 - Handoff trigger**: When context >= 80%, a "Handoff" button appears. Clicking it calls `triggerHandoff(agentId)` which:
- Adds a log entry about initiating the 7-step protocol
- After a 3-second `setTimeout`, sets context to 35%
- The 7 protocol steps are never actually executed

**Step 3 - Can HR auto-generate a JD?**: 
- The dashboard backend has `POST /api/agents` which creates an agent in `MOCK_AGENTS`.
- A JD template exists at `company/templates/jd_template.md` with placeholders.
- But there is no code that fills the template, writes to disk, or links this to the handoff flow.
- The heartbeat system (`heartbeat/monitor.py`) monitors gateway, Redis, PostgreSQL, GPU, budget, and disk -- but it does NOT monitor individual agent context usage.

**Step 4 - Training transfer**: The SOP describes extracting content from manager JD.md to worker JD.md. This is a manual process to be done by an AI agent reading/writing files. There is no automation code for this.

**Verdict**: UI simulation only. No real context monitoring, no auto-JD generation, no training transfer. **FRONTEND ONLY**.

### Scenario C: User wants to add a tool from GitHub

**Step 1 - Request flow**: User clicks "Request Tool", fills form, clicks "Send to IT". JSON is `console.log()`-ed, added to `approvalQueue[]`. After 4 seconds, a simulated completion toast appears. Nothing reaches any server.

**Step 2 - Can IT search GitHub?**: 
- There is no GitHub search code anywhere in the codebase.
- The equipment system (`equipment/manager.py`) manages deterministic scripts (backup, health_check, cost_report, log_rotate).
- `EquipmentManager.register_equipment()` can register a script in `registry.yaml`, but this is for cron-scheduled Python scripts, not GitHub tool discovery.

**Step 3 - Equipment installation code**: 
- `EquipmentManager` can register, enable/disable, and run Python scripts from `equipment/scripts/`.
- It cannot clone repos, install pip packages, or configure external tools.
- The `add-tool` SOP describes writing to `equipment/{tool_id}.yaml` but the actual equipment system uses `equipment/registry.yaml` (a single file) and `equipment/scripts/*.py`.

**Verdict**: UI simulation only. No GitHub search, no tool installation automation. **FRONTEND ONLY**.

---

## Test 4: API Integration Test

### Gateway Startup
```
Command: source .venv/bin/activate && uvicorn gateway.main:app
Result: Starts but pipeline fails to initialize
  - Redis: AuthenticationError (requires password)
  - PostgreSQL: password authentication failed for user "nexus"
  - Gateway serves /health endpoint but all pipeline-dependent endpoints fail
```

The gateway requires Redis + PostgreSQL infrastructure. These are not running with correct credentials.

### Dashboard Backend Startup
```
Command: uvicorn dashboard.backend.main:app
Result: Starts successfully, all endpoints functional (using mock data)
```

### API Endpoint Test Results

| Endpoint | Status | Data Source | Connected to Dashboard HTML? |
|----------|--------|-------------|------------------------------|
| GET /health | 200 OK | Hardcoded | No |
| GET /api/org | 200 OK | MOCK_ORG (Python dict) | No |
| GET /api/org/tree | 200 OK | MOCK_AGENTS (Python dict) | No |
| GET /api/agents | 200 OK | MOCK_AGENTS | No |
| GET /api/agents/{id} | 200 OK | MOCK_AGENTS | No |
| PUT /api/agents/{id}/jd | 200 OK | Updates MOCK_AGENTS in-memory | No |
| POST /api/agents | 200 OK | Adds to MOCK_AGENTS | No |
| DELETE /api/agents/{id} | 200 OK | Removes from MOCK_AGENTS | No |
| GET /api/contracts | 200 OK | MOCK_CONTRACTS | No |
| POST /api/contracts | 200 OK | Appends to MOCK_CONTRACTS | No |
| GET /api/contracts/{id}/chain | 200 OK | Builds tree from MOCK_CONTRACTS | No |
| POST /api/departments | 200/409 | MOCK_ORG | No |
| DELETE /api/departments/{name} | 200 OK | MOCK_ORG | No |
| GET /api/analytics/tokens | 200 OK | `generate_token_history()` (random) | No |
| GET /api/analytics/performance | 200 OK | `generate_performance_data()` (random) | No |
| GET /api/analytics/cost | 200 OK | `generate_cost_optimization()` (hardcoded) | No |
| GET /api/settings/tools | 200 OK | MOCK_TOOLS | No |
| GET /api/settings/models | 200 OK | MOCK_MODELS | No |
| GET /api/settings/state-machine | 200 OK | Hardcoded state definitions | No |
| GET /api/settings/contract-format | 200 OK | Hardcoded template/examples | No |
| POST /api/activate | 200 OK | Sets in-memory `_execution_state` | No |
| WS /ws/live | Available | DashboardWSManager | No |

**Critical finding**: The chain-of-command.html dashboard makes **zero API calls**. Every cell in the "Connected to Dashboard HTML?" column is "No". The dashboard backend serves its own separate data model (MOCK_AGENTS with 11 agents from 5 departments) that has no relationship to the chain-of-command.yaml data embedded in the HTML.

### Approval Queue API
There is **no API endpoint for the approval queue**. The approval queue exists only in the HTML's client-side JavaScript `approvalQueue[]` array. The dashboard backend has contract endpoints but no approval/review workflow endpoints.

---

## Test 5: End-to-End Gap Analysis

### Action-by-Action Trace

| Dashboard Action | Frontend Code | Backend API | Backend Logic | Disk Persistence | Agent Execution | E2E Status |
|-----------------|--------------|-------------|---------------|-----------------|----------------|------------|
| View org chart | `renderOrgChart()` from embedded data | GET /api/org (unused) | Mock data only | chain-of-command.yaml exists but not read dynamically | N/A | FRONTEND ONLY |
| Click node for details | `selectOrgNode()` | GET /api/agents/{id} (unused) | Mock data only | N/A | N/A | FRONTEND ONLY |
| View SOP | `renderSop()` from embedded data | None | N/A | SOP files exist on disk but not read | N/A | FRONTEND ONLY |
| Create department | `submitCreateDept()` | POST /api/departments (unused) | Adds to MOCK_ORG dict | Nothing written to disk | No agent dispatched | FRONTEND ONLY |
| Request tool | `submitToolRequest()` | None | N/A | Nothing written to disk | No IT agent dispatched | FRONTEND ONLY |
| Hire employee | `submitHireRequest()` | POST /api/agents (unused) | Adds to MOCK_AGENTS dict | No JD file generated | No HR agent dispatched | FRONTEND ONLY |
| Issue contract | `issueContract()` | POST /api/contracts (unused) | Appends to MOCK_CONTRACTS | No contract file written | No agent receives contract | FRONTEND ONLY |
| Approve in queue | `approveItem()` | None | N/A | N/A | N/A | FRONTEND ONLY |
| Context monitor | `renderContextMonitor()` | None | N/A | No real context measurement | N/A | FRONTEND ONLY |
| Trigger handoff | `triggerHandoff()` | None | N/A | N/A | No HR agent, no JD transfer | FRONTEND ONLY |
| Simulate alert | `simulateContextAlert()` | None | N/A | N/A | N/A | Works as designed (simulation) |

### What Actually Works End-to-End

1. **Equipment health check**: `equipment/manager.py` + `equipment/scripts/health_check.py` runs on a cron schedule and has executed 20 times (`last_run: 2026-02-19T05:49:36`). This is real, functioning automation.

2. **Gateway work order pipeline**: When Redis + PostgreSQL are properly configured, the gateway can receive messages via HTTP (`POST /api/chat`) or WebSocket (`/ws`), create work orders via `AdminAgent`, enqueue them in Redis, and have the `Dispatcher` route them to agents via `ModelRouter`. This is real pipeline code, not a mock.

Everything else is either mock data or client-side simulation.

---

## Scenario Results

| Scenario | Frontend | Backend | End-to-End | Verdict |
|----------|----------|---------|------------|---------|
| Dashboard loads without errors | PASS | N/A | N/A | PASS |
| Org chart renders correctly | PASS | N/A | N/A | PASS (from embedded data) |
| Create Department form | PASS (JSON generated) | API exists but unused | No disk write, no agent dispatch | FRONTEND ONLY |
| Request Tool form | PASS (JSON generated) | No API endpoint | No GitHub search, no install | FRONTEND ONLY |
| Hire Employee form | PASS (JSON generated) | API exists but unused | No JD generated, no file written | FRONTEND ONLY |
| Issue Contract form | PASS (JSON generated) | API exists but unused | No contract dispatched to agent | FRONTEND ONLY |
| Approval Queue workflow | PASS (client-side) | No API endpoint | No persistence | FRONTEND ONLY |
| Context monitoring | PASS (simulated) | No real monitoring | No agent context measurement | FRONTEND ONLY |
| Context handoff protocol | PASS (simulated 3s delay) | No backend | No HR provisioning, no JD transfer | FRONTEND ONLY |
| SOP viewer | PASS (embedded data) | No API | Does not read SOP .md files dynamically | FRONTEND ONLY |
| Data consistency (YAML files) | N/A | N/A | N/A | FAIL (3 conflicting org structures) |

---

## Critical Gaps

### Gap 1: Dashboard has no backend connection
The chain-of-command.html file contains zero `fetch()`, `axios`, `XMLHttpRequest`, or `WebSocket` calls. Every action resolves within client-side JavaScript. The dashboard backend exists at `/dashboard/backend/` and serves working API endpoints, but nothing connects to them. **This is the single largest gap.**

### Gap 2: Three conflicting organizational structures
- `company/chain-of-command.yaml`: 2 departments (HR, IT), 4 entities
- `company/org.yaml`: 6 departments, 14 positions
- `dashboard/backend/mock_data.py`: 5 departments, 11 agents with full model configs

These three sources disagree on department names, agent IDs, reporting lines, and even which departments exist.

### Gap 3: SOP file references are broken
SOPs reference `agents/jds/{id}.md` but actual JD files live at `agents/{id}/JD.md`. SOPs reference `logs/hr-activity.log`, `logs/it-activity.log`, `logs/handoffs.log` -- none of these files exist. Template path uses hyphen (`jd-template.md`) but actual file uses underscore (`jd_template.md`).

### Gap 4: No real context monitoring
The context percentages in the dashboard are hardcoded initial values with random "Refresh" deltas. The heartbeat system (`heartbeat/monitor.py`) monitors infrastructure health (gateway, Redis, PostgreSQL, GPU, disk) but does NOT track individual agent context window usage. There is no mechanism to measure how much of an agent's context window is consumed.

### Gap 5: Approval queue is ephemeral
The approval queue exists only in the browser's JavaScript memory. Refreshing the page loses all pending approvals. There is no API endpoint to persist, query, or manage approval items.

### Gap 6: Department creation directory is empty
`company/departments/` exists but contains no files. The create-department SOP says HR should write department configs here, but no code does this.

### Gap 7: Equipment system mismatch
The `add-tool` SOP describes writing individual `equipment/{tool_id}.yaml` files. The actual equipment system uses a single `equipment/registry.yaml` for all scripts and only manages Python cron scripts. There is no tool discovery, GitHub search, or arbitrary software installation capability.

---

## Recommendations

### Priority 1: Connect the dashboard to the backend (Critical)
1. Add `fetch()` calls in the HTML JavaScript to load data from dashboard backend API endpoints instead of using embedded `COC_DATA`
2. Replace `submitCreateDept()` console.log with `POST /api/departments` call
3. Replace `submitHireRequest()` with `POST /api/agents` call
4. Replace `submitToolRequest()` with a new backend endpoint
5. Add WebSocket connection to `/ws/live` for real-time updates
6. Add `GET /api/approval-queue` and `POST /api/approval-queue/{id}/approve` endpoints

### Priority 2: Unify the data model (Critical)
1. Pick one canonical org structure and delete or regenerate the others
2. Decide: is `chain-of-command.yaml` the source of truth, or `org.yaml`?
3. Make the dashboard backend read from YAML files on disk instead of hardcoded `MOCK_*` dictionaries
4. Ensure agent IDs are consistent across all files

### Priority 3: Fix SOP file references (Medium)
1. Standardize JD path: decide between `agents/jds/{id}.md` and `agents/{id}/JD.md`
2. Create the missing log files or update SOPs to reference the actual logging mechanism
3. Fix template filename reference (hyphen vs underscore)

### Priority 4: Implement real context monitoring (Medium)
1. Add token counting per agent per session
2. Store context usage in the database
3. Add a `/api/agents/{id}/context` endpoint
4. Wire the heartbeat system to track agent context, not just infrastructure

### Priority 5: Build the agent dispatch bridge (High)
1. When a user approves a department creation, generate and write actual contract files to `company/contracts/pending/`
2. Build a watcher or API that dispatches contracts to agents via the existing nexus-dispatch mechanism
3. Connect the gateway's work order pipeline to the dashboard's approval flow

### Priority 6: Infrastructure prerequisites (High)
1. Configure Redis with authentication credentials
2. Configure PostgreSQL with correct `nexus` user password
3. Document the required `.env` configuration for gateway startup
4. Consider adding a `docker-compose up` that starts Redis + PostgreSQL + Gateway + Dashboard together

---

## Appendix: File Inventory

### Files that ARE real and functional
- `equipment/manager.py` + `equipment/scripts/*.py` -- working cron automation
- `equipment/registry.yaml` -- equipment state with actual run history
- `gateway/main.py` + `gateway/ws.py` -- production-quality gateway (needs Redis/PG)
- `pipeline/dispatcher.py` + `pipeline/queue.py` + `pipeline/work_order.py` -- real work order pipeline
- `nexus_v1/admin.py` -- real AdminAgent with LLM routing and heuristic fallback
- `heartbeat/monitor.py` + `heartbeat/alerts.py` -- real infrastructure monitoring with Telegram alerts
- `dashboard/backend/` -- functional FastAPI app (but serves mock data and is not connected to HTML)
- `company/templates/*.md` -- JD/resume/memory templates with placeholders

### Files that are design documents / static config
- `company/chain-of-command.yaml` -- org structure definition
- `company/org.yaml` -- alternative org structure
- `company/sops/*.md` -- process documentation
- `dashboard/chain-of-command.html` -- interactive prototype (no backend connection)

### Files/paths referenced but missing
- `logs/hr-activity.log`
- `logs/it-activity.log`
- `logs/handoffs.log`
- Any file in `company/departments/`
- `agents/jds/*.md` (path convention does not match actual `agents/*/JD.md`)
