"""Contract checks on analysis.json before rendering."""
import json
import re

from .ingest import item_keys

DIM_IDS_EXPECTED = 16
VALID_STATUS = {"yes", "part", "no", "unk"}

def validate(lessons, analysis, dims):
    problems, warnings = [], []
    dim_ids = {d["id"] for d in dims["dims"]}
    if len(dim_ids) != DIM_IDS_EXPECTED:
        warnings.append(f"expected {DIM_IDS_EXPECTED} dimensions, found {len(dim_ids)}")
    keys = {k for k, _, _ in item_keys(lessons)}
    mapped = analysis.get("item_dims", {})
    for k, ids in mapped.items():
        if k not in keys:
            problems.append(f"item_dims key {k} does not match any report item")
        for i in ids:
            if i not in dim_ids:
                problems.append(f"item_dims {k}: unknown dimension id {i}")
    unmapped = sorted(keys - set(mapped), key=lambda k: (int(re.match(r"\d+", k).group()), k))
    if unmapped:
        warnings.append(f"{len(unmapped)} items have no dimension: {', '.join(unmapped)}")
    for d in analysis.get("dims", {}):
        if d not in dim_ids:
            problems.append(f"dims: unknown dimension id {d}")
    for a in analysis.get("adopt", []):
        if a.get("status") not in VALID_STATUS:
            problems.append(f"adopt '{a.get('rec')}': status must be one of {sorted(VALID_STATUS)}")
    n_ins = len(analysis.get("insights", []))
    if not 3 <= n_ins <= 5:
        warnings.append(f"insights: {n_ins} items, the format calls for 3 to 5")
    nums = {l["n"] for l in lessons}
    for r in analysis.get("recs", []):
        bad = [x for x in r.get("lessons", []) if x not in nums]
        if bad:
            problems.append(f"recs '{r.get('name')}': lesson numbers out of range {bad}")
    for section in ("hero", "recs", "adopt", "growth", "next", "dims", "item_dims"):
        if section not in analysis:
            problems.append(f"analysis.json is missing '{section}'")
    text = json.dumps({k: x for k, x in analysis.items() if not k.startswith("_")}, ensure_ascii=False)
    if "—" in text:
        warnings.append("analysis text contains em dashes (—); the house style avoids them")
    return problems, warnings


