# AgentOffice End-to-End Test Report

Date: 2026-02-16
Tester: QA Agent (Task 08)

## Test Results Overview

| Phase | Description | Result |
|-------|-------------|--------|
| 1     | Environment Preparation | PASS (with note) |
| 2     | CEO Initiates Project | PASS |
| 3     | CEO Distributes Task | PASS (with bug) |
| 4     | Manager Decomposes and Assigns | PASS (with bug) |
| 5     | Worker Executes | PASS |
| 6     | QA Verification | PASS |
| 7     | Manager Reports to CEO | PASS |

**Overall: 7/7 Phases PASS** (2 bugs found, 1 environment note)

---

## Detailed Results

### Phase 1: Environment Preparation

**Step 1: Confirm base structure exists**
- Command: `ls agents/ceo/ agents/hr/ agents/it-support/`
- Result: **PASS**
- Output: All three directories exist with expected contents (INBOX, JD.md, MEMORY.md, TOOL.md). `it-support` also has `install_log.md`.

**Step 2: Confirm scripts are executable**
- Command: `ls -la agents/scripts/*.sh`
- Result: **PASS**
- Output: All 16 scripts found with `-rwxr-xr-x` permissions:
  - `check_inbox.sh`, `create_agent.sh`, `create_contract.sh`, `delete_agent.sh`
  - `inbox_watcher.sh`, `install_tool.sh`, `list_contracts.sh`, `orchestrator.sh`
  - `read_mail.sh`, `remove_tool.sh`, `search_tool.sh`, `send_mail.sh`
  - `start_agent.sh`, `stop_agent.sh`, `update_contract.sh`, `write_memory.sh`

**Step 3: Confirm registry exists**
- Command: `cat agents/registry.yaml`
- Result: **NOTE** - `registry.yaml` does not pre-exist. File is created dynamically by `create_agent.sh` on first agent creation. This is by design (confirmed by reading script source). No pre-seeded entries for ceo, hr, or it-support in registry.
- Severity: Low - The built-in agents (ceo, hr, it-support) are not registered in registry.yaml. This means `registry.yaml` is incomplete as an organizational source of truth until agents are dynamically created.

---

### Phase 2: CEO Initiates Project

**Step 4: CEO sends hiring email to HR**
- Command: `echo "..." | agents/scripts/send_mail.sh ceo hr hire create-gateway-dept`
- Result: **PASS**
- Output: `Mail sent: hr/INBOX/20260216_180342_ceo_hire_create-gateway-dept.md`

**Step 5: HR checks inbox**
- Command: `agents/scripts/check_inbox.sh hr`
- Result: **PASS**
- Output: `2026-02-16 18:03:42  ceo  hire  create-gateway-dept  [UNREAD]`

**Step 6: HR reads mail**
- Command: `agents/scripts/read_mail.sh hr 20260216_180342_ceo_hire_create-gateway-dept.md`
- Result: **PASS**
- Output: Correctly formatted mail with headers (FROM, TO, TYPE, PRIORITY, TIMESTAMP) and body. Mail was moved to `INBOX/read/` directory after reading. `[Marked as read]` confirmation displayed.

**Step 7: HR creates Manager**
- Command: `agents/scripts/create_agent.sh dept-gw-manager manager dept-gateway ceo`
- Result: **PASS**
- Output: Agent created with ID `dept-gw-manager`, role `manager`, department `dept-gateway`, reports_to `ceo`, model `opus`. Registry initialized.

**Step 8: HR creates Worker**
- Command: `agents/scripts/create_agent.sh dept-gw-dev-01 worker dept-gateway dept-gw-manager`
- Result: **PASS**
- Output: Agent created with ID `dept-gw-dev-01`, role `worker`, department `dept-gateway`, reports_to `dept-gw-manager`, model `sonnet`. WORKSPACE directory created.

**Step 9: HR creates QA**
- Command: `agents/scripts/create_agent.sh dept-gw-qa qa dept-gateway dept-gw-manager`
- Result: **PASS**
- Output: Agent created with ID `dept-gw-qa`, role `qa`, department `dept-gateway`, reports_to `dept-gw-manager`, model `sonnet`. WORKSPACE directory created.

**Step 10: Verify registry updated**
- Command: `cat agents/registry.yaml`
- Result: **PASS**
- Output: Registry contains all 3 new agents with correct roles, department assignments, reporting relationships. Department `dept-gateway` section correctly lists manager and members.

**Step 11: Verify directory structure**
- Command: `ls agents/dept-gw-manager/ agents/dept-gw-dev-01/ agents/dept-gw-qa/`
- Result: **PASS**
- Output:
  - `dept-gw-manager/`: INBOX, JD.md, MEMORY.md, TOOL.md (no WORKSPACE - correct for manager role)
  - `dept-gw-dev-01/`: INBOX, JD.md, MEMORY.md, TOOL.md, WORKSPACE (correct for worker)
  - `dept-gw-qa/`: INBOX, JD.md, MEMORY.md, TOOL.md, WORKSPACE (correct for qa)
- JD.md files verified: Each contains role-appropriate job description with correct reporting relationships and permissions.

---

### Phase 3: CEO Distributes Task

**Step 12: CEO creates Contract**
- Command: `echo '{...}' | agents/scripts/create_contract.sh ceo dept-gw-manager`
- Result: **PASS**
- Output: `Contract created: CTR-20260216-001`
- Contract file verified at `agents/contracts/CTR-20260216-001.md` with correct fields: ID, FROM (ceo), TO (dept-gw-manager), STATUS (pending), all JSON fields properly mapped to markdown sections.
- Contract also delivered as symlink/copy to `dept-gw-manager/INBOX/CTR-20260216-001.md`.

**Step 13: CEO sends notification to Manager**
- Command: `echo "..." | agents/scripts/send_mail.sh ceo dept-gw-manager contract new-task`
- Result: **PASS**
- Output: `Mail sent: dept-gw-manager/INBOX/20260216_180516_ceo_contract_new-task.md`

**Step 14: Manager checks inbox**
- Command: `agents/scripts/check_inbox.sh dept-gw-manager`
- Result: **PASS (with BUG)**
- Output:
  ```
  CTR--20-26 CT:R-:20  CTR-20260216-001  CTR-20260216-001  CTR-20260216-001  [UNREAD]
  2026-02-16 18:05:16  ceo  contract  new-task  [UNREAD]
  ```
- **BUG-001**: The contract file `CTR-20260216-001.md` delivered to the inbox causes garbled display output. See Issues section for details.

---

### Phase 4: Manager Decomposes and Assigns

**Step 15: Manager creates sub-Contract for Worker**
- Command: `echo '{...}' | agents/scripts/create_contract.sh dept-gw-manager dept-gw-dev-01 --parent CTR-20260216-001`
- Result: **PASS**
- Output: `Contract created: CTR-20260216-001-A`
- Sub-contract correctly references parent `CTR-20260216-001`. ID format uses alphabetic suffix (`-A`). File verified with all fields correct.

**Step 16: Worker checks inbox**
- Command: `agents/scripts/check_inbox.sh dept-gw-dev-01`
- Result: **PASS (with BUG)**
- Output: `CTR--20-26 CT:R-:20  CTR-20260216-001-A  CTR-20260216-001-A  CTR-20260216-001-A  [UNREAD]`
- Same BUG-001 as Step 14: contract file causes garbled check_inbox.sh output.

---

### Phase 5: Worker Executes (simulated)

**Step 17: Worker writes code in WORKSPACE**
- Created `agents/dept-gw-dev-01/WORKSPACE/app.py`: Python HTTP server using `http.server` module, returns `{"message": "Hello World"}` on `GET /`.
- Created `agents/dept-gw-dev-01/WORKSPACE/test_app.py`: Pytest test that starts server on port 18080, sends GET request, verifies 200 status and correct JSON response.
- Result: **PASS**

**Step 18: Worker sends completion report to Manager**
- Command: `echo "..." | agents/scripts/send_mail.sh dept-gw-dev-01 dept-gw-manager report task-complete`
- Result: **PASS**
- Output: `Mail sent: dept-gw-manager/INBOX/20260216_180636_dept-gw-dev-01_report_task-complete.md`

**Step 19: Update sub-Contract status to review**
- Required two transitions due to state machine enforcement (pending -> in_progress -> review):
  - `update_contract.sh CTR-20260216-001-A in_progress` -- **PASS**: `pending -> in_progress`
  - `update_contract.sh CTR-20260216-001-A review` -- **PASS**: `in_progress -> review`
- Status change records properly appended to contract file with timestamps and notes.
- Result: **PASS**

---

### Phase 6: QA Verification (simulated)

**Step 20: Manager sends verification request to QA**
- Command: `echo "..." | agents/scripts/send_mail.sh dept-gw-manager dept-gw-qa review verify-output`
- Result: **PASS**
- Output: `Mail sent: dept-gw-qa/INBOX/20260216_180714_dept-gw-manager_review_verify-output.md`

**Step 21: QA checks the code**
- Import test: `python3 -c "import app; print('import OK')"` -- **PASS**: `import OK`
- Unit test: `python3 -m pytest test_app.py -v` -- **PASS**: `1 passed` in 0.57s
  - Note: `pytest` was not pre-installed in the environment (had to be installed via pip). This is an environment setup concern, not a script bug.
- Result: **PASS**

**Step 22: QA sends verification result**
- Command: `echo "..." | agents/scripts/send_mail.sh dept-gw-qa dept-gw-manager result review-passed`
- Result: **PASS**
- Output: `Mail sent: dept-gw-manager/INBOX/20260216_180800_dept-gw-qa_result_review-passed.md`

**Step 23: Update sub-Contract to passed**
- Command: `update_contract.sh CTR-20260216-001-A passed`
- Result: **PASS**: `review -> passed`
- Status change record appended with note.

---

### Phase 7: Manager Reports to CEO

**Step 24: Manager sends report to CEO**
- Command: `echo "..." | agents/scripts/send_mail.sh dept-gw-manager ceo report dept-task-complete`
- Result: **PASS**
- Output: `Mail sent: ceo/INBOX/20260216_180824_dept-gw-manager_report_dept-task-complete.md`
- Mail content verified: correctly formatted with headers and body.

**Step 25: Update parent Contract to passed**
- Required three transitions (pending -> in_progress -> review -> passed):
  - `update_contract.sh CTR-20260216-001 in_progress` -- **PASS**
  - `update_contract.sh CTR-20260216-001 review` -- **PASS**
  - `update_contract.sh CTR-20260216-001 passed` -- **PASS**
- All status change records properly appended to contract file.

**Step 26: CEO checks final state**
- CEO inbox: `agents/scripts/check_inbox.sh ceo` -- **PASS**
  - Shows: `2026-02-16 18:08:24  dept-gw-manager  report  dept-task-complete  [UNREAD]`
- Contract listing: `agents/scripts/list_contracts.sh --status passed` -- **PASS**
  - Output:
    ```
    ID                   FROM              TO                STATUS   DEADLINE
    --------------------------------------------------------------------------
    CTR-20260216-001-A   dept-gw-manager   dept-gw-dev-01    passed   (none)
    CTR-20260216-001     ceo               dept-gw-manager   passed   (none)
    ```
- Both contracts correctly show `passed` status.

**Additional verification: Invalid state transition**
- Command: `update_contract.sh CTR-20260216-001 in_progress` (attempt to re-open passed contract)
- Result: **PASS** (correctly rejected): `Error: Invalid transition 'passed' -> 'in_progress'. (terminal state -- no transitions allowed)`

---

## Verification Checklist

| Check | Result | Notes |
|-------|--------|-------|
| Mail delivery: target INBOX has the file | PASS | All 6 mail messages delivered to correct INBOX directories |
| Mail format: correct headers and body | PASS | All mails have FROM, TO, TYPE, PRIORITY, TIMESTAMP headers + body |
| Mail read mechanism: moved to read/ | PASS | read_mail.sh moves file to INBOX/read/ subdirectory |
| Agent creation: directory complete | PASS | All directories created with correct files (INBOX, JD.md, MEMORY.md, TOOL.md, WORKSPACE where applicable) |
| Agent creation: JD.md correct | PASS | Each JD contains role-appropriate description with correct reporting relationships |
| Agent creation: registry updated | PASS | registry.yaml created and updated with all 3 agents and department structure |
| Contract flow: ID format correct | PASS | Parent: CTR-YYYYMMDD-NNN, Sub: CTR-YYYYMMDD-NNN-A |
| Contract flow: state transitions legal | PASS | State machine enforces pending->in_progress->review->passed; terminal states properly locked |
| Contract flow: change log appended | PASS | Each status change appends timestamped record with FROM, TO, and optional NOTE |
| File isolation: Worker files only in WORKSPACE | PASS | app.py and test_app.py only exist in agents/dept-gw-dev-01/WORKSPACE/ |

---

## Issues Found

### BUG-001: check_inbox.sh garbled output for contract files in INBOX (Severity: Medium)

**Description:** When `create_contract.sh` delivers a contract to an agent's INBOX, it places a file named `CTR-20260216-001.md` (or similar) directly in the INBOX directory. When `check_inbox.sh` lists the inbox, it iterates over all `*.md` files and parses them assuming the filename format `YYYYMMDD_HHMMSS_from_type_subject.md`. Contract filenames like `CTR-20260216-001.md` do not follow this convention, causing the `cut -d'_'` field extraction to produce garbled output.

**Reproduction:**
1. Create a contract assigned to an agent (e.g., `create_contract.sh ceo dept-gw-manager`)
2. Run `check_inbox.sh dept-gw-manager`
3. Observe garbled first line: `CTR--20-26 CT:R-:20  CTR-20260216-001  CTR-20260216-001  CTR-20260216-001  [UNREAD]`

**Root Cause:** In `check_inbox.sh`, the `parse_and_print()` function (lines 115-157) assumes all `.md` files in INBOX follow the mail filename convention. Contract files use a different naming pattern (`CTR-YYYYMMDD-NNN.md` with hyphens, not underscores for separating timestamp parts), so `cut -d'_' -f1` through `-f5` extract wrong fields.

**Expected Behavior:** Either:
- (a) `check_inbox.sh` should skip or specially handle files matching the contract pattern `CTR-*.md`, or
- (b) `create_contract.sh` should not deliver contract files directly to INBOX (use mail notification only), or
- (c) Contract files delivered to INBOX should follow the mail filename convention.

**Affected Steps:** Step 14, Step 16 (any agent with a contract in INBOX).

---

### NOTE-001: registry.yaml not pre-initialized (Severity: Low)

**Description:** The `agents/registry.yaml` file does not exist until the first call to `create_agent.sh`. The three built-in agents (ceo, hr, it-support) are not registered in the registry. This means the registry is incomplete as an organizational directory - it only tracks dynamically created agents.

**Impact:** Any tooling that relies on registry.yaml to discover all agents will miss ceo, hr, and it-support. This could cause issues for orchestration scripts or auditing.

---

### NOTE-002: pytest not pre-installed in environment (Severity: Low)

**Description:** The test environment does not have `pytest` installed. Running `python3 -m pytest` fails with `No module named pytest`. This was resolved by installing pytest via pip, but in a real agent execution scenario, the Worker or QA agent would need IT Support to install testing tools first.

**Impact:** The IT Support tool installation flow (via `install_tool.sh`) was not exercised in this test scenario. In a complete workflow, the Manager should request tool installation before assigning coding tasks.

---

## Recommendations

1. **Fix BUG-001 (check_inbox.sh contract file handling):** Add a filename pattern check in `parse_and_print()` to skip or specially format files that don't match the `YYYYMMDD_HHMMSS_*` mail convention. Alternatively, refactor contract delivery to not place raw contract files in the INBOX -- use a dedicated notification mail instead.

2. **Pre-initialize registry.yaml:** Create `registry.yaml` during system bootstrap with entries for the three built-in agents (ceo, hr, it-support). This ensures the registry is always a complete organizational directory.

3. **Add tool dependency management to workflow:** Before a Manager assigns coding/testing tasks, the workflow should include a step where the Manager requests IT Support to verify/install required tools (python3, pytest, etc.) for Worker and QA agents.

4. **Add contract read support to read_mail.sh:** Currently `read_mail.sh` only handles mail files. Consider adding support for reading contract files delivered to INBOX, or provide a separate `read_contract.sh` command.

5. **Consider adding mail notification for contract state changes:** When a contract status changes (e.g., to `passed` or `failed`), automatically send a notification mail to the contract parties. Currently, status updates are silent -- agents must manually check contract files.

6. **Add parent-child contract status coordination:** When all sub-contracts of a parent are `passed`, consider automatically transitioning the parent to `review` status, or at least sending a notification to the parent contract owner.

7. **Add idempotency checks:** `send_mail.sh` with the same subject creates duplicate files with different timestamps. Consider adding deduplication or message IDs for reliable communication.
