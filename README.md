# CodeGraph

AST-based code knowledge graph. Parses source code across 10 languages, builds a Neo4j graph of classes, functions, endpoints, DB models, imports, and call chains — then exposes it all via MCP for Claude.

## Why

Documentation gets outdated. Code doesn't. CodeGraph lets you query business logic directly from source code.

## What it extracts

**13 node types**: Repository, Service, File, Module, Class, Function, Variable, Endpoint, DatabaseTable, Event, ExternalAPI, BusinessRule, PullRequest

**16 relationship types**: CONTAINS_FILE, DEFINES, CONTAINS, HAS_METHOD, HAS_FIELD, EXTENDS, IMPLEMENTS, CALLS, CALLS_EXTERNAL, EXPOSES, HANDLED_BY, READS_FROM, WRITES_TO, PUBLISHES, SUBSCRIBES_TO, IMPORTS, TOUCHED_FILE

## Supported languages

Swift, Kotlin, PHP, Python, JavaScript, TypeScript, Go, Dart, C#

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker

### Install

```bash
git clone https://github.com/mustafo/CodeGraph.git
cd CodeGraph
uv sync
```

### Start Neo4j

```bash
docker compose up -d
```

Neo4j Browser: http://localhost:7474 (neo4j / codegraph)

## Usage

### Index repositories

```bash
# Single repo
uv run main.py index /path/to/your-repo

# With a custom name
uv run main.py index /path/to/your-repo --name my-service

# Multiple repos
uv run main.py index \
  /path/to/repo-one --name backend \
  /path/to/repo-two --name mobile
```

Indexing is incremental by default — only changed files get re-parsed.

### Re-index all

```bash
uv run reindex.py
```

Re-indexes every previously indexed repo (incremental).

### Index pull requests (Forgejo)

Links each PR to the `File` nodes it touched, in the same graph. Run *after*
`main.py index` so the `File` nodes exist.

```bash
export FORGEJO_URL=http://127.0.0.1:3000
export FORGEJO_TOKEN=<token>
uv run index_prs.py --repo owner/name --state all
```

`--state` is `all` (default), `open`, or `closed`. PRs link to `File` nodes by
`File.repo`; `graph_repo` defaults to the full `owner/name` of `--repo` (how
repos are indexed here) and the indexer warns if no `File` nodes exist for it —
pass `--graph-repo NAME` to override when a repo was indexed under a different
name. Then query the links:

```cypher
MATCH (pr:PullRequest)-[:TOUCHED_FILE]->(f:File)
RETURN pr.number, f.file_path LIMIT 10
```

Re-running is idempotent: PRs merge on their id, and each PR's `TOUCHED_FILE`
edges are rebuilt from its current file set.

### MCP server (Claude Desktop)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "code-graph": {
      "command": "uv",
      "args": ["--directory", "/path/to/CodeGraph", "run", "main.py"]
    }
  }
}
```

### MCP server (Claude Code)

```bash
claude mcp add --transport stdio -s user code-graph -- uv --directory /path/to/CodeGraph run main.py
```

### Available MCP tools

| Tool | Description |
|---|---|
| `index_repository` | Index a local git repo into the graph |
| `query_code` | Execute raw Cypher against the graph |
| `find_callers` | Find all functions that call a given function |
| `find_dependencies` | Find what a service depends on |
| `trace_endpoint` | Trace an API endpoint through the call graph |
| `list_services` | List all indexed repositories |
| `search_code` | Fuzzy search for any code entity by name |
| `graph_stats` | Node and relationship counts |

## Architecture

```
Claude Desktop / Claude Code
        │
    MCP (stdio)
        │
   main.py (FastMCP)
        │
   code_graph/
   ├── parser.py      ← tree-sitter AST parsing
   ├── languages.py   ← per-language node type mappings
   ├── schema.py      ← CodeNode / CodeRelationship
   ├── neo4j_store.py ← async Neo4j client
   └── indexer.py     ← repo walker + orchestrator
        │
   Neo4j (Docker)
```

## Example queries via Claude

- "What services are indexed?"
- "Who calls `processPayment`?"
- "Trace POST /api/checkout through the call graph"
- "What classes extend BaseRepository?"
- "Show me all REST endpoints in the payments service"
