# SOP: Add Tool / Equipment

**Owner**: IT Team  
**Trigger authority**: CEO, any peer manager  
**File path**: `company/sops/add-tool.md`

---

## Trigger Conditions

- CEO directive, OR
- Peer manager tool request (via contract to IT manager)

## Steps

1. Receive tool requirements (name, purpose, target department, constraints)
2. Search GitHub / tools marketplace for candidate packages
3. Evaluate candidates:
   - Compatibility with current system stack
   - Security: license, maintainer reputation, last commit date
   - Dependencies: conflicts with existing tools
4. Select best candidate, document decision rationale
5. Install and configure in appropriate environment
6. Write tool spec to `equipment/{tool_id}.yaml`
7. Run integration test in sandbox
8. On PASS: notify requester with tool ID and usage instructions
9. Log installation to `logs/it-activity.log`

## Approval Requirements

| Action | Requires Approval |
|---|---|
| Add new tool | No — IT manager decides |
| System-wide upgrade | Yes — CEO approval required |
| Hardware purchase | Yes — Board approval required |
| External API key / paid service | Yes — CEO approval required |

## Equipment Spec Format

```yaml
# equipment/{tool_id}.yaml
tool_id: "example_tool"
name: "Example Tool"
version: "1.2.3"
installed_by: "it_manager"
installed_date: "2026-02-19"
purpose: "What this tool does"
departments_using:
  - hr
  - engineering
config_path: "equipment/configs/example_tool.conf"
docs_url: "https://github.com/example/tool"
status: "active"
```

## Output Files

- `equipment/{tool_id}.yaml` — Tool specification and config reference
- `logs/it-activity.log` — Timestamped installation record
