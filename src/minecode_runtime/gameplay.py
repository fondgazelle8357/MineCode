"""Small, static terminology index. No learning, execution, network or persistence."""
from pathlib import Path
import re
import unicodedata
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from .installation import resources
from .models import ResultModel

Text = Annotated[str, Field(min_length=1, max_length=800)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,79}$")]
Category = Literal["sword", "movement", "mace", "pearls", "wind-charge", "shield", "crystal", "anchor", "inventory"]
MAX_OUTPUT = 16000


def normalize(value: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", value).casefold()))


class Provenance(ResultModel):
    title: Name
    url: Annotated[str, Field(min_length=1, max_length=500)]
    kind: Literal["official", "community-documentation", "maintainer"]
    checked_at: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    supports: Text

    @field_validator("url")
    @classmethod
    def https_source(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Provenance must be a HTTPS reference without credentials")
        return value


class Technique(ResultModel):
    id: Identifier
    name: Name
    aliases: Annotated[list[Name], Field(max_length=8)]
    category: Category
    definition: Text
    mechanic: Text
    inputs: Annotated[list[Name], Field(min_length=1, max_length=8)]
    version_relevance: Text
    server_dependence: Text
    timing_dependence: Text
    client_server_relevance: Text
    related: Annotated[list[Identifier], Field(max_length=8)]
    development_relevance: Text
    automation_relevance: Text
    confidence: Literal["high", "medium", "low"]
    sources: Annotated[list[Provenance], Field(min_length=1, max_length=4)]
    known_uncertainty: Text


class Registry(ResultModel):
    schema_version: Literal[1]
    entries: Annotated[list[Technique], Field(min_length=1, max_length=40)]

    @model_validator(mode="after")
    def unique_and_linked(self) -> "Registry":
        ids: set[str] = set()
        terms: dict[str, str] = {}
        for entry in self.entries:
            if entry.id in ids:
                raise ValueError(f"Duplicate technique ID: {entry.id}")
            ids.add(entry.id)
            for term in [entry.name, *entry.aliases]:
                key = normalize(term)
                if not key or key in terms:
                    raise ValueError(f"Empty/duplicate normalized name or alias: {term}")
                terms[key] = entry.id
        for entry in self.entries:
            if any(item not in ids or item == entry.id for item in entry.related):
                raise ValueError(f"Invalid related technique in {entry.id}")
        return self


class TechniqueResults(ResultModel):
    query: str
    results: list[Technique]
    truncated: bool = False
    warning: str = ("Terminology evidence, not tested gameplay or implementation instructions. "
                    "Confirm edition, exact version, server rules and timing. Development/automation relevance is MineCode analysis.")


def load_registry(path: Path | None = None) -> Registry:
    path = path or resources() / "references" / "gameplay" / "techniques.json"
    if path.stat().st_size > 262144:
        raise ValueError("Gameplay registry exceeds 256 KiB")
    return Registry.model_validate_json(path.read_text(encoding="utf-8"))


def search_techniques(query: str, max_results: int = 3, category: Category | None = None,
                      registry: Registry | None = None) -> TechniqueResults:
    if not isinstance(query, str) or not 1 <= len(query) <= 300 or not normalize(query):
        raise ValueError("Query must contain 1–300 characters including a word")
    if type(max_results) is not int or not 1 <= max_results <= 5:
        raise ValueError("Use 1–5 results")
    query_key = normalize(query)
    tokens = set(query_key.split()) - {"what", "is", "a", "the", "in", "minecraft", "how", "does", "work"}
    ranked = []
    for entry in (registry or load_registry()).entries:
        if category is not None and entry.category != category:
            continue
        names = [normalize(x) for x in [entry.name, *entry.aliases]]
        # Whole aliases beat generic mechanics; acronym matching is never substring matching.
        exact = query_key in names
        phrase = any(f" {name} " in f" {query_key} " for name in names)
        keywords = set(normalize(" ".join([entry.name, *entry.aliases, entry.category,
                                          entry.definition, entry.mechanic])).split())
        overlap = len(tokens & keywords)
        if exact or phrase or (tokens and overlap == len(tokens)):
            ranked.append((1000 * exact + 100 * phrase + overlap, entry))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    result = TechniqueResults(query=query, results=[entry for _, entry in ranked[:max_results]],
                              truncated=len(ranked) > max_results)
    while len(result.model_dump_json()) > MAX_OUTPUT:
        result.results.pop()
        result.truncated = True
    return result
