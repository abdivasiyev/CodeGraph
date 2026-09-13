"""Index Forgejo pull requests into the code knowledge graph.

Pulls PRs from Forgejo and links each to the File nodes it touched, in the same
Neo4j graph as the code. Run AFTER `main.py index` has populated the File nodes
for the repo — otherwise every PR matches zero files (a warning fires at start).

    export FORGEJO_URL=http://127.0.0.1:3000
    export FORGEJO_TOKEN=<token>
    python index_prs.py --repo owner/name --state all
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from code_graph.forgejo import ForgejoClient, ForgejoError
from code_graph.neo4j_store import Neo4jStore
from code_graph.schema import PullRequestNode

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("code_graph.index_prs")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "codegraph")
FORGEJO_URL = os.getenv("FORGEJO_URL")
FORGEJO_TOKEN = os.getenv("FORGEJO_TOKEN")


async def run(owner: str, name: str, state: str, graph_repo: str) -> None:
    store = Neo4jStore(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)
    await store.connect()
    try:
        # A PR links to File nodes by repo — if none exist under graph_repo, the
        # whole run produces zero edges and would otherwise exit green.
        rows = await store.query(
            "MATCH (f:File {repo: $repo}) RETURN count(f) AS c", {"repo": graph_repo}
        )
        if not rows or rows[0]["c"] == 0:
            log.warning(
                "No File nodes for repo '%s' — every PR will have 0 TOUCHED_FILE "
                "edges. Run `main.py index` first, or pass --graph-repo NAME to "
                "match the name the File nodes were indexed under.", graph_repo,
            )

        prs = edges = zero_matches = 0
        async with ForgejoClient(FORGEJO_URL, FORGEJO_TOKEN) as fg:
            async for pr in fg.list_pulls(owner, name, state):
                user = pr.get("user") or {}
                node = PullRequestNode(
                    id=pr["id"],
                    number=pr["number"],
                    title=pr.get("title") or "",
                    state=pr.get("state") or "",
                    url=pr.get("html_url") or "",
                    repo=graph_repo,
                    author=user.get("login"),        # may be None (deleted acct)
                    created_at=pr.get("created_at"),
                    merged_at=pr.get("merged_at"),    # None while unmerged
                )
                await store.upsert_pull_requests([node])

                paths = [f["filename"] async for f in fg.list_pr_files(owner, name, pr["number"])]
                linked = await store.link_pr_files(pr["id"], graph_repo, paths)
                prs += 1
                edges += linked
                if paths and linked == 0:
                    zero_matches += 1
                log.info("PR #%s: %d/%d files matched", pr["number"], linked, len(paths))

        summary = f"Done: {prs} PR(s) upserted, {edges} TOUCHED_FILE edge(s) created"
        if zero_matches:
            summary += (f", {zero_matches} PR(s) matched 0 files "
                        f"(graph_repo '{graph_repo}' mismatch?)")
        print("\n" + summary)
    finally:
        await store.close()


def _usage() -> None:
    print(
        "Usage: python index_prs.py --repo owner/name "
        "[--state all|open|closed] [--graph-repo NAME]",
        file=sys.stderr,
    )


def main() -> None:
    # Config comes from the environment; no defaults for the Forgejo side —
    # falling back would index against the wrong server silently.
    if not FORGEJO_URL or not FORGEJO_TOKEN:
        print("FORGEJO_URL and FORGEJO_TOKEN must be set.", file=sys.stderr)
        sys.exit(2)

    args = sys.argv[1:]
    repo = graph_repo = None
    state = "all"
    i = 0
    while i < len(args):
        if args[i] == "--repo" and i + 1 < len(args):
            repo = args[i + 1]
            i += 2
        elif args[i] == "--state" and i + 1 < len(args):
            state = args[i + 1]
            i += 2
        elif args[i] == "--graph-repo" and i + 1 < len(args):
            graph_repo = args[i + 1]
            i += 2
        else:
            _usage()
            sys.exit(2)

    if not repo or "/" not in repo:
        _usage()
        sys.exit(2)
    if state not in ("all", "open", "closed"):
        print("--state must be one of: all, open, closed", file=sys.stderr)
        sys.exit(2)

    owner, name = repo.split("/", 1)
    # Default graph_repo to the full "owner/name": that is how File.repo is
    # actually stored in this graph (e.g. "abdivasiyev/code-graph"). Pass
    # --graph-repo to override when a repo was indexed under a different name.
    graph_repo = graph_repo or repo

    try:
        asyncio.run(run(owner, name, state, graph_repo))
    except ForgejoError as exc:
        print(f"Forgejo error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
