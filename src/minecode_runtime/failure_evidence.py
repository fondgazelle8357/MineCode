"""Bounded, best-effort sanitized runtime failure diagnosis."""
import re
from typing import Literal
from pydantic import Field
from .diagnostics import analyze, bounded_log
from .models import FailureEnvironment, ResultModel
from .output_safety import sanitize


class RepairEvidence(ResultModel):
    attempted: str = Field(default='', max_length=1000)
    result: Literal['not_attempted', 'failed', 'build_passed', 'runtime_passed', 'unverified'] = 'not_attempted'


class FailureEvidence(ResultModel):
    environment: FailureEnvironment
    category: str
    root_cause_hypothesis: str
    evidence: list[str]
    confidence: Literal['pattern-match', 'unknown']
    source: str
    attempted_repair: RepairEvidence
    remaining_uncertainty: list[str]
    next_step: str = ''
    migration_layer: str = 'unknown'
    migration_details: dict[str, str] = Field(default_factory=dict)
    mixin_failure: str | None = None
    mixin_details: dict[str, str] = Field(default_factory=dict)
    networking_failure: str | None = None
    networking_details: dict[str, str] = Field(default_factory=dict)
    input_truncated: bool = False


def diagnose(output: str, environment: FailureEnvironment | None = None,
             source: str = 'developer-provided log', repair: RepairEvidence | None = None) -> FailureEvidence:
    if len(output) > 128000 or len(source) > 240:
        raise ValueError('Log limit is 128,000 characters; provenance label limit is 240')
    bounded, input_truncated = bounded_log(output)
    clean = sanitize(bounded)
    if len(clean) > 128000:
        clean = clean[:128000]
        input_truncated = True
    env=environment or FailureEnvironment()
    limits = FailureEnvironment.model_json_schema()['properties']
    env=FailureEnvironment.model_validate({
        k:sanitize(v)[:limits[k]['anyOf'][0]['maxLength']] if v else v for k,v in env.model_dump().items()})
    d = analyze(clean, env)
    category, hypothesis = d.category, d.likely_root_cause
    if category == 'unknown':
        for pattern, label, why in [
            (r'OutOfMemoryError', 'memory', 'The JVM reports exhausted memory; inspect allocation and heap settings.'),
            (r'GLFW error|Failed to create.*window|OpenGL.*(?:error|unsupported)', 'graphics-startup', 'Graphics/window initialization failed; inspect the driver and runtime environment.'),
            (r'Cannot load class .*environment|invalid dist', 'side-mismatch', 'A class may be loaded on an incompatible logical/physical side.'),
        ]:
            hits=[line[:800] for line in clean.splitlines() if re.search(pattern,line,re.I)]
            if hits:
                category,hypothesis,d.evidence,d.confidence=label,why,hits[:3],'pattern-match'
                break
    excerpts=[]
    for number,line in enumerate(clean.splitlines(),1):
        if any(e in line for e in d.evidence) or 'Caused by:' in line:
            excerpts.append(f'line {number}: {line.strip()[:800]}')
            if len(excerpts)==6: break
    repair=repair or RepairEvidence()
    repair=RepairEvidence(attempted=sanitize(repair.attempted)[:1000], result=repair.result)
    next_step=d.next_step
    uncertainty=['Pattern matching does not prove the root cause.',
        'Environment and repair results are caller-reported, not independently verified.',
        'Redaction is best-effort; review before sharing. Raw logs are not stored by this tool.']
    if input_truncated or d.input_truncated:
        uncertainty.insert(0, 'Oversized log lines or expanded sanitized output were omitted; inspect the original locally if needed.')
    if category == 'mixin':
        uncertainty.insert(0, 'The failure does not identify a replacement target; verify current-version source and mappings.')
        uncertainty.insert(1, 'A successful compile or build does not prove that this Mixin applies at runtime.')
    elif category == 'networking-registration':
        uncertainty.insert(0, 'Registration evidence does not prove payload delivery, handler execution, or server-side validation.')
    return FailureEvidence(environment=env, category=category, root_cause_hypothesis=hypothesis,
        evidence=excerpts, confidence=d.confidence, source=sanitize(source)[:240], attempted_repair=repair,
        remaining_uncertainty=uncertainty, next_step=next_step,
        migration_layer=d.migration_layer, migration_details=d.migration_details,
        mixin_failure=d.mixin_failure, mixin_details=d.mixin_details,
        networking_failure=d.networking_failure, networking_details=d.networking_details,
        input_truncated=input_truncated or d.input_truncated)
