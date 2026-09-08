"""Warm dense retrieval service; run with one Uvicorn worker per GPU."""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from service.local_env import load_local_env

load_local_env(ROOT)

from retrieval.dense_protocol import SERVICE_VERSION, Identity, SearchRequest, SearchResponse


def load_runtime():
    from retrieval.config import VectorIndexConfig
    from retrieval.embeddings import SentenceTransformerEmbedder
    from retrieval.retriever import VectorRetriever
    from retrieval.sqlite_faiss_store import SQLitePayloadFaissVectorStore

    index_dir = Path(os.environ.get("DENSE_INDEX_DIR", str(ROOT / "data/chunk metadata")))
    manifest = json.loads((index_dir / "index_manifest.json").read_text(encoding="utf-8"))
    expected = {
        "embedding_model": os.environ.get("DENSE_EXPECTED_MODEL", "intfloat/multilingual-e5-large"),
        "index_version": os.environ.get("DENSE_EXPECTED_INDEX_VERSION", "chunk-metadata-faiss-v1"),
        "corpus_version": os.environ.get("DENSE_EXPECTED_CORPUS_VERSION", "pre-processed-v1"),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Artifact identity does not match configured dense identity.")
    # Check the model before spending time loading the large index.
    embedder = SentenceTransformerEmbedder(
        expected["embedding_model"], device=os.environ.get("DENSE_DEVICE", "cuda")
    )
    store = SQLitePayloadFaissVectorStore.load(index_dir, require_existing_cache=True)
    try:
        count = store.conn.execute("SELECT COUNT(*) FROM payloads").fetchone()[0]
        if count != store.index.ntotal or count != manifest.get("payload_count"):
            raise ValueError("Index and payload cardinalities do not agree.")
        import faiss
        if store.index.metric_type != faiss.METRIC_INNER_PRODUCT:
            raise ValueError("Dense v1 requires an inner-product index.")
        expected_dimension = int(os.environ.get("DENSE_EXPECTED_DIMENSION", "1024"))
        if store.dimension != expected_dimension or manifest.get("embedding_dimension", store.dimension) != store.dimension:
            raise ValueError("Artifact embedding dimension is incompatible.")
        if embedder.dimension != store.dimension:
            raise ValueError("Model and FAISS dimensions do not agree.")
        config = VectorIndexConfig(embedding_model=expected["embedding_model"], expand_units=False)
        retriever = VectorRetriever(config=config, embedder=embedder, store=store)
        identity = Identity(
            service_version=SERVICE_VERSION, **expected,
            embedding_dimension=store.dimension, payload_count=count,
        ).model_dump()
        # Probe the actual embedding/search/hydration path before readiness.
        probe = retriever.retrieve(
            "quy định pháp luật", filter_profile="broad", top_k=3, top_n=1,
            score_threshold=-1, expand_units=False,
        )
        if not probe.chunks:
            raise ValueError("Startup retrieval probe returned no citation-ready chunks.")
        from retrieval.dense_protocol import ChunkResponse
        for chunk in probe.chunks:
            ChunkResponse.model_validate(asdict(chunk))
        return retriever, identity
    except Exception:
        store.conn.close()
        raise


def create_app(loader=load_runtime, *, api_key=None):
    key = os.environ.get("DENSE_API_KEY", "") if api_key is None else api_key
    lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        # Uvicorn accepts traffic only after a successful startup.
        retriever, identity = await asyncio.to_thread(loader)
        app.state.retriever = retriever
        app.state.identity = Identity.model_validate(identity).model_dump()
        app.state.ready = True
        try:
            yield
        finally:
            app.state.ready = False
            if hasattr(retriever.store, "conn"):
                retriever.store.conn.close()

    app = FastAPI(
        title="Dense retrieval", lifespan=lifespan,
        docs_url=None, redoc_url=None, openapi_url=None,
    )
    app.state.ready = False
    app.state.retriever = None
    app.state.identity = None

    def auth(request: Request):
        if key and not hmac.compare_digest(request.headers.get("authorization", "").encode(), f"Bearer {key}".encode()):
            raise HTTPException(401, detail="Authentication failed.")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={
            "error": "invalid_request",
            "message": "Request does not satisfy the dense search contract.",
        })

    @app.get("/healthz", dependencies=[Depends(auth)])
    def healthz():
        return {"status": "ok", "service": "dense-retrieval", "service_version": "dense-retrieval-v1"}

    def require_ready():
        if not app.state.ready:
            raise HTTPException(503, detail="Dense service is not ready.")

    @app.get("/readyz", dependencies=[Depends(auth), Depends(require_ready)])
    def readyz():
        return {"status": "ready", **app.state.identity}

    @app.get("/version", dependencies=[Depends(auth), Depends(require_ready)])
    def version():
        return app.state.identity

    @app.post("/search", response_model=SearchResponse, dependencies=[Depends(auth), Depends(require_ready)])
    def search(body: SearchRequest):
        # Bound GPU work instead of allowing an unbounded queue behind one model.
        if not lock.acquire(blocking=False):
            raise HTTPException(429, detail="Dense service is busy; retry later.")
        try:
            started = time.perf_counter()
            retriever = app.state.retriever
            result = retriever.retrieve(**body.model_dump(exclude={"request_id"}))
            response = dict(
                app.state.identity,
                request_id=body.request_id or uuid.uuid4().hex,
                total_candidates=result.total_candidates,
                filter_profile_used=result.filter_profile_used,
                empty_filter_warning=result.empty_filter_warning,
                latency_ms={
                    **retriever.store.last_search_latency_ms,
                    "embedding": retriever.last_embedding_ms,
                    "total": (time.perf_counter() - started) * 1000,
                },
                hits=[asdict(chunk) for chunk in result.chunks],
            )
            return SearchResponse.model_validate(response)
        except Exception:
            raise HTTPException(500, detail="Dense retrieval failed.") from None
        finally:
            lock.release()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    # Local entry point. Container deployments keep their explicit Uvicorn command.
    os.environ.setdefault("DENSE_DEVICE", "cpu")
    uvicorn.run(app, host="127.0.0.1", port=8002)
