#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OFFICIAL = Path("data/benchmark/qa_final.jsonl")
REQ = ("qa_id", "question", "answer_type", "category", "difficulty")
ANS = ("answer", "reference_answer")
OPT = ("ground_truth_ids", "ground_truth_chunks", "ground_truth_documents", "source_ids", "provision_ids", "chunk_ids", "document_ids")
NESTED = {"provision_ids": ("ground_truth", "provision_ids"), "chunk_ids": ("ground_truth", "chunk_ids"), "document_ids": ("ground_truth", "document_ids")}


def nonempty(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) > 0
    return True


def sha(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def optval(row: dict[str, Any], key: str) -> Any:
    if key in row:
        return row.get(key)
    cur: Any = row
    for part in NESTED.get(key, ()):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur if key in NESTED else None


def short(vals: list[Any], n: int = 20) -> str:
    if not vals:
        return "—"
    s = ", ".join(map(str, vals[:n]))
    return s if len(vals) <= n else f"{s} … (+{len(vals)-n} more)"


def validate(path: Path, version_arg: str | None) -> dict[str, Any]:
    file_sha = sha(path)
    r: dict[str, Any] = {
        "path": path,
        "version": version_arg or (f"qa-final-{file_sha[:12]}" if file_sha else "qa-final-unavailable"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha": file_sha,
        "lines": 0,
        "blank": 0,
        "count": 0,
        "invalid_json": [],
        "non_object": [],
        "missing": defaultdict(list),
        "empty": defaultdict(list),
        "dupes": {},
        "answer_cov": {k: 0 for k in ANS},
        "opt_cov": {k: 0 for k in OPT},
        "blocking": [],
        "warnings": [],
    }
    if path != OFFICIAL:
        r["warnings"].append(f"Validated path `{path}` differs from official path `{OFFICIAL}`.")
    if not path.exists():
        r["blocking"].append(f"Benchmark file is missing: `{path}`.")
        return finish(r)
    if not path.is_file():
        r["blocking"].append(f"Benchmark path is not a file: `{path}`.")
        return finish(r)
    seen: dict[str, list[int]] = defaultdict(list)
    try:
        with path.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, 1):
                r["lines"] += 1
                if not raw.strip():
                    r["blank"] += 1
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as e:
                    r["invalid_json"].append(f"line {line_no}: {e.msg}")
                    continue
                if not isinstance(row, dict):
                    r["non_object"].append(f"line {line_no}: {type(row).__name__}")
                    continue
                r["count"] += 1
                for key in REQ:
                    if key not in row:
                        r["missing"][key].append(line_no)
                    elif not nonempty(row[key]):
                        r["empty"][key].append(line_no)
                if nonempty(row.get("qa_id")):
                    seen[str(row.get("qa_id"))].append(line_no)
                has_answer = False
                for key in ANS:
                    if nonempty(row.get(key)):
                        r["answer_cov"][key] += 1
                        has_answer = True
                if not has_answer:
                    r["missing"]["answer_or_reference_answer"].append(line_no)
                for key in OPT:
                    if nonempty(optval(row, key)):
                        r["opt_cov"][key] += 1
    except OSError as e:
        r["blocking"].append(f"Benchmark file is unreadable: `{path}` ({e}).")
        return finish(r)
    r["dupes"] = {k: v for k, v in seen.items() if len(v) > 1}
    if r["count"] == 0:
        r["blocking"].append("Benchmark contains zero valid JSON object QA rows.")
    if r["invalid_json"]:
        r["blocking"].append(f"Malformed JSONL lines detected: {len(r['invalid_json'])}.")
    if r["non_object"]:
        r["blocking"].append(f"Non-object JSONL rows detected: {len(r['non_object'])}.")
    if r["dupes"]:
        r["blocking"].append(f"Duplicate qa_id values detected: {len(r['dupes'])}.")
    for kind in ("missing", "empty"):
        for key, vals in r[kind].items():
            if vals:
                r["blocking"].append(f"{kind.title()} required field `{key}` on {len(vals)} row(s).")
    for key, val in r["opt_cov"].items():
        if r["count"] and val < r["count"]:
            r["warnings"].append(f"Optional field `{key}` coverage is {val}/{r['count']}; related metrics may be limited.")
    return finish(r)


def finish(r: dict[str, Any]) -> dict[str, Any]:
    r["status"] = "FAIL" if r["blocking"] else ("PASS_WITH_WARNINGS" if r["warnings"] else "PASS")
    r["locked"] = not r["blocking"]
    return r


def report(r: dict[str, Any]) -> str:
    total = r["count"]
    lines = [
        "# Ablation Benchmark Contract", "", "## Benchmark Identity", "",
        f"- Official benchmark artifact: `{OFFICIAL.as_posix()}`",
        f"- Validated benchmark path: `{r['path'].as_posix()}`",
        f"- Benchmark version: `{r['version']}`",
        f"- Generated at: `{r['generated_at']}`",
        f"- SHA-256: `{r['sha'] or 'unavailable'}`",
        "- Candidate benchmark files: not official for ablation unless explicitly promoted later.",
        "", "## Summary", "",
        f"- Validation status: **{r['status']}**",
        f"- Benchmark locked for ablation: **{'YES' if r['locked'] else 'NO'}**",
        f"- Total QA cases: {total}", f"- Total physical lines: {r['lines']}", f"- Blank lines ignored: {r['blank']}",
        "", "## Required Schema", "", "| Rule | Coverage / Issues |", "| --- | --- |",
        f"| `qa_id` non-empty | missing: {len(r['missing'].get('qa_id', []))}; empty: {len(r['empty'].get('qa_id', []))} |",
        f"| `qa_id` unique | duplicate IDs: {len(r['dupes'])} |",
        f"| `question` non-empty | missing: {len(r['missing'].get('question', []))}; empty: {len(r['empty'].get('question', []))} |",
        f"| `answer` or `reference_answer` non-empty | answer: {r['answer_cov']['answer']}; reference_answer: {r['answer_cov']['reference_answer']}; missing both: {len(r['missing'].get('answer_or_reference_answer', []))} |",
        f"| `answer_type` non-empty | missing: {len(r['missing'].get('answer_type', []))}; empty: {len(r['empty'].get('answer_type', []))} |",
        f"| `category` non-empty | missing: {len(r['missing'].get('category', []))}; empty: {len(r['empty'].get('category', []))} |",
        f"| `difficulty` non-empty | missing: {len(r['missing'].get('difficulty', []))}; empty: {len(r['empty'].get('difficulty', []))} |",
        "", "## Optional Ground Truth Fields", "", "| Field | Rows with value | Coverage |", "| --- | ---: | ---: |",
    ]
    for key in OPT:
        val = r["opt_cov"][key]; pct = (val / total * 100) if total else 0
        lines.append(f"| `{key}` | {val}/{total} | {pct:.1f}% |")
    lines += ["", "## Validation Results", "", f"- Invalid JSON lines: {len(r['invalid_json'])} ({short(r['invalid_json'])})", f"- Non-object rows: {len(r['non_object'])} ({short(r['non_object'])})", "", "### Missing Required Fields", "", "| Field | Count | Lines |", "| --- | ---: | --- |"]
    for key in sorted(set(r["missing"]) | {"answer_or_reference_answer"}):
        vals = r["missing"].get(key, [])
        lines.append(f"| `{key}` | {len(vals)} | {short(vals)} |")
    lines += ["", "### Empty Required Fields", "", "| Field | Count | Lines |", "| --- | ---: | --- |"]
    for key in sorted(set(REQ) | set(r["empty"])):
        vals = r["empty"].get(key, [])
        lines.append(f"| `{key}` | {len(vals)} | {short(vals)} |")
    lines += ["", "### Duplicate QA IDs", "", "| qa_id | Lines |", "| --- | --- |"]
    lines += [f"| `{k}` | {short(v)} |" for k, v in sorted(r["dupes"].items())] or ["| — | — |"]
    lines += ["", "## Known Issues", ""]
    if r["blocking"]:
        lines += ["### Blocking", ""] + [f"- {x}" for x in r["blocking"]] + [""]
    if r["warnings"]:
        lines += ["### Warnings", ""] + [f"- {x}" for x in r["warnings"]]
    if not r["blocking"] and not r["warnings"]:
        lines.append("- None.")
    lines += ["", "## Contract Decision", "", f"- Decision: **{'LOCKED' if r['locked'] else 'NOT LOCKED'}**", f"- Status: **{r['status']}**", f"- Official benchmark path for downstream specs: `{OFFICIAL.as_posix()}`", f"- Benchmark version to reference downstream: `{r['version']}`", f"- QA count to reference downstream: {total}"]
    lines.append("- Team may use this benchmark artifact for ablation runs, while respecting warnings above." if r["locked"] else "- Team must fix blocking issues before using this benchmark for ablation runs.")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Validate the ablation QA benchmark contract.")
    p.add_argument("--benchmark", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--version")
    a = p.parse_args()
    r = validate(a.benchmark, a.version)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(report(r), encoding="utf-8")
    print(f"Ablation benchmark contract: {a.out}")
    print(f"Status: {r['status']}; locked={r['locked']}; qa_count={r['count']}")
    return 1 if r["status"] == "FAIL" else 0

if __name__ == "__main__":
    raise SystemExit(main())
