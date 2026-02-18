# SOP: Create New Department

**Owner**: HR Team (execution) / CEO (authority) / Board (final approval if budget involved)  
**Trigger authority**: CEO only  
**File path**: `company/sops/create-department.md`

---

## Trigger Conditions

- CEO identifies a capability gap that requires a new department
- Only CEO can initiate this workflow

## Steps

| Step | Actor | Action |
|---|---|---|
| 1 | CEO | Identify capability gap, define department purpose |
| 2 | CEO | Dispatch Project Manager to investigate |
| 3 | PM | Research required workflow, tools, agent roles |
| 4 | PM | Deliver project plan to CEO (tools list, JD specs, timeline) |
| 5 | CEO | Review plan, request revisions if needed |
| 6 | CEO | Send tool requirements contract to IT |
| 7 | CEO | Send agent JD specs contract to HR |
| 8 | CEO | Request Board approval if budget or hardware needed |
| 9 | IT | Source and install required tools |
| 10 | HR | Generate department config in `company/departments/{dept_id}.yaml` |
| 11 | HR | Generate all agent JDs in `agents/jds/` |
| 12 | HR | Update `company/org.yaml` |
| 13 | HR | Update `company/chain-of-command.yaml` |
| 14 | CEO | Activate department, notify all stakeholders |
| 15 | Manager | Begin operations (solo if light load, request workers as needed) |

## Approval Requirements

| Scenario | Requires Approval |
|---|---|
| Department creation (no budget) | CEO |
| Department creation (requires tools) | CEO + IT sourcing |
| Department creation (budget / hardware) | Board |
| Department creation (external contractors) | Board |

## Output Files

- `company/departments/{dept_id}.yaml` — Department configuration
- `agents/jds/{manager_id}.md` — Department manager JD
- `agents/jds/{worker_id}.md` — Worker JDs (one per initial headcount)
- `company/org.yaml` — Updated with new department
- `company/chain-of-command.yaml` — Updated with new reporting lines
- `logs/hr-activity.log` — Timestamped department creation record

## Department Config Format

```yaml
# company/departments/{dept_id}.yaml
dept_id: "example_dept"
name: "Example Department"
type: "dynamic"
status: "active"
created: "2026-02-19"
created_by: "ceo"
manager: "example_manager"
level: 2
reports_to: "ceo"
description: "What this department does"
headcount:
  total: 2
  manager: 1
  workers: 1
tools:
  - tool_id: "example_tool"
sops:
  - "company/sops/example-workflow.md"
```
