"""Authenticated Graph and Reranker APIs for RunPod."""
from __future__ import annotations

import os
import secrets
import sys
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from itertools import islice
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, StringConstraints

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from knowledge_graph.expansion import GraphExpansion  # noqa: E402
from knowledge_graph.persist import load_knowledge_graph  # noqa: E402
from retrieval.remote_stages import SQLiteChunkLoader  # noqa: E402
from services.reranker_adapters import (  # noqa: E402
    RerankerError, RerankerRegistry, SUPPORTED_MODELS, normalize_model_name,
)

Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16000)
]
ChunkId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
]


class GraphRequest(BaseModel):
    seed_chunk_ids: list[ChunkId] = Field(min_length=1, max_length=100)
    max_hop: int = Field(default=2, ge=1, le=5)
    max_context: int = Field(default=30, ge=1, le=100)


class RerankRequest(BaseModel):
    query: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]
    texts: list[Text] = Field(min_length=1, max_length=100)
    model: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)
    ] = None
    top_k: int | None = Field(default=None, ge=1, le=100)


def create_app(kind: Literal["graph", "reranker"], load_engine):
    lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        key = os.environ.get(kind.upper() + "_API_KEY", "").strip()
        if not key:
            raise RuntimeError(f"{kind.upper()}_API_KEY is required")
        app.state.key = key
        app.state.engine = load_engine()
        yield
        app.state.engine = None

    app = FastAPI(title=f"LexVN {kind}", lifespan=lifespan)

    def authenticate(authorization: str = Header(default="")):
        expected = "Bearer " + app.state.key
        if not secrets.compare_digest(authorization, expected):
            raise HTTPException(401, "Unauthorized")

    @app.get("/healthz", dependencies=[Depends(authenticate)])
    def health():
        return {"status": "ok", "service": kind}

    @app.get("/readyz", dependencies=[Depends(authenticate)])
    def ready():
        return {"status": "ready", "service": kind, **app.state.engine.identity}

    def execute(payload):
        with lock:
            try:
                return app.state.engine.run(payload)
            except RerankerError as exc:
                raise HTTPException(exc.status_code, exc.detail()) from None
            except ValueError as exc:
                raise HTTPException(
                    422, {"error": "invalid_runtime_input", "message": str(exc)}
                ) from None

    if kind == "graph":

        @app.post("/graph", dependencies=[Depends(authenticate)])
        def graph(payload: GraphRequest):
            return execute(payload)

    else:

        @app.post("/rerank", dependencies=[Depends(authenticate)])
        def rerank(payload: RerankRequest):
            return execute(payload)

    return app


class GraphEngine:
    def __init__(self):
        artifact = load_knowledge_graph(Path(os.environ["GRAPH_PICKLE_PATH"]))
        self.expansion = GraphExpansion(artifact.graph)
        self.loader = SQLiteChunkLoader(Path(os.environ["GRAPH_PAYLOAD_CACHE"]))
        if not artifact.graph.chunks:
            raise ValueError("Graph is empty")
        samples = list(islice(artifact.graph.chunks, 25))
        loaded_ids = {chunk.chunk_id for chunk in self.loader(samples)}
        if any(sample not in loaded_ids for sample in samples):
            raise ValueError("Graph and payload cache do not match")
        self.identity = {
            "graph_format_version": artifact.format_version,
            "chunk_count": len(artifact.graph.chunks),
        }

    def run(self, request):
        if any(seed not in self.expansion.graph.chunks for seed in request.seed_chunk_ids):
            raise ValueError("Unknown graph seed")
        result = self.expansion.expand(
            request.seed_chunk_ids,
            max_hop=request.max_hop,
            max_context=request.max_context,
        )
        ids = list(dict.fromkeys(result.ordered_context_chunks))
        chunks = {chunk.chunk_id: chunk for chunk in self.loader(ids)}
        if any(chunk_id not in chunks for chunk_id in ids):
            raise ValueError("Missing graph payload")
        return {
            "hits": [asdict(chunks[chunk_id]) for chunk_id in ids],
            "warnings": list(result.warnings),
        }


class RerankerEngine:
    def __init__(self):
        self.registry = RerankerRegistry.from_env()

    @property
    def identity(self):
        return {
            "model": self.registry.default_model,
            "default_model": self.registry.default_model,
            "supported_models": list(SUPPORTED_MODELS),
            "loaded_models": self.registry.loaded_models,
            "device": self.registry.device,
            "max_length": self.registry.max_length,
            "model_cache_size": self.registry.cache_size,
            "allow_experimental": self.registry.allow_experimental,
            "trust_remote_code": self.registry.trust_remote_code,
        }

    def run(self, request):
        model_name = normalize_model_name(request.model or self.registry.default_model)
        adapter = self.registry.get(model_name)
        ranked = adapter.rerank(request.query, list(request.texts), top_k=request.top_k)
        score_by_index = {int(item["index"]): float(item["score"]) for item in ranked}
        if request.top_k is None:
            scores = [score_by_index[index] for index in range(len(request.texts))]
        else:
            scores = [score_by_index.get(index) for index in range(len(request.texts))]
        return {
            "scores": scores,
            "rankings": ranked,
            "model": model_name,
            "default_model": self.registry.default_model,
            "loaded_models": self.registry.loaded_models,
            "device": self.registry.device,
            "max_length": self.registry.max_length,
        }


graph_app = create_app("graph", GraphEngine)
reranker_app = create_app("reranker", RerankerEngine)
