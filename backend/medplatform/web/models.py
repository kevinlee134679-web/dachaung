from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Error(StrictModel):
    code: str
    message: str


class Envelope[T](StrictModel):
    request_id: str
    status: Literal["success", "error"]
    data: T | None
    error: Error | None


class DependencyStatus(StrictModel):
    name: str
    status: Literal["available", "unavailable", "unverified"]
    reason: str | None


class Health(StrictModel):
    process_status: Literal["running"]
    readiness: Literal["ready", "not_ready"]
    dependencies: list[DependencyStatus]
    app_version: str
    checked_at: str


class Capability(StrictModel):
    code: str
    available: bool
    reason: str | None


class VersionRef(StrictModel):
    kind: str
    version: str


class ConfigStatus(StrictModel):
    auth_mode: Literal["demo", "external"]
    llm_mode: Literal["mock", "real"]
    model_configured: bool
    model_connectivity: Literal["unverified", "available", "unavailable"]
    capabilities: list[Capability]
    version_refs: list[VersionRef]
