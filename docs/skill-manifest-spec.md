# Skill Manifest Specification

Version: 1.0.0

## Overview

Every Nexus skill must include a `manifest.yaml` at its repository root. This file declares the skill's metadata, dependencies, capabilities, and agent assignment rules. The Nexus Skill Manager reads this file during installation to automate the onboarding process.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique identifier for the skill (lowercase, hyphens allowed) |
| `version` | string | Semantic version (e.g. `1.0.0`) |
| `entry_point` | string | Relative path to the main executable (`server.py`, `index.js`) |
| `type` | string | One of: `mcp-server`, `skill-file`, `plugin` |

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | `""` | Human-readable description |
| `author` | string | `""` | Author name or organization |
| `category` | string | `""` | Skill category (e.g. `git`, `database`, `monitoring`) |
| `license` | string | `""` | SPDX license identifier |

## Install Block

```yaml
install:
  runtime: "python"       # "python" or "node"
  dependencies:           # List of package specifiers
    - "pygithub>=2.0"
    - "requests"
```

If `install` is not provided, the manager will look for `requirements.txt` (Python) or `package.json` (Node.js) in the skill root.

## Capabilities

```yaml
capabilities:
  - "git_operations"
  - "pr_management"
  - "issue_tracking"
```

Capabilities are free-form strings that describe what the skill can do. They are injected into the agent's TOOL.md so the agent knows what tools are available.

## Department Assignment

```yaml
compatible_departments:
  - engineering
  - devops

auto_assign_to:
  - devops
  - backend_dev
```

- `compatible_departments`: Departments where this skill is relevant. Used for discovery.
- `auto_assign_to`: Agent roles that will automatically receive this skill's tools in their TOOL.md upon installation.

The assignment logic:
1. If `auto_assign_to` is set, find agents matching those roles.
2. Otherwise, fall back to all agents in `compatible_departments`.

## Skill Types

### mcp-server
A Model Context Protocol server that exposes tools via stdio or HTTP.

```yaml
type: "mcp-server"
entry_point: "server.py"
mcp:
  transport: "stdio"      # "stdio" or "http"
  port: 8080              # Only for http transport
```

### skill-file
A standalone script or module that provides utility functions.

```yaml
type: "skill-file"
entry_point: "main.py"
```

### plugin
A plugin that extends Nexus core functionality.

```yaml
type: "plugin"
entry_point: "plugin.py"
hooks:
  - "on_task_assigned"
  - "on_task_completed"
```

## Full Example

```yaml
name: "github-mcp"
version: "1.0.0"
description: "GitHub operations via MCP — create PRs, manage issues, review code"
author: "nexus-community"
category: "git"
license: "MIT"
entry_point: "server.py"
type: "mcp-server"
install:
  runtime: "python"
  dependencies:
    - "pygithub>=2.0"
    - "mcp>=0.1.0"
capabilities:
  - "git_operations"
  - "pr_management"
  - "issue_tracking"
  - "code_review"
compatible_departments:
  - engineering
  - devops
auto_assign_to:
  - devops
  - backend_dev
  - frontend_dev
mcp:
  transport: "stdio"
```

## Validation Rules

The `nexus-skill validate <name>` command checks:

1. `manifest.yaml` exists and is valid YAML
2. All required fields are present
3. `entry_point` file exists
4. `type` is one of the recognized types
5. `version` follows semver format
6. Dependencies are installable (dry-run check)
7. At least one capability is defined (warning if missing)
8. At least one department or agent assignment is configured (warning if missing)
