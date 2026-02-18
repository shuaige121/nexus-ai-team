# NEXUS AI-Team Architecture Review

**Date**: 2026-02-19  
**Reviewer**: Senior Architect (Internal)  
**Status**: Critical — Not Production Ready  
**Codebase age**: ~3 days  
**Lines reviewed**: ~26K (agentoffice engine, pipeline, gateway, company config, SOPs)

---

## Executive Summary

NEXUS has a compelling organizational metaphor — CEO, managers, workers, HR, IT — and a structurally sound contract pipeline design. The idea of context isolation through role-based information filtering is genuinely good. But beneath the metaphor, there are serious gaps between what the documentation describes and what the code actually does. The security model is largely aspirational. The chain-of-command is not enforced. The org structure has duplication and inconsistency. Context management is completely unimplemented. Several single points of failure have no redundancy whatsoever.

This review is blunt because a blunt review now is worth more than a polite review after you've built 50 more agents on top of a broken foundation.

---

## 1. Chain of Command Logic

### 1.1 Hierarchy Definition: Structurally Sound, Practically Ignored

The hierarchy is defined in two places: `company/org.yaml` and `company/chain-of-command.yaml`. These two files duplicate the same information in different formats and have already drifted apart. `org.yaml` uses `hr_lead` and `it_admin` as top-level names. `chain-of-command.yaml` uses `hr.manager` and `it.manager`. These are not the same identifiers. Any code that reads one file and cross-references the other will silently produce wrong results.

There is also a third agent directory structure: `company/agents/` (old, static) and `agents/` (new, runtime). Both exist simultaneously. The `agentoffice/config.py` points to `company/agents/` as `AGENTS_DIR`. The `agents/README.md` says `agents/` is the new runtime workspace. So which one does the engine actually use? Answer: `company/agents/`. The `agents/` directory with its INBOX-based mail system and Unix permission model is the DESIGN.md vision, not the current runtime reality.

### 1.2 Permission Boundaries: Documented, Not Enforced

The chain-of-command is read by `activate.py` to determine an agent's level (CEO/manager/worker). The `can_command` list is used to populate the manager's context view of subordinates. That is where enforcement ends.

There is no code that checks whether agent A is actually authorized to send a contract to agent B before routing it. The `route_contract()` function in `router.py` checks only that the target agent directory exists — not that the sender is permitted to dispatch to that target. A worker can call `create_contract(from_agent="backend_dev", to_agent="ceo", ...)` and it will be routed without any authorization check.

The hierarchy is consulted for context building. It is not a security boundary.

### 1.3 CEO Unavailability: No Fallback

There is no deputy CEO, no acting authority mechanism, no fallback path. If the CEO agent fails mid-chain (LLM timeout after 3 retries, budget exhaustion, malformed response), the entire chain terminates with an error. No escalation to the board occurs. No alert fires specifically for "CEO unreachable." The work order just fails in the database.

The `chain-of-command.yaml` documents a `context_threshold` and `assistants.spawn_trigger` for the CEO, but this is entirely unimplemented. There is no code that monitors CEO context usage, no spawning of assistant agents, and no mechanism to detect that the CEO is saturated.

### 1.4 Worker Bypass: Possible via dynamic Target Resolution

The `choice_handlers.py` dynamic target resolution reads `choice_payload["to"]` without any validation against the org hierarchy. If a worker's LLM response includes `"choice": "request_assistance", "choice_payload": {"to": "board"}`, the contract will be routed directly to the board, bypassing all intermediate layers. The only thing preventing this is the LLM following its system prompt instructions — which is not a security boundary.

---

## 2. Communication Protocol

### 2.1 Two Incompatible Systems Coexist

DESIGN.md describes a mail system: files dropped into `INBOX/` directories with `chmod 733` permissions, structured markdown mail headers, send_mail.sh scripts. The `agents/` directory implements this model with actual INBOX directories.

The agentoffice engine (`activate.py`, `contract_manager.py`) implements a completely different contract system: YAML files in `company/contracts/pending/`, `completed/`, `archived/` directories, processed synchronously by a recursive `activate()` call chain.

These are two different communication models. The INBOX mail system is not connected to the contract pipeline. The scripts referenced in `agents/ceo/TOOL.md` (`send_mail.sh`, `check_inbox.sh`, `read_mail.sh`) do not exist. The `agents/scripts/` directory exists but does not contain these scripts.

### 2.2 No Message Bus

There is no real message bus. The contract pipeline is a synchronous file-system poll: `load_pending_contracts()` reads all YAML files from `company/contracts/pending/`, then calls `route_contract()` on each. This is essentially a directory-scan loop dressed up as a message queue.

The gateway has Redis Streams integration in `pipeline/queue.py`, but this queue is used only for the `nexus_v1`-tier pipeline (the Dispatcher/ModelRouter path). The agentoffice engine does not use Redis at all. The two pipeline implementations — `agentoffice/engine/activate.py` and `pipeline/dispatcher.py` — run completely independently and do not share a queue.

### 2.3 No Prevention of Direct Agent Communication

Nothing prevents an agent from constructing a contract with any target it wants. The `create_contract()` function takes `from_agent` and `to_agent` as plain strings with no validation. An LLM that decides to pass `"to": "sec_analyst"` in its `choice_payload` will have that contract routed directly to the security analyst, bypassing the IT manager and the CEO.

### 2.4 Contract Delivery is Pull, Not Push

The current system requires something to call `route_contract()` or `process_pending_contracts()` to move contracts. There is no persistent listener watching the pending directory. If the calling process exits between contract creation and routing, contracts sit in `company/contracts/pending/` forever with no delivery.

---

## 3. SOP Enforcement

### 3.1 SOPs Are Decoration

The three SOP files (`add-tool.md`, `create-department.md`, `hire-employee.md`) describe step-by-step processes with actors, actions, output files, and approval requirements. None of this is enforced in code.

There is no SOP runner. There is no step sequencer. There is no mechanism to verify that "Step 5: Write tool spec to equipment/{tool_id}.yaml" was actually executed before proceeding to "Step 6: Run integration test." An agent that skips step 3 and jumps to step 8 will not be caught.

The SOPs are documentation that agents are expected to read in their system prompt and voluntarily follow. If the LLM decides to skip a step, or misunderstands a step, or hallucinates completing a step it did not complete, there is no detection mechanism.

### 3.2 Approval Requirements Have No Enforcement Gate

The SOP tables list "Requires Approval: CEO" or "Requires Approval: Board" for various actions. There is no approval gate in the code. The `create_department` SOP says CEO approval is required — but the `create_department()` tool in `agentoffice/tools/create_department.py` can be called directly by any agent whose tool_calls the engine decides to execute. There is no check for a prior approval contract before the tool runs.

### 3.3 Output File Validation: None

SOPs specify output files that should be created (e.g., `equipment/{tool_id}.yaml`, `logs/hr-activity.log`). No code verifies these files were created after a SOP completes. The `logs/` directory likely does not exist. There is no log rotation or log existence check.

---

## 4. Context Management

### 4.1 Context Tracking: Completely Unimplemented

The `chain-of-command.yaml` defines `context_threshold: 0.80` and `critical_threshold: 0.90` for agents. The `hire-employee.md` SOP describes a "Training & Handoff Protocol" triggered when "any agent context > 80%." The context management section of `chain-of-command.yaml` describes a detailed handoff workflow.

None of this is implemented. There is no code anywhere in the repository that:
- Tracks an agent's context window usage as a percentage
- Compares that usage to any threshold
- Triggers HR to provision a new agent
- Executes a handoff protocol

The `llm_client.py` records `input_tokens` and `output_tokens` per call, but these are not summed across a session, not compared to model limits, and not used to trigger anything.

### 4.2 Context 85% Detection is Architecturally Unsound

Even if someone wanted to implement this, the current architecture makes it difficult. Each `activate()` call is stateless — it builds a fresh system prompt each time. There is no session object tracking cumulative token usage across multiple contract activations for the same agent. To detect "this agent has used 85% of its context budget across its lifetime of contracts," you would need persistent per-agent session accounting, which does not exist.

### 4.3 Handoff Protocol Relies on LLM Self-Reporting

Even if context tracking were implemented, the handoff protocol as designed requires the manager agent to "extract execution-level content from own JD.md" and "write training section into new worker's JD.md." This is the agent modifying its own JD.md — the file that `agents/README.md` explicitly marks `chmod 444` (read-only). The design contradicts itself.

---

## 5. Single Points of Failure

### 5.1 HR Agent Failure: No One Else Can Create Agents

The org structure designates HR as the sole creator of agents. If the HR agent fails (LLM error, budget exceeded, corrupted memory file), there is no alternative path to create new agents. The `create_agent()` Python function exists and could be called programmatically, but no other agent has it in their tool_map. There is no documented emergency procedure.

### 5.2 IT Agent Failure: No One Else Can Install Tools

Same pattern. The `add-tool.md` SOP gives IT sole authority over tool installation. If IT fails, departments cannot get new tools. There is no backup IT agent, no self-service tool installation path, and no mechanism for CEO to temporarily assume IT authority.

### 5.3 Gateway Failure: Everything Stops

The FastAPI gateway is the single entry point. There is no load balancing, no standby instance, and no health check that triggers automatic restart (the heartbeat service can restart it, but only if the heartbeat service itself is running). If the gateway process dies and the heartbeat service is not configured, all work order intake stops. Existing work orders sitting in the Redis queue will not be processed because the dispatcher runs as a background task inside the gateway process — it is not a separate worker process.

### 5.4 org.yaml Corruption: Catastrophic

`org.yaml` is the single source of truth for the entire organizational hierarchy. It is a plain YAML file with no schema validation, no version history beyond git, no locking, and no backup mechanism. The `save_org()` function does a direct overwrite. If two agents call `create_agent()` or `update_chain()` concurrently (even theoretically, in a future async implementation), they will race to write `org.yaml` and one write will silently overwrite the other. There is a `org.yaml.bak` file present in the repository, suggesting this has already been a concern, but there is no code that creates or uses this backup.

### 5.5 The Budget Guard is Process-Local

The daily budget tracker in `llm_client.py` uses module-level global variables (`_daily_cost`, `_budget_date`). This means:
- Each Python process has its own budget counter
- If two gateway workers run simultaneously, each tracks only its own spend
- If the process restarts, the counter resets to zero regardless of actual spend
- There is no persistence to PostgreSQL or Redis

The budget guard will not prevent overspend in any multi-process or post-restart scenario.

---

## 6. Scalability Concerns

### 6.1 Synchronous Recursive Activation Does Not Scale

The `activate()` function in `activate.py` is synchronous and recursive. When CEO dispatches to 3 managers, each of whom dispatch to 2 workers, the call stack goes:

```
activate(ceo) → activate(manager_1) → activate(worker_1) → activate(qa_1) → ...
```

All of this happens in a single thread, sequentially. The comment in `activate.py` acknowledges this: "When CEO dispatches tasks to multiple Managers, they execute one at a time." With 10 departments each running 5 agents, you have 50 sequential LLM calls each with a 60-second timeout. A full org-wide operation could take 50 minutes just in LLM wait time.

There is no parallelism for independent subtasks. The `asyncio.gather` mentioned in the activate.py comment is planned but not implemented.

### 6.2 File System Contract Queue Does Not Scale Horizontally

`load_pending_contracts()` does a `glob("*.yaml")` on the pending directory. With 100 concurrent contracts, this is still fast. With 10,000 contracts accumulated due to a slow agent, this becomes a problem. More critically: there is no locking around contract file reads and moves. If two processes call `process_pending_contracts()` simultaneously, the same contract will be picked up twice and executed twice.

### 6.3 org.yaml Read/Write Contention

Every agent activation calls `load_org()` at least twice (once in `_determine_level()`, once in `prompt_builder.py` for context). Every `create_agent()` or `update_chain()` call does a read-modify-write cycle on `org.yaml`. With 50 active agents, this is a high-frequency unprotected YAML file that will experience read/write contention.

### 6.4 The Dispatcher and AgentOffice Engine are Disconnected

The `pipeline/dispatcher.py` uses `nexus_v1.model_router.ModelRouter` for LLM calls — a simple role-based router that maps `ceo/director/intern` to models. The `agentoffice/engine/activate.py` uses its own `llm_client.py` with per-agent `race.yaml` configs. These are two completely separate execution paths that do not share models, do not share budget tracking, and do not share audit logs. Adding a feature (like circuit breaking) to one path does not benefit the other.

### 6.5 Memory Limit of 2000 Characters is Aggressive

`MEMORY_CHAR_LIMIT = 2000` means agents can store roughly 300-400 words of working memory. For a manager tracking multiple concurrent worker assignments, this is extremely tight. The `compress_memory()` tool exists, but LLM-based compression has a cost, and calling it on every activation when memory fills up will add latency and token cost to every operation.

---

## 7. Security Gaps

### 7.1 Unix Isolation is Documented But Not Deployed

The `agents/README.md` describes a permission model: `chmod 700` on agent directories, `chmod 733` on INBOX, `chmod 444` on JD.md and TOOL.md, separate Linux user per agent. The actual file permissions on every agent directory are `drwxrwxr-x` (775) and files are `-rw-rw-r--` (664). Every file is readable and writable by any process running as user `leonard`. There is one user: `leonard`. All agents run as the same user.

The isolation model is fictional. Any agent that calls a tool allowing file reads can read any other agent's memory, JD, resume, or contracts. A backend developer could, in theory, read the CEO's MEMORY.md through a poorly constrained tool call.

### 7.2 Tool Execution Has No Sandbox

The `_execute_tool_call()` in `activate.py` maps tool names to Python functions in `_get_tool_map()`. The available tools are: `create_agent`, `remove_agent`, `create_department`, `remove_department`, `update_chain`. These are all org-management tools — no shell execution, no file read tools. The LLM cannot call arbitrary shell commands through the tool system.

However, the `agents/ceo/TOOL.md` lists `ls -R {path}` as an allowed file tool, and `send_mail.sh`, `check_inbox.sh` as communication tools. These shell scripts do not exist and are not wired into the tool map. The tool documentation does not match the tool implementation. An LLM following its TOOL.md will attempt to call tools that will fail with "Unknown tool."

### 7.3 Contract Payload is Unsanitized

The `create_contract()` function accepts a `payload` dict that is inserted directly into the YAML contract file and later injected into agent prompts via `_assemble_user_message()`. There is no sanitization of contract content before it enters an agent's system context. A malicious or corrupted contract with carefully crafted YAML could inject instruction text into an agent's system prompt. This is a prompt injection vector through the contract system.

### 7.4 The "from" Field in Contracts is Unverified

Any code can call `create_contract(from_agent="ceo", to_agent="board", ...)` and create a contract that appears to come from the CEO. The `from` field is a plain string written by the caller. There is no signing, no token, no verification that the agent claiming to send a contract is actually the agent that created it. A worker agent could create a contract that says it came from the CEO.

### 7.5 Gateway Auth is Bypassable in Dev Mode

`auth.py` line 22: "No secret configured → auth is DISABLED (dev mode)." The `settings.api_secret` is read from an environment variable. If the environment variable is not set (common in dev, possible in misconfigured prod), the gateway accepts any request from any IP without authentication. The CORS middleware also has a wildcard origins path that forces `allow_credentials=False` when present, but the code emits only a `logger.critical()` warning — it does not refuse to start.

### 7.6 The QA Runner Executes Arbitrary Commands in a Subprocess

`qa/runner.py` implements an allowlist (`ALLOWED_COMMANDS`) for subprocess execution, which is good. However, the allowlist includes `sh`, `python`, `python3`, and `bash` (via `sh`). Including a general shell interpreter in the allowlist largely defeats the purpose of the allowlist. `sh -c "rm -rf /"` would pass validation because the executable is `sh`.

---

## 8. Architectural Coherence Problems

### 8.1 Two Parallel Universes

There are effectively two systems in this repository that share a name but not architecture:

**Universe A — AgentOffice engine** (`agentoffice/`):
- Synchronous, file-based, YAML contracts
- Per-agent race.yaml model config
- company/agents/ directory structure
- Choice-state machine (finite set of next actions)
- In-process budget tracking

**Universe B — Gateway/Pipeline** (`gateway/`, `pipeline/`, `nexus_v1/`):
- Async, Redis Streams, PostgreSQL work orders
- Role-tier model routing (ceo/director/intern)
- nexus_v1/config.py model targets
- Free-form LLM responses
- DB-backed cost tracking

These two systems are not connected. A work order entering the gateway goes through Universe B. A contract created by the agentoffice engine stays in Universe A. There is no bridge between them. The gateway's `/api/chat` endpoint uses Universe B's Dispatcher, which calls ModelRouter, which has nothing to do with the organizational hierarchy in Universe A.

### 8.2 The Org Chart in org.yaml Does Not Match Runtime Agents

`org.yaml` lists `hr_lead`, `it_admin`, `eng_manager` etc. The actual agent directories in `company/agents/` contain `ceo`, `hr_lead`, `it_admin`, `eng_manager`, etc. The `agentoffice/engine` uses `company/agents/` as `AGENTS_DIR`. So far consistent.

But the `agents/` directory (the new workspace) contains `ceo`, `hr`, `it-support`, `dept-gw-manager`, `dept-gw-dev-01`, `dept-gw-qa`, `backend_dev`, `devops`, `execution`. These identifiers do not appear in `org.yaml` at all. The `hr` directory uses a different ID than `hr_lead`. The `it-support` directory uses a different ID than `it_admin`. If the engine tries to route a contract to `hr` (the INBOX-based workspace agent), it will fail because `hr` has no `race.yaml` in `company/agents/hr/` — that directory does not exist.

### 8.3 The department_creation_workflow and SOPs Describe Different Processes

`chain-of-command.yaml` has a `department_creation_workflow` section with 10 steps. `company/sops/create-department.md` has a 15-step process with a different actor sequence and different step content. These are two descriptions of the same process that are not in sync. Which one do agents follow?

---

## 9. What is Actually Working

To be fair, several things are solid:

- The `activate.py` choice-state machine design is genuinely good. Forcing LLMs into a fixed set of next actions prevents free-form hallucination of arbitrary behaviors.
- The `llm_client.py` retry logic with exponential backoff is correctly implemented.
- The `contract_manager.py` YAML contract format is clean and extensible.
- The `choice_handlers.py` level-based choice set is a correct implementation of role-based action constraints.
- The gateway's PostgreSQL/Redis infrastructure (Universe B) is production-quality.
- The QA runner spec system is a genuinely good idea.
- The context isolation in `prompt_builder.py` (CEO sees org summary, manager sees worker roster, worker sees tools) is correctly implemented for what is there.
- The heartbeat/monitor system is well-structured.

The engineering quality of individual components is good. The integration between components is the problem.

---

## 10. Priority Fix List

These are ordered by impact, not difficulty.

**P0 — Breaks correctness today**

1. **Unify the org identifier namespace.** `hr_lead` vs `hr` vs `hr.manager` must be the same string everywhere. Pick one and enforce it. Update all YAML files, all agent directories, all references.

2. **Add contract authorization check in `route_contract()`.** Before routing, verify that `contract["from"]` is in the `can_command` list of `contract["to"]`'s manager, or is the direct manager. Reject unauthorized contracts with an error contract back to sender.

3. **Validate dynamic targets against org hierarchy.** In `resolve_choice_target()`, when `target_spec == "dynamic"` and `choice_payload["to"]` is used, verify the resolved target is a valid peer or superior — not an arbitrary agent ID.

4. **Fix the budget guard to use Redis or PostgreSQL.** The in-process global is not safe. Store cumulative daily cost in Redis with a TTL key. Read before each call.

**P1 — Broken architecture that will hurt at scale**

5. **Implement file locking around org.yaml writes.** Use `fcntl.flock()` or a Redis lock. Without this, concurrent agent operations will corrupt the org structure.

6. **Separate the Dispatcher into a standalone worker process.** It should not run as a background task inside the gateway. This eliminates the gateway-kills-dispatcher failure mode.

7. **Add a persistent contract delivery mechanism.** Replace the directory scan with a file watcher (watchdog) or move contract delivery to the Redis queue. Contracts should not be lost when the process exits.

8. **Actually implement Unix isolation or remove the claim.** Either create per-agent Linux users and apply the documented permissions, or remove all references to chmod 700/733/444 from the documentation. Aspirational security documentation is more dangerous than no security documentation — it creates false confidence.

**P2 — Design debt to address before v2**

9. **Choose one pipeline architecture and deprecate the other.** Universe A (agentoffice) and Universe B (gateway/pipeline) need to converge. The most likely correct path is: agentoffice provides the organizational semantics (contracts, roles, choices), Universe B provides the infrastructure (queue, DB, monitoring). Route agentoffice contract execution through the Redis queue so it benefits from async processing.

10. **Implement basic context token accounting per agent session.** Even a simple counter in Redis (`INCR nexus:tokens:agent_id`) updated after each `call_llm()` would be a foundation for the context threshold system.

11. **Add SOP step validation as a contract chain.** Each SOP step should emit a completion marker (a contract, a DB record, a file). Subsequent steps check for the prior step's marker. This does not require building a full BPM engine — a simple prerequisite contract type is enough.

12. **Sanitize contract payloads before prompt injection.** Strip or escape any text that looks like system prompt instructions (common patterns: "Ignore previous instructions", "You are now", markdown headers that could be confused with system prompt sections).

---

## Summary Assessment

| Area | Status | Severity |
|---|---|---|
| Hierarchy definition | Defined in two conflicting files | HIGH |
| Permission enforcement | Not implemented in code | CRITICAL |
| Communication protocol | Two incompatible systems | HIGH |
| Message bus | File system scan, no real bus | MEDIUM |
| SOP enforcement | Documentation only | HIGH |
| Context tracking | Completely absent | HIGH |
| CEO fallback | None | MEDIUM |
| Worker bypass prevention | Not enforced | CRITICAL |
| Unix isolation | Documented but not deployed | CRITICAL |
| Budget guard reliability | Process-local only | HIGH |
| Contract authorization | No signing, no verification | CRITICAL |
| Concurrent write safety | No locking on org.yaml | HIGH |
| Parallel execution | Sequential only, by design for now | MEDIUM |
| Gateway/AgentOffice bridge | Non-existent | HIGH |
| Prompt injection prevention | None | HIGH |

NEXUS at 3 days old has the right ideas in the right places. The organizational metaphor is sound. The choice-state machine is the right approach for constraining LLM behavior. The context isolation concept is correct. What it lacks is the connective tissue: enforcement, locking, authorization, persistence, and most critically, honesty about what is actually running versus what is documented as the vision.

The recommendation is not to stop — it is to spend one focused pass auditing what is real versus what is aspirational, removing or clearly marking aspirational documentation, and implementing the P0 items before adding any more features.
