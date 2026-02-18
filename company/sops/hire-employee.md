# SOP: Hire New Employee

**Owner**: HR Team  
**Trigger authority**: CEO, any peer manager, or auto-trigger on context alert  
**File path**: `company/sops/hire-employee.md`

---

## Trigger Conditions

- CEO directive, OR
- Peer manager staffing request, OR
- Context alert (auto-trigger when any agent context > 80%)

## Steps

1. Receive role requirements (skills, tools, department, reason for hire)
2. Generate JD using RACE profile template (`company/templates/jd-template.md`)
3. Write JD to `agents/jds/{agent_id}.md`
4. Register agent in `company/org.yaml` under correct department
5. If replacing manager workload: execute Training & Handoff Protocol (see below)
6. Notify requester with agent ID and JD path

## Training & Handoff Protocol

When a manager offloads execution work to a new hire:

1. Manager extracts execution-level content from own JD.md (task logs, step-by-step details)
2. Manager writes training section into new worker's JD.md
3. New worker executes one test task under observation
4. Manager QA-checks result
5. On PASS: Manager deletes transferred content from own JD.md and work records
6. Manager context freed, returns to pure management role (~35% context usage target)
7. Log handoff completion to `logs/handoffs.log`

## Approval Requirements

| Action | Requires Approval |
|---|---|
| Hire new employee | No — any manager can request |
| Create new department | Yes — CEO approval required |
| Onboard external contractor | Yes — Board approval required |

## Output Files

- `agents/jds/{agent_id}.md` — Job description and operating instructions
- `company/org.yaml` — Updated org chart entry
- `logs/hr-activity.log` — Timestamped record of hire action
