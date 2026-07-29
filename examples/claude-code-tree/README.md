# Claude Code Session-Tree Fixture

This synthetic, content-marked fixture exercises
`source.claude-code-session-tree@1`.

```text
session.jsonl
session/subagents/agent-child-001.jsonl
session/subagents/agent-child-001.meta.json
```

The parent delegates one task through the `Agent` tool. The child transcript
contains a fork bootstrap envelope, two actual model calls, and one `Read` call.
The adapter verifies the envelope without counting the repeated parent call twice.

Run the complete conversion and decision:

```bash
make claude-code-tree
```

Expected evidence:

```text
3 source files
1 root task
1 expanded subagent
4 model calls
2 tool calls
6 dependency edges
SCALE
```

All prompt, response, thinking, result, argument, path, session, agent, and metadata
secret markers are fake. Their purpose is to prove that generated artifacts do
not leak source content.
