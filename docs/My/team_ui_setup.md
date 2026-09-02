# Team UI setup

This is the shortest path for running the Streamlit legal Q&A UI on a teammate machine.

## 1. Create a Python environment

From the repository root:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `.venv` already exists, reuse it.

## 2. Add local secrets

Copy the example file and edit `.env` locally:

```powershell
Copy-Item .env.example .env
notepad .env
```

Required for Production:

```text
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-real-key
LLM_BASE_MODEL=your-fast-model
LLM_LARGER_MODEL=your-larger-model
HF_HUB_OFFLINE=0
```

Keep `.env` local. It is ignored by git.

## 3. Place local artifacts

Demo Preview needs:

```text
data/qa_final.jsonl
```

Production needs:

```text
data/chunk metadata/index.faiss
data/chunk metadata/payloads.jsonl
data/chunk metadata/index_manifest.json
data/pre-processed/documents.jsonl
```

Optional:

```text
data/chunk metadata/payload_cache.sqlite
data/chunk metadata/id_map.json
data/graph/knowledge_graph.gpickle
```

If `index_manifest.json` is missing but `index.faiss` and `payloads.jsonl` are present, create it:

```powershell
.\.venv\Scripts\python.exe scripts\write_faiss_manifest.py --config Agent-None-PlainRAG
```

The script writes only metadata it can verify from config and the payload file.

## 4. Check readiness

Run:

```powershell
.\.venv\Scripts\python.exe scripts\check_ui_production_readiness.py --config Agent-None-PlainRAG
```

Production can run when `ready: True`. Warnings about a missing benchmark do not block one interactive question.

## 5. Start the UI

Run:

```powershell
.\scripts\start_ui_local.ps1
```

Open:

```text
http://localhost:8501
```

Use `Demo Preview` first for a fast UI check. Use `Production` after readiness passes.
