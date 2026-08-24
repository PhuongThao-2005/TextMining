# Production-Like Web App Runbook

## Goal

This document explains how to run the G-LRAG Streamlit web app as a local production-style prototype.

Expected behavior:

- Streamlit starts reliably.
- Production mode uses the real retrieval/generation pipeline.
- Production mode does not fall back to mock/demo data.
- A user question runs through FAISS retrieval, query embedding, and LLM generation.
- The answer displays sources, citations, latency, and diagnostics.
- API keys and secrets are never shown in the UI or committed to the repository.

Current app entry point:

```text
ui/app.py
```

Recommended local start command:

```powershell
.\scripts\start_ui_local.ps1
```

App URL:

```text
http://localhost:8501
```

## 1. Requirements

## 1.1. Python Environment

Use the same Python interpreter for installing dependencies and running Streamlit.

On this machine, the intended interpreter is:

```text
D:\anaconda3\python.exe
```

Check it:

```powershell
python -c "import sys; print(sys.executable)"
```

If `python` points to another interpreter, use the full path:

```powershell
D:\anaconda3\python.exe -c "import sys; print(sys.executable)"
```

## 1.2. Python Dependencies

Install dependencies from the repository root:

```powershell
D:\anaconda3\python.exe -m pip install -r requirements.txt
```

Important packages:

- `streamlit`: web UI
- `openai`: OpenAI-compatible generation API client
- `faiss-cpu`: local FAISS vector index
- `sentence-transformers`: query embedding model
- `transformers>=4.41,<5`: required by `sentence-transformers`
- `torch`: model runtime
- `huggingface-hub`: downloads/caches the embedding model

Check packages:

```powershell
D:\anaconda3\python.exe -c "import importlib.util as u; mods=['streamlit','yaml','openai','faiss','sentence_transformers','transformers','torch']; [print(m, bool(u.find_spec(m))) for m in mods]"
```

Expected:

```text
streamlit True
yaml True
openai True
faiss True
sentence_transformers True
transformers True
torch True
```

## 1.3. Retrieval Artifacts

The local Production config uses this FAISS artifact:

```text
data/chunk metadata/index.faiss
data/chunk metadata/payloads.jsonl
data/chunk metadata/index_manifest.json
```

Optional but useful:

```text
data/chunk metadata/id_map.json
data/chunk metadata/payload_cache.sqlite
```

Check artifact files:

```powershell
D:\anaconda3\python.exe -c "from pathlib import Path; paths=['data/chunk metadata/index.faiss','data/chunk metadata/payloads.jsonl','data/chunk metadata/index_manifest.json']; [print(p, Path(p).exists()) for p in paths]"
```

## 1.4. Corpus and Benchmark

Current local corpus identity:

```text
data/pre-processed/documents.jsonl
```

Official benchmark path for full evaluation:

```text
data/benchmark/qa_final.jsonl
```

Notes:

- The benchmark is not required for one interactive UI question.
- The benchmark is required for full evaluation/ablation runs.
- If the benchmark is missing, the UI may show a warning, but a single Production question can still run.

## 1.5. Config Matrix

Main config file:

```text
configs/ablation_configs.yaml
```

Use this config first for local Production:

```text
Agent-None-PlainRAG
```

After the baseline works, try:

```text
Agent-SimplePlanner
```

Do not use the `LLM-*` configs for the first local app test. Those configs are for ablation contracts and may include Graph/Reranker settings.

## 1.6. Environment Variables

Production OpenAI-compatible configs use:

```text
LLM_BASE_URL
LLM_API_KEY
LLM_BASE_MODEL
LLM_LARGER_MODEL
GRAPH_PICKLE_PATH
HF_HUB_OFFLINE
HF_HOME
TRANSFORMERS_CACHE
SENTENCE_TRANSFORMERS_HOME
TORCH_HOME
XDG_CACHE_HOME
```

For local runs, use a root `.env` file.

Template:

```text
.env.example
```

Local file:

```text
.env
```

`GRAPH_PICKLE_PATH` is optional when the graph is stored at either default location:

```text
data/graph/knowledge_graph.gpickle
data/kg/knowledge_graph.gpickle
```

Set it only when the graph pickle lives somewhere else.

`HF_HUB_OFFLINE=1` is the recommended normal local setting after models are cached. If the Graph + RRF + reranker toggle fails because the cross-encoder model is not cached yet, temporarily set:

```text
HF_HUB_OFFLINE=0
```

Restart Streamlit, let the first reranker load download the model, then switch it back to `1` for stable offline starts.

To keep model downloads off the Windows user profile on `C:`, the local `.env` should point caches into this repository on drive `D:`:

```text
XDG_CACHE_HOME=.cache
HF_HOME=.cache/huggingface
TRANSFORMERS_CACHE=.cache/huggingface/hub
SENTENCE_TRANSFORMERS_HOME=.cache/sentence-transformers
TORCH_HOME=.cache/torch
```

`scripts/start_ui_local.ps1` creates those folders and prints the resolved paths at startup.

The app loads `.env` automatically when `ui/app.py` starts. `.env` is ignored by git.

Example `.env` for OpenAI:

```text
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_BASE_MODEL=gpt-4.1-mini
LLM_LARGER_MODEL=gpt-4.1
```

If terminal environment variables are already set, they take priority over `.env`.

Never commit API keys into YAML, notebooks, docs, or source code.

## 2. How to Run

## 2.1. Install Dependencies

```powershell
cd D:\Study\NamBa\TextMining\TextMining
D:\anaconda3\python.exe -m pip install -r requirements.txt
```

## 2.2. Start the App

Recommended:

```powershell
cd D:\Study\NamBa\TextMining\TextMining
.\scripts\start_ui_local.ps1
```

If PowerShell blocks script execution:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_ui_local.ps1
```

Expected terminal output:

```text
Using Python:
D:\anaconda3\python.exe

Checking required packages:
streamlit: True
faiss: True
sentence_transformers: True
transformers: True
torch: True
openai: True

Starting Streamlit UI at http://localhost:8501
```

Open:

```text
http://localhost:8501
```

## 2.3. Demo Preview

Use Demo Preview when credentials or artifacts are not ready.

Sidebar:

```text
Mode = Demo Preview
```

Try:

```text
Show a complete example with several supporting sources
```

Expected:

- Answer is shown.
- Source cards are shown.
- Sources are labeled as demo/mock sources.
- No model API call is made.
- No FAISS index is loaded.

## 2.4. Production

Sidebar:

```text
Mode = Production
Named configuration = Agent-None-PlainRAG
Top-k = 5
Filter profile = broad
Graph + RRF + reranker = off for the first baseline run
```

If `.env`, config, or artifacts changed, click:

```text
Clear resource cache
```

Then ask one corpus-relevant question.

## 3. Production Question Flow

The first Production question can take longer because the app loads heavy local resources.

You may see terminal logs like:

```text
Reusing SQLite payload cache: payload_cache.sqlite
FAISS index loaded in 12.15s
```

This only means the FAISS store loaded successfully. The app still needs to:

1. Load the embedding model from local Hugging Face cache.
2. Embed the user query.
3. Search FAISS.
4. Build context.
5. Call the LLM API.
6. Validate citations and render the answer.

If no answer appears after FAISS loads, common causes are:

- The embedding model is still loading.
- Windows memory/pagefile is too small for FAISS + embedding model.
- The LLM API call is waiting or retrying.
- `LLM_BASE_URL` is wrong.
- `LLM_API_KEY` is invalid.
- `LLM_BASE_MODEL` is unsupported by the provider.
- The provider is not fully OpenAI-compatible.

An invalid API key usually fails only after the generation request starts. It may not fail instantly because the client can retry.

## 4. Readiness Check

Run from the repository root:

```powershell
$env:PYTHONPATH="src;."
D:\anaconda3\python.exe -c "import runpy; runpy.run_path('ui/app.py', run_name='not_main'); from pathlib import Path; from service.qa_service import load_ui_config_registry; from service.ui_runtime import scan_production_readiness; r=load_ui_config_registry(); rd=scan_production_readiness(r, 'Agent-None-PlainRAG', project_root=Path('.')); print('ready:', rd.ready); print('artifact:', rd.selected_artifact.index_dir if rd.selected_artifact else None); print('blockers:', list(rd.blockers)); print('warnings:', list(rd.warnings))"
```

Expected:

```text
ready: True
blockers: []
```

Warnings about a missing benchmark or incomplete manifest counts do not block one interactive question.

## 5. Health Check

After starting Streamlit:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8501/healthz
```

Expected:

```text
200 OK
ok
```

## 6. Tests

UI tests:

```powershell
D:\anaconda3\python.exe -m pytest tests\ui -q
```

Full suite:

```powershell
D:\anaconda3\python.exe -m pytest -q
```

Recent known result:

```text
334 passed
```

## 7. Troubleshooting

## 7.1. Wrong Python Interpreter

Symptom:

```text
faiss: False
sentence_transformers: False
```

Fix:

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
Get-Process streamlit -ErrorAction SilentlyContinue | Stop-Process

cd D:\Study\NamBa\TextMining\TextMining
.\scripts\start_ui_local.ps1
```

The script should print:

```text
D:\anaconda3\python.exe
```

## 7.2. Missing Packages

Fix:

```powershell
D:\anaconda3\python.exe -m pip install -r requirements.txt
```

Check:

```powershell
D:\anaconda3\python.exe -c "import importlib.util as u; mods=['streamlit','faiss','sentence_transformers','transformers','torch','openai']; [print(m, bool(u.find_spec(m))) for m in mods]"
```

## 7.3. Missing API or Model Settings

Fix `.env`:

```text
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_BASE_MODEL=gpt-4.1-mini
LLM_LARGER_MODEL=gpt-4.1
```

Then restart Streamlit or click:

```text
Clear resource cache
```

## 7.4. FAISS Loads but No Answer Appears

If the terminal stops after:

```text
Reusing SQLite payload cache: payload_cache.sqlite
FAISS index loaded in ...
```

wait a little longer first. The next stages are embedding and API generation.

If it still hangs:

1. Stop all old Python/Streamlit processes.
2. Restart with `.\scripts\start_ui_local.ps1`.
3. Confirm `HF_HOME`, `SENTENCE_TRANSFORMERS_HOME`, and `TORCH_HOME` point to the project `.cache` folder on drive `D:`.
4. Confirm `HF_HUB_OFFLINE` matches the current task: `0` for the first model download, `1` after models are cached.
5. Confirm Windows has enough memory/pagefile.
6. Confirm API settings in `.env`.

Possible memory errors:

```text
The paging file is too small for this operation to complete.
std::bad_alloc
```

Recommended local resources:

```text
RAM: 32 GB or more
Pagefile: 32-64 GB
Free disk: 50 GB or more
```

## 7.5. Increase Windows Pagefile

1. Search Windows for:

```text
Advanced system settings
```

2. Open:

```text
Performance > Settings > Advanced > Virtual memory > Change
```

3. Disable:

```text
Automatically manage paging file size
```

4. Set custom size on a disk with enough free space:

```text
Initial size: 32768 MB
Maximum size: 65536 MB
```

5. Click Set, OK, then restart Windows.

## 7.6. Graph and Reranker

The local UI can run the Graph + RRF + global reranker stack when all of these are available:

```text
data/graph/knowledge_graph.gpickle
data/kg/knowledge_graph.gpickle
sentence-transformers
the configured cross-encoder model cache or network access for the first download
```

The UI exposes this as one runtime toggle: `Graph + RRF + reranker`. It is disabled when the graph pickle is missing. If a browser download leaves a `.crdownload` file in `data/graph` or `data/kg`, wait for the download to finish; do not rename a partial file.

Use `Agent-None-PlainRAG` first with the graph toggle off. After the baseline works, enable `Graph + RRF + reranker` and clear the resource cache.

## 8. Security

Do not:

- Commit `.env`.
- Put API keys in YAML.
- Print raw provider responses containing secrets.
- Show hidden reasoning or `<think>` blocks in the UI.
- Trust model-generated HTML.

Do:

- Use environment variables or `.env` for secrets.
- Keep diagnostics behind a UI toggle.
- Redact errors.
- Keep Demo and Production clearly separated.
- Show real blockers instead of silently falling back to mock data.

## 9. Quick Commands

Install:

```powershell
D:\anaconda3\python.exe -m pip install -r requirements.txt
```

Start:

```powershell
.\scripts\start_ui_local.ps1
```

Health:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8501/healthz
```

UI tests:

```powershell
D:\anaconda3\python.exe -m pytest tests\ui -q
```
