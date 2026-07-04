#!/usr/bin/env python3
"""Finalize metadata/relationships datasets for G-LRAG preprocessing handoff."""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RAW_DIR = Path("Road2AI_ApplePie/data/untracked_data")
OUT_DIR = Path("Road2AI_ApplePie/data/finalized")
OUT_DIR.mkdir(parents=True, exist_ok=True)

METADATA_IN = RAW_DIR / "metadata.jsonl"
REL_IN = RAW_DIR / "relationships.jsonl"
METADATA_FINAL = OUT_DIR / "metadata_final.jsonl"
METADATA_QUAR = OUT_DIR / "metadata_quarantine.jsonl"
REL_FINAL = OUT_DIR / "relationships_final.jsonl"
REL_QUAR = OUT_DIR / "relationships_quarantine.jsonl"
STUBS_OUT = OUT_DIR / "metadata_external_stubs.jsonl"
REPORT_OUT = OUT_DIR / "preprocessing_report.md"

CURRENT_MAX_YEAR = 2026
MIN_PLAUSIBLE_YEAR = 1945

TYPE_MAP = {
    "Nghị Quyết": "Nghị quyết",
    "": "unknown_type",
    None: "unknown_type",
}
ACCEPTED_TYPES = {
    "Hiến pháp", "Bộ luật", "Luật", "Pháp lệnh", "Lệnh", "Sắc lệnh", "Sắc luật",
    "Nghị định", "Nghị định thư", "Nghị quyết", "Nghị quyết liên tịch",
    "Quyết định", "Chỉ thị", "Thông tư", "Thông tư liên tịch", "Thông tư liên bộ",
    "Văn bản hợp nhất", "Công văn", "Văn bản liên quan", "Văn bản liên quan khác",
    "Văn bản khác", "Hiệp định", "Công ước", "Chương trình", "Thông báo",
    "Bản ghi nhớ", "Thỏa thuận",
}

STATUS_TO_GROUP = {
    "Còn hiệu lực": ("active", "primary"),
    "Hết hiệu lực một phần": ("partial", "primary"),
    "Chưa có hiệu lực": ("future", "primary"),
    "Ngưng hiệu lực một phần": ("partial", "primary"),
    "Hết hiệu lực toàn bộ": ("expired", "reference"),
    "Không còn phù hợp": ("expired", "reference"),
    "Ngưng hiệu lực": ("suspended", "reference"),
    "Chưa xác định": ("unknown", "reference"),
    "": ("unknown", "reference"),
    None: ("unknown", "reference"),
}

REL_MAP = {
    "Văn bản căn cứ": ("based_on", "basis"),
    "Văn bản dẫn chiếu": ("cites", "citation"),
    "Văn bản HD, QĐ chi tiết": ("guides_or_details", "guidance"),
    "Văn bản được HD, QĐ chi tiết": ("guided_or_detailed_by", "guidance"),
    "Văn bản sửa đổi": ("amends", "amendment"),
    "Văn bản được sửa đổi": ("amended_by", "amendment"),
    "Văn bản bổ sung": ("supplements", "supplement"),
    "Văn bản được bổ sung": ("supplemented_by", "supplement"),
    "Văn bản hết hiệu lực": ("expires_or_replaces", "validity"),
    "Văn bản quy định hết hiệu lực": ("expired_or_replaced_by", "validity"),
    "Văn bản bị hết hiệu lực 1 phần": ("partially_expired_by", "validity"),
    "Văn bản quy định hết hiệu lực 1 phần": ("partially_expires", "validity"),
    "Văn bản đình chỉ": ("suspends", "suspension"),
    "Văn bản bị đình chỉ": ("suspended_by", "suspension"),
    "Văn bản đình chỉ 1 phần": ("partially_suspends", "suspension"),
    "Văn bản bị đình chỉ 1 phần": ("partially_suspended_by", "suspension"),
    "Văn bản liên quan khác": ("related_to", "related"),
}

REFERENCE_ONLY_TYPES = {"Công văn", "Văn bản liên quan", "Văn bản liên quan khác", "Văn bản khác", "Chương trình", "Thông báo", "Bản ghi nhớ", "Thỏa thuận"}


def clean_text(v):
    if v is None:
        return ""
    v = unicodedata.normalize("NFC", str(v)).strip()
    v = re.sub(r"\s+", " ", v)
    return v


def parse_date(v):
    v = clean_text(v)
    if not v or v == "...":
        return None, None, None
    try:
        dt = datetime.strptime(v, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d"), dt.year, None
    except Exception:
        return None, None, "invalid_date"


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def citation_label(d):
    parts = []
    typ = d.get("loai_van_ban_canonical") or d.get("loai_van_ban")
    num = d.get("so_ky_hieu_clean") or d.get("so_ky_hieu")
    date = d.get("ngay_ban_hanh")
    issuer = d.get("co_quan_ban_hanh_canonical") or d.get("co_quan_ban_hanh")
    title = d.get("title_clean") or d.get("title")
    if typ or num:
        parts.append(clean_text(f"{typ} {num}"))
    if date:
        parts.append(clean_text(date))
    if issuer:
        parts.append(clean_text(issuer))
    label = ", ".join([p for p in parts if p])
    if title:
        label = f"{label}: {title}" if label else title
    return label

raw_ids = set()
metadata_final = []
metadata_quar = []
meta_by_id = {}

raw_metadata_count = 0
for line in METADATA_IN.open(encoding="utf-8"):
    raw_metadata_count += 1
    d = json.loads(line)
    id_str = clean_text(d.get("id"))
    raw_ids.add(id_str)

    flags = []
    reasons = []

    title_clean = clean_text(d.get("title"))
    so_clean = clean_text(d.get("so_ky_hieu"))
    typ_raw = clean_text(d.get("loai_van_ban"))
    typ = TYPE_MAP.get(d.get("loai_van_ban"), TYPE_MAP.get(typ_raw, typ_raw or "unknown_type"))
    issuer = clean_text(d.get("co_quan_ban_hanh"))
    scope = clean_text(d.get("pham_vi"))
    sector = clean_text(d.get("nganh"))
    field = clean_text(d.get("linh_vuc"))
    status_raw = clean_text(d.get("tinh_trang_hieu_luc"))
    validity_group, default_tier = STATUS_TO_GROUP.get(status_raw, ("unknown", "reference"))

    issue_iso, issue_year, issue_err = parse_date(d.get("ngay_ban_hanh"))
    eff_iso, eff_year, eff_err = parse_date(d.get("ngay_co_hieu_luc"))
    exp_iso, exp_year, exp_err = parse_date(d.get("ngay_het_hieu_luc"))

    if not id_str:
        reasons.append("missing_id")
    if not title_clean:
        reasons.append("missing_title")
    if not so_clean:
        reasons.append("missing_so_ky_hieu")
    if typ == "unknown_type":
        flags.append("unknown_type"); reasons.append("unknown_type")
    elif typ not in ACCEPTED_TYPES:
        flags.append("unsupported_type"); reasons.append("unsupported_type")
    if not issuer:
        flags.append("missing_issuer"); reasons.append("missing_issuer")
    if issue_err or (clean_text(d.get("ngay_ban_hanh")) == "..."):
        flags.append("invalid_issue_date")
    if issue_year and issue_year > CURRENT_MAX_YEAR:
        flags.append("future_issue_date"); reasons.append("future_issue_date")
    if issue_year and issue_year < MIN_PLAUSIBLE_YEAR:
        flags.append("pre_1945_issue_year")
    if eff_iso and issue_iso and eff_iso < issue_iso:
        flags.append("effective_before_issue")
    if not clean_text(d.get("nguon_thu_thap")):
        flags.append("missing_source")
    if not clean_text(d.get("ngay_dang_cong_bao")) or clean_text(d.get("ngay_dang_cong_bao")) == "...":
        flags.append("missing_publication_date")
    if not clean_text(d.get("ngay_co_hieu_luc")) or clean_text(d.get("ngay_co_hieu_luc")) == "...":
        flags.append("missing_effective_date")
    if not clean_text(d.get("ngay_het_hieu_luc")) or clean_text(d.get("ngay_het_hieu_luc")) == "...":
        flags.append("missing_expiry_date")
    if not sector:
        flags.append("missing_sector")
    if not field:
        flags.append("missing_field")
    if not scope:
        flags.append("missing_scope")
    if validity_group == "unknown":
        flags.append("unknown_validity")
    if validity_group == "expired":
        flags.append("expired_full")
    if validity_group == "suspended":
        flags.append("suspended")

    tier = default_tier
    if typ in REFERENCE_ONLY_TYPES and tier == "primary":
        tier = "reference"
        flags.append("reference_only")

    out = dict(d)
    out.update({
        "id_str": id_str,
        "title_clean": title_clean,
        "so_ky_hieu_clean": so_clean,
        "loai_van_ban_canonical": typ,
        "ngay_ban_hanh_iso": issue_iso,
        "ngay_co_hieu_luc_iso": eff_iso,
        "ngay_het_hieu_luc_iso": exp_iso,
        "issue_year": issue_year,
        "co_quan_ban_hanh_canonical": issuer,
        "pham_vi_canonical": scope,
        "nganh_canonical": sector,
        "linh_vuc_canonical": field,
        "tinh_trang_hieu_luc_canonical": status_raw or "unknown_validity",
        "validity_group": validity_group,
        "dataset_tier": "quarantine" if reasons else tier,
        "quality_flags": sorted(set(flags)),
    })
    out["citation_label"] = citation_label(out)

    if reasons:
        out["exclusion_reasons"] = sorted(set(reasons))
        metadata_quar.append(out)
    else:
        metadata_final.append(out)
        meta_by_id[id_str] = out

final_ids = set(meta_by_id)
quar_ids = {d["id_str"] for d in metadata_quar if d.get("id_str")}

seen_edges = set()
rel_final = []
rel_quar = []
stub_ids = set()
raw_relationship_count = 0

for line in REL_IN.open(encoding="utf-8"):
    raw_relationship_count += 1
    d = json.loads(line)
    a = clean_text(d.get("doc_id"))
    b = clean_text(d.get("other_doc_id"))
    r_raw = clean_text(d.get("relationship"))
    flags = []
    reasons = []
    canon_group = REL_MAP.get(r_raw)
    if not a:
        reasons.append("missing_doc_id")
    if not b:
        reasons.append("missing_other_doc_id")
    if not r_raw or not canon_group:
        flags.append("unmapped_relationship"); reasons.append("unmapped_relationship")
    if a == b:
        flags.append("self_loop"); reasons.append("self_loop")
    edge_key = (a, b, r_raw)
    if edge_key in seen_edges:
        flags.append("duplicate_edge"); reasons.append("duplicate_edge")
    else:
        seen_edges.add(edge_key)
    if a not in raw_ids:
        flags.append("missing_source_metadata"); reasons.append("missing_source_metadata")
    elif a not in final_ids:
        flags.append("source_quarantined"); reasons.append("source_quarantined")
    external_target = False
    if b not in raw_ids:
        flags.append("missing_target_metadata")
        flags.append("external_stub_target")
        external_target = True
        stub_ids.add(b)
    elif b not in final_ids:
        flags.append("target_quarantined"); reasons.append("target_quarantined")

    canonical, group = canon_group if canon_group else ("unmapped", "unmapped")
    if group == "related":
        flags.append("weak_relationship")

    out = dict(d)
    out.update({
        "doc_id_str": a,
        "other_doc_id_str": b,
        "relationship_raw": r_raw,
        "relationship_canonical": canonical,
        "relationship_group": group,
        "source_in_metadata": a in raw_ids,
        "target_in_metadata": b in raw_ids,
        "external_target": external_target,
        "edge_quality_flags": sorted(set(flags)),
        "edge_keep_status": "quarantine" if reasons else "kept",
    })
    if reasons:
        out["exclusion_reasons"] = sorted(set(reasons))
        rel_quar.append(out)
    else:
        rel_final.append(out)

stubs = []
for sid in sorted(stub_ids):
    stubs.append({
        "id_str": sid,
        "is_external_stub": True,
        "missing_metadata": True,
        "citation_safe": False,
        "dataset_tier": "reference_stub",
        "source": "relationships_only",
        "quality_flags": ["external_stub", "missing_metadata", "not_citation_safe"],
    })

write_jsonl(METADATA_FINAL, metadata_final)
write_jsonl(METADATA_QUAR, metadata_quar)
write_jsonl(REL_FINAL, rel_final)
write_jsonl(REL_QUAR, rel_quar)
write_jsonl(STUBS_OUT, stubs)

# Report
meta_tier = Counter(d["dataset_tier"] for d in metadata_final)
meta_valid = Counter(d["validity_group"] for d in metadata_final)
meta_type = Counter(d["loai_van_ban_canonical"] for d in metadata_final)
rel_canon = Counter(d["relationship_canonical"] for d in rel_final)
rel_group = Counter(d["relationship_group"] for d in rel_final)
q_meta_reasons = Counter(r for d in metadata_quar for r in d.get("exclusion_reasons", []))
q_rel_reasons = Counter(r for d in rel_quar for r in d.get("exclusion_reasons", []))

with REPORT_OUT.open("w", encoding="utf-8") as f:
    f.write("# Preprocessing Report\n\n")
    f.write("## Output Files\n\n")
    for p in [METADATA_FINAL, REL_FINAL, METADATA_QUAR, REL_QUAR, STUBS_OUT]:
        f.write(f"- `{p}`\n")
    f.write("\n## Counts\n\n")
    f.write(f"- Raw metadata records: {raw_metadata_count:,}\n")
    f.write(f"- Final metadata records: {len(metadata_final):,}\n")
    f.write(f"- Metadata quarantine records: {len(metadata_quar):,}\n")
    f.write(f"- Raw relationship records: {raw_relationship_count:,}\n")
    f.write(f"- Final relationship records: {len(rel_final):,}\n")
    f.write(f"- Relationship quarantine records: {len(rel_quar):,}\n")
    f.write(f"- External stubs created: {len(stubs):,}\n")
    f.write("\n## Metadata by Tier\n\n")
    for k, v in meta_tier.most_common(): f.write(f"- {k}: {v:,}\n")
    f.write("\n## Metadata by Validity Group\n\n")
    for k, v in meta_valid.most_common(): f.write(f"- {k}: {v:,}\n")
    f.write("\n## Top Metadata Types\n\n")
    for k, v in meta_type.most_common(25): f.write(f"- {k}: {v:,}\n")
    f.write("\n## Relationships by Canonical Label\n\n")
    for k, v in rel_canon.most_common(): f.write(f"- {k}: {v:,}\n")
    f.write("\n## Relationships by Group\n\n")
    for k, v in rel_group.most_common(): f.write(f"- {k}: {v:,}\n")
    f.write("\n## Metadata Quarantine Reasons\n\n")
    for k, v in q_meta_reasons.most_common(): f.write(f"- {k}: {v:,}\n")
    f.write("\n## Relationship Quarantine Reasons\n\n")
    for k, v in q_rel_reasons.most_common(): f.write(f"- {k}: {v:,}\n")

print(json.dumps({
    "metadata_final": len(metadata_final),
    "metadata_quarantine": len(metadata_quar),
    "relationships_final": len(rel_final),
    "relationships_quarantine": len(rel_quar),
    "external_stubs": len(stubs),
    "out_dir": str(OUT_DIR),
}, ensure_ascii=False, indent=2))
