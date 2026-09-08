"""Versioned dense HTTP contract shared by server and client."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SERVICE_VERSION = "dense-retrieval-v1"


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    query: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=30, ge=1, le=150)
    top_n: int = Field(default=10, ge=1, le=50)
    filter_profile: Literal["current_law", "broad", "historical"] = "broad"
    score_threshold: float | None = Field(default=0.3, ge=-1, le=1)
    expand_units: bool = False
    request_id: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._-]+$")

    @model_validator(mode="after")
    def check_bounds(self):
        if not self.query.strip() or self.top_n > self.top_k:
            raise ValueError("Query must contain text and top_n must not exceed top_k.")
        return self


class Identity(BaseModel):
    model_config = ConfigDict(strict=True)
    service_version: Literal["dense-retrieval-v1"]
    embedding_model: str = Field(min_length=1)
    embedding_dimension: int = Field(gt=0)
    corpus_version: str = Field(min_length=1)
    index_version: str = Field(min_length=1)
    payload_count: int = Field(gt=0)


class ChunkResponse(BaseModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)
    chunk_id: str = Field(min_length=1)
    chunk_text: str = Field(min_length=1)
    citation_anchor: str = Field(min_length=1)
    citation_label: str = Field(min_length=1)
    title: str
    article_number: str | None
    unit_type: str
    path: str | None
    validity_group: str
    legal_authority_rank: int
    vector_score: float
    rerank_score: float
    id_str: str
    parent_unit_id: str
    metadata: dict[str, Any]


class SearchResponse(Identity):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)
    request_id: str
    filter_profile_used: Literal["current_law", "broad", "historical"]
    total_candidates: int = Field(ge=0)
    empty_filter_warning: bool
    latency_ms: dict[str, float]
    hits: list[ChunkResponse]
