"""Typed results shared by local tools and MCP."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Detection(ResultModel):
    project_root: str
    minecraft_detected: bool
    java_detected: bool
    gradle_detected: bool
    fabric_detected: bool
    project_type: Literal["fabric-client", "fabric-mod", "server-plugin", "minecraft", "java", "unknown"]
    descriptor_files: list[str]
    warnings: list[str] = Field(default_factory=list)


class LocalReferenceArtifact(ResultModel):
    artifact_id: str = Field(description="Inventory identity, not a repository source_ids filter. Search local artifacts with search_reference_code(query=...), omitting source_ids.")
    kind: Literal["minecraft-sources", "fabric-api-sources", "yarn-mappings"]
    path: str
    scope: Literal["project", "gradle-user"]
    minecraft_version: str | None = None
    mappings_type: str | None = None
    mappings_version: str | None = None
    namespace: str | None = None
    artifact_version: str | None = None
    project_environment: dict[str, str | None] = Field(default_factory=dict)
    identity_evidence: dict[str, str] = Field(default_factory=dict)
    compatibility: dict[str, str] = Field(default_factory=dict)


class ProjectProfile(ResultModel):
    detection: Detection
    project_name: str | None = None
    minecraft_version: str | None = None
    fabric_loader_version: str | None = None
    fabric_api_version: str | None = None
    java_version: str | None = None
    gradle_version: str | None = None
    loom_version: str | None = None
    mappings_type: str | None = None
    mappings_version: str | None = None
    mod_id: str | None = None
    source_roots: list[str] = Field(default_factory=list)
    client_source_roots: list[str] = Field(default_factory=list)
    mixin_configs: list[str] = Field(default_factory=list)
    entrypoints: dict[str, list[str]] = Field(default_factory=dict)
    gradle_files: list[str] = Field(default_factory=list)
    likely_build_task: str | None = None
    likely_run_client_task: str | None = None
    local_reference_artifacts: list[LocalReferenceArtifact] = Field(default_factory=list)
    local_reference_artifact_counts: dict[str, int] = Field(default_factory=dict)
    local_reference_inventory_included: bool = True
    local_reference_limitations: list[str] = Field(default_factory=list)
    evidence: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class FailureEnvironment(ResultModel):
    minecraft: str | None = Field(default=None, max_length=80)
    loader: str | None = Field(default=None, max_length=80)
    fabric_api: str | None = Field(default=None, max_length=80)
    loom: str | None = Field(default=None, max_length=80)
    mappings: str | None = Field(default=None, max_length=80)
    side: str | None = Field(default=None, max_length=80)
    java: str | None = Field(default=None, max_length=80)
    gradle: str | None = Field(default=None, max_length=80)
    dependency: str | None = Field(default=None, max_length=160)


class Diagnosis(ResultModel):
    category: str
    input_truncated: bool = False
    likely_root_cause: str
    environment: FailureEnvironment = Field(default_factory=FailureEnvironment)
    migration_layer: str = "unknown"
    migration_details: dict[str, str] = Field(default_factory=dict)
    mixin_failure: str | None = None
    mixin_details: dict[str, str] = Field(default_factory=dict)
    networking_failure: str | None = None
    networking_details: dict[str, str] = Field(default_factory=dict)
    important_error: str | None = None
    affected_file: str | None = None
    affected_line: int | None = None
    affected_class: str | None = None
    exception_class: str | None = None
    dependency: str | None = None
    expected_java: str | None = None
    observed_java: str | None = None
    evidence: list[str] = Field(default_factory=list)
    next_step: str
    confidence: Literal["pattern-match", "unknown"] = "pattern-match"


class GradleResult(ResultModel):
    task: str
    success: bool = False
    exit_code: int | None = None
    state: Literal["completed", "failed", "timed_out", "blocked", "task_missing", "cancelled"] = "blocked"
    summary: str
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    elapsed_seconds: float = 0
    diagnosis: Diagnosis | None = None
    warnings: list[str] = Field(default_factory=list)


class Artifact(ResultModel):
    path: str
    changed_during_build: bool
    runtime_verified: bool = False


class BuildResult(ResultModel):
    execution: GradleResult
    artifacts: list[Artifact] = Field(default_factory=list)
    runtime_verified: bool = False


class ClientResult(ResultModel):
    execution: GradleResult
    discovery: GradleResult | None = None
    startup_state: Literal["not_run", "task_missing", "process_exited", "failed", "unverified_timeout"] = "not_run"
    gameplay_verified: bool = False
