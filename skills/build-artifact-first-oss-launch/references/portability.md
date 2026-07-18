# Skill Portability

The core package follows the Agent Skills `SKILL.md` convention and uses only the
portable `name` and `description` frontmatter fields. The `agents/openai.yaml` file
is optional Codex UI metadata; other agents may ignore it.

## Codex

For a personal installation, copy the entire skill directory to:

```text
${CODEX_HOME:-~/.codex}/skills/build-artifact-first-oss-launch/
```

Restart or refresh skill discovery if required, then invoke:

```text
$build-artifact-first-oss-launch
```

For a repository handoff, keep the skill in version control and tell Codex to read
its `SKILL.md` completely before acting.

## Claude Code

For a project installation, copy the directory to:

```text
.claude/skills/build-artifact-first-oss-launch/
```

For a personal installation, use:

```text
~/.claude/skills/build-artifact-first-oss-launch/
```

Invoke it directly with:

```text
/build-artifact-first-oss-launch
```

Claude Code can also discover it automatically from the description. Keep all
supporting files beside `SKILL.md`; the relative links intentionally work in both
Claude and Codex layouts.

## Generic agent or chat model

If the product has no skill discovery:

1. attach or expose the whole directory;
2. send: “Read `SKILL.md` completely and follow it as the operating procedure for
   this task”;
3. provide only the references named by `SKILL.md` when context is limited; and
4. require the output contract in the final section of `SKILL.md`.

If file attachments are unavailable, paste `SKILL.md`, then paste the requested
reference files. Do not paste every asset into context; copy templates only when
producing the corresponding deliverable.

## Agents with and without delegation

If multiple independent agents or subagents are available, use the three reviewer
briefs and require cross-critique. If delegation is unavailable, run the briefs
sequentially in isolated sections, hide each draft while producing the next when
possible, and synthesize only after all three exist.

## Expected limitations

- The skill cannot guarantee traction, revenue, market novelty, or production
  safety.
- Market and competitor statements require current source verification.
- Repository mutation, publishing, profile edits, and external messages remain
  governed by the host agent's permissions and confirmation rules.
- A generic chat model without filesystem or command tools can produce the audit
  and copy but cannot validate executable claims.
