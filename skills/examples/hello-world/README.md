# Hello World Skill

A minimal example skill for the Nexus AI-Team platform. Use this as a template when creating new skills.

## What it does

- `hello_greet` — Greet someone by name
- `hello_echo` — Echo back an input message

## Install

```bash
python tools/nexus_skill.py install ./skills/examples/hello-world
```

## Structure

```
hello-world/
  manifest.yaml   # Skill metadata and configuration
  server.py       # MCP server (stdio transport)
  README.md       # This file
```

## Creating Your Own Skill

1. Copy this directory as a template
2. Edit `manifest.yaml` with your skill's metadata
3. Replace `server.py` with your implementation
4. Test with `nexus-skill install <path>` then `nexus-skill validate <name>`
