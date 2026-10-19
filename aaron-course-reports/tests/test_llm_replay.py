"""Record/replay for Layer 3. The fixtures are raw replies from the real model, saved with
AARON_LLM_RECORD=tests/fixtures/llm/<course>. CI replays them and never calls the API.

To re-record after changing SYSTEM, SCHEMA or the facts:
  AARON_LLM_RECORD=tests/fixtures/llm/psychology course-reports build --reports examples/psychology/export.json \\
    --learned examples/psychology/learning_report.md --course examples/psychology/course.json --out /tmp/o --slug psychology
"""
import json
from pathlib import Path

import pytest

from course_reports import narrative, pipeline
from course_reports.ingest import load_course

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/llm"
LEARNED = {"psychology": ROOT / "examples/psychology/learning_report.md", "informal": None}


@pytest.mark.parametrize("name", LEARNED)
def test_recorded_reply_passes_guards(name, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # replay must not depend on a key
    cfg = json.loads((ROOT / "examples" / name / "course.json").read_text(encoding="utf-8"))
    lessons, taught, learned = load_course([ROOT / "examples" / name / "export.json"], LEARNED[name])
    *_, facts = pipeline.compute(cfg, lessons, taught, learned)
    raw = (FIX / f"{name}.txt").read_text(encoding="utf-8")

    def replay(facts, feedback=None, model=None):
        assert feedback is None, "the recorded reply needed a retry; re-record the fixture"
        return raw, {"model": "claude-sonnet-5-5", "input_tokens": 13447, "output_tokens": 3526}
    monkeypatch.setattr(narrative, "_request", replay)
    narr, meta = narrative.build_narrative(facts, use_llm=True, log=lambda m: None)
    assert meta["source"] == "llm" and meta["violations"] == [] and meta["calls"] == 1
    reply = narrative.parse_reply(raw)
    assert narr["hero"] == narrative.fix_dashes(reply["hero"])
    assert set(narr["dim_notes"]) == {d["id"] for d in facts["dims"]}
    assert "—" not in json.dumps(narr, ensure_ascii=False)


def test_batch_mode_uses_batch_replies(tmp_path, monkeypatch):
    """batch --llm-batch: one Message Batch for all courses; replies flow into each build, priced at half."""
    from course_reports import cli, llm_batch
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    sent = {}

    def fake_run(facts_by_id, out, model=None, batch_id=None, poll=30, log=None):
        sent.update(facts_by_id)
        u = {"model": "claude-haiku-5-5", "input_tokens": 12000, "output_tokens": 4000, "batch": True}
        replies = {"c0": ((FIX / "psychology.txt").read_text(encoding="utf-8"), u)}
        return replies, {"c1": "expired"}
    monkeypatch.setattr(llm_batch, "run", fake_run)
    monkeypatch.setattr(narrative, "_request", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no network in tests")))
    manifest = [{"name": "מבוא לפסיכולוגיה", "student_noun": "סטודנטיות", "slug": "psy",
                 "reports": str(ROOT / "examples/psychology/export.json"),
                 "learned": str(ROOT / "examples/psychology/learning_report.md")},
                {"name": "חינוך בלתי פורמלי", "slug": "informal", "reports": str(ROOT / "examples/informal/export.json")}]
    m = tmp_path / "courses.json"
    m.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    cli.main(["batch", "--manifest", str(m), "--out", str(tmp_path / "out"), "--llm-batch", "--format", "md"])
    assert set(sent) == {"c0", "c1"}
    s = {r["slug"]: r for r in json.loads((tmp_path / "out/summary.json").read_text(encoding="utf-8"))}
    assert s["psy"]["narrative_source"] == "llm" and s["psy"]["llm_batch"] is True
    assert s["psy"]["llm_cost_usd_est"] == round((12000 * 0.10 + 4000 * 0.50) / 1e6 / 2, 4)
    assert s["informal"]["narrative_source"] == "fallback"   # expired in the batch, direct call failed -> deterministic copy
    assert "batch request failed (expired)" in (tmp_path / "out/logs/informal.log").read_text(encoding="utf-8")
