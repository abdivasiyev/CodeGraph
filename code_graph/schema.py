"""Node and Relationship dataclasses for the code knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CodeNode:
    """A node in the code knowledge graph.

    Labels: Repository, Service, File, Module, Class, Function,
    Variable, Endpoint, DatabaseTable, Event, ExternalAPI, BusinessRule
    """

    fqn: str  # fully qualified name — unique key
    name: str
    label: str  # Neo4j node label
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    language: str = ""
    repo: str = ""
    properties: dict[str, str | int | bool | None] = field(default_factory=dict)

    def to_dict(self) -> dict:
        base = {
            "fqn": self.fqn,
            "name": self.name,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "repo": self.repo,
        }
        base.update(self.properties)
        return base


@dataclass
class PullRequestNode:
    """A pull request, linked to the File nodes it touched.

    Kept separate from CodeNode on purpose: fqn/file_path/start_line/language
    are meaningless for a PR, and folding them in would pollute the code-node
    indexes and the stats headings. The unique key is the Forgejo internal id.
    """

    id: int  # Forgejo internal id — unique merge key
    number: int
    title: str
    state: str  # "open" | "closed"
    url: str
    repo: str  # graph_repo — matches File.repo
    author: str | None = None
    created_at: str | None = None
    merged_at: str | None = None

    def to_dict(self) -> dict:
        # Drop None-valued keys: `SET pr += item` treats a null in the map as
        # "remove this property", so writing {author: null} would strip an
        # author set on an earlier run. Omitting the key leaves it untouched.
        d = {
            "id": self.id,
            "number": self.number,
            "title": self.title,
            "state": self.state,
            "url": self.url,
            "repo": self.repo,
            "author": self.author,
            "created_at": self.created_at,
            "merged_at": self.merged_at,
        }
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class CodeRelationship:
    """A directed relationship between two code nodes."""

    from_fqn: str
    to_fqn: str
    rel_type: str  # e.g. CALLS, CONTAINS, IMPORTS
    properties: dict[str, str | int | bool | None] = field(default_factory=dict)

    def to_dict(self) -> dict:
        base = {
            "from_fqn": self.from_fqn,
            "to_fqn": self.to_fqn,
        }
        base.update(self.properties)
        return base
