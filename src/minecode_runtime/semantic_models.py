"""Conservative evidence contracts for optional language-server navigation."""
from typing import Literal
from pydantic import Field
from .models import ResultModel

Operation = Literal['definition', 'references', 'implementation', 'incoming_calls', 'outgoing_calls']


class NavigationResult(ResultModel):
    operation: Operation
    status: Literal['completed', 'unsupported', 'failed', 'timed_out']
    items: list[dict] = Field(default_factory=list)
    truncated: bool = False
    message: str = ''


class SemanticResult(ResultModel):
    file: str
    source_sha256: str
    language: Literal['java', 'kotlin']
    backend: dict = Field(default_factory=dict)
    results: list[NavigationResult] = Field(default_factory=list)
    index_state: Literal['unknown'] = 'unknown'
    complete: Literal[False] = False
    untrusted: Literal[True] = True
    limitations: list[str] = Field(default_factory=lambda: [
        'Backend results are not proof of a complete index or resolved dependencies.',
        'Reflection, Mixins and runtime registration can escape static navigation.',
        'Java/Kotlin interoperability depends on the configured backend; it is not guaranteed.',
        'Locations use zero-based UTF-16 coordinates. Only saved source is observed.',
    ])
