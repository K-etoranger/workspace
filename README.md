# Workspace

A sample of a personal "Workspace": one folder on one Mac where AI coding agents (Claude Code and Codex) and scheduled jobs keep a person's memory, tasks and tools in order.

This repository is a small copy of a real Workspace. The code and the rules are copied from the real one. Everything personal was replaced with fiction: the owner here is a made-up person, "Taro Yamada" (`/Users/taro`), and the memory files describe his invented week.

**Most of the content is in Japanese**, because the real Workspace runs in Japanese: the rules the agents read, the prompts of the scheduled jobs, the code comments and the sample memory. This page explains the ideas in English. The Japanese map of the folders is [README.ja.md](README.ja.md).

## The ideas

- **One place.** All work, data, memory and tools live inside one folder. Anything outside it that may be touched is listed in `config/external_paths.json`, and a check counts paths that point anywhere else.
- **Memory is plain Markdown, written through one door.** `SecondBrain/` holds only `.md` files, in numbered layers (inbox, daily notes, identity, projects, tasks, media, distilled notes, logs). Agents and jobs read it freely but write only through the `sb` CLI, which checks the shape of every file before writing and refuses secrets and writes into places the company-confidential gate forbids.
- **One system, one repo.** Each tool is its own repo under `src/`. A repo may use the `sb` commands, its own folder in `data/`, `models/` and `config/`, and nothing from another repo. Each `data/` folder has exactly one writer, declared in that repo's README.
- **Maps are generated, not written.** The READMEs that list repos, data folders, models and logs are built from each repo's README and launchd files by `workspace-index`, which also reports anything that breaks the rules above.
- **Agents follow written rules.** One shared rule book (`src/agent-setup/rules/AGENTS.md`) tells every agent how to answer, when to ask before changing things, never to invent values, and where to work. Claude Code and Codex read the same file. Each repo keeps its own skills, hooks and scheduled agent jobs next to its code. What only one agent uses lives in a `<agent>-setup` repo (here `src/claude-setup/`), so the shared parts never depend on one agent. `src/agents/` holds none of them and only collects and deploys them.
- **Change happens in `work/`.** New things are built in `work/`, and existing repos are changed in git worktrees there. Nothing runs from `work/`, and nothing reaches the live branch without the owner's approval.

## What is inside

| Folder | What it is |
|---|---|
| `SecondBrain/` | The memory: fictional sample notes, tasks and a generated `NOW.md` (today's view) |
| `sb/` | The CLI that reads and writes `SecondBrain/` (Python 3.9+, standard library only) |
| `src/agent-setup/` | What every agent shares: the rule book and a hook that stops agents from using temp folders outside the Workspace |
| `src/claude-setup/` | What only Claude Code uses: the entry file that loads the shared rule book, and the base settings |
| `src/agents/` | Collects every repo's agent rules, settings, hooks, skills and scheduled agent jobs and deploys them to `~/.claude` and `~/.codex` |
| `src/workspace-index/` | Builds the map READMEs and checks the Workspace rules |
| `src/workspace-history/` | Records changes to the hand-written files in git every hour |
| `src/jobs/` | Installs every repo's launchd jobs on the Mac |
| `src/memory-search/` | Cuts the Markdown into chunks and builds full-text and embedding indexes |
| `src/memory-recall/` | Finds memories related to what the owner just said and adds them to the agent's context |
| `src/taskizer/` | Reads new messages in the inbox and turns only the ones that need action into tasks |
| `config/` | Workspace-wide settings (fake values here) |
| `data/`, `models/`, `logs/`, `company/`, `work/` | Only their READMEs and empty folders. In the real Workspace they hold data, model files, logs, the employer's material and work in progress |

## Try it

```sh
export SB_WORKSPACE="$PWD"
python3 sb/bin/sb task list                 # the sample tasks
python3 sb/bin/sb day --json                # today's "logical day" (a day ends at 05:00 Asia/Tokyo)
cat SecondBrain/NOW.md                      # today's view, generated from the tasks
```

Writing is refused until the company-confidential gate points at your copy: set `local_only_source_paths` in `config/company_confidential.json` to `<this folder>/company`. Then, for example:

```sh
python3 sb/bin/sb task new --title "Water the tomatoes" --owner 本人 --due 2026-10-20 --by 本人
python3 sb/bin/sb views refresh --by sb/views-refresh
```

Each repo's README has a "試験" (tests) section with the command to run its tests. `memory-search` and `memory-recall` need an index and models (see `models/`), so search does not run in this copy as it is.

## License

[MIT](LICENSE)
