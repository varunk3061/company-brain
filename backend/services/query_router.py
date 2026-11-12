"""Decide which retrieval paths a question needs: vector, entity graph, graph facts.

Rules (cheap and predictable, no extra LLM call):
    vector        always: it carries the permission filter and the evidence text
    entity graph  when the question names an entity the graph knows
    graph facts   when it also asks about a relationship ("who manages", "which", "how many", ...)

Entity detection itself needs Neo4j and lives in retrieval_service; this module only applies the rules.
"""
# Looks at the question and decides which search to use: vector search always, and graph search too when the question asks about a person or thing, or about a link like “who manages…”.

import re
from dataclasses import dataclass, field

# Words that signal a question about how things are connected, not just what a text says.
RELATIONAL_PATTERN = re.compile(
    r"\b("
    r"who|whom|whose|which|"
    r"manag(?:e|es|ed|er|ers|ing)|lead(?:s|er|ers|ing)?|led|head(?:s|ed)?|"
    r"own(?:s|ed|er|ers)?|report(?:s|ed|ing)?\s+to|"
    r"work(?:s|ed|ing)?\s+(?:in|with|for|on)|"
    r"use(?:s|d)?|using|responsible|in\s+charge|belong(?:s)?\s+to|member(?:s)?\s+of|"
    r"appl(?:y|ies)\s+to|client(?:s)?\s+of|"
    r"related|connected|relationship|"
    r"how\s+many|list\s+(?:all|the)"
    r")\b",
    re.IGNORECASE, #it ignore the case of the letters in the question. 
)


@dataclass(frozen=True)
class RetrievalPlan:
    """What retrieval should run for one question. `entity_keys` are normalized entity keys."""

    entity_keys: tuple[str, ...] = field(default_factory=tuple)
    relational: bool = False

    @property
    def use_entity_graph(self) -> bool: #This checks whether any entity keys were detected.
        return bool(self.entity_keys)

    @property
    def use_graph_facts(self) -> bool: #This checks two conditions:At least one entity must be detected. The question must be relational.
        return bool(self.entity_keys) and self.relational

    @property
    def name(self) -> str:
        """Short label for the audit log."""
        if self.use_graph_facts:
            return "vector+entity+facts"
        if self.use_entity_graph:
            return "vector+entity"
        return "vector"


def is_relational(question: str) -> bool:
    return bool(RELATIONAL_PATTERN.search(question or ""))
#find the relational pattern in the question. using the regex pattern defined earlier


def build_plan(question: str, entity_keys: list[str] | tuple[str, ...]) -> RetrievalPlan:
    return RetrievalPlan(
        entity_keys=tuple(sorted(set(entity_keys))),
        relational=is_relational(question), #it is either true or false
    )
