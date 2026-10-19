"""Regression tests on the two example courses. Run: pytest -q"""
import json
import re
from pathlib import Path

import pytest

from course_reports import narrative, pipeline
from course_reports import signals as S
from course_reports.ingest import load_course
from course_reports.render_html import render
from course_reports.render_md import render_md

EX = Path(__file__).resolve().parents[1] / "examples"
COURSES = {
    "psychology": dict(reports=[EX / "psychology/export.json"], learned=EX / "psychology/learning_report.md"),
    "informal": dict(reports=[EX / "informal/export.json"], learned=None),
}


def _load(name):
    c = COURSES[name]
    cfg = json.loads((EX / name / "course.json").read_text(encoding="utf-8"))
    lessons, taught, learned = load_course(c["reports"], c["learned"])
    return cfg, lessons, taught, learned


@pytest.mark.parametrize("name", COURSES)
def test_ingest(name):
    cfg, lessons, taught, learned = _load(name)
    assert len(lessons) == 10
    assert all(len(l["practices"]) == 4 and len(l["opportunities"]) == 4 for l in lessons)
    assert all(l["actions"] for l in lessons)
    assert len(taught) == 10
    assert (learned is not None) == (name == "psychology")


@pytest.mark.parametrize("name", COURSES)
def test_dimension_mapping_matches_golden(name):
    cfg, lessons, taught, learned = _load(name)
    gold = json.loads((EX / name / "golden_analysis.json").read_text(encoding="utf-8"))["item_dims"]
    pred = S.map_items(lessons, S.LexiconClassifier())
    keys = [k for k in pred if k in gold]
    overlap = sum(1 for k in keys if set(pred[k]) & set(gold[k])) / len(keys)
    assert overlap >= 0.85, overlap
    ids = [d["id"] for d in pipeline.load_dims()["dims"]]
    sp, sg = S.dim_signals(pred, ids), S.dim_signals(gold, ids)
    lv = lambda st: int(S.dim_state(st)["level"][1])
    assert sum(abs(lv(sp[d]) - lv(sg[d])) <= 1 for d in ids) >= 15


def test_adoption_matches_known_cases():
    cfg, lessons, taught, learned = _load("psychology")
    th = {t["id"]: t for t in S.theme_signals(lessons, taught, S.load_themes())}
    assert th["pairs"]["status"] == "yes"       # pair work entered the classroom from lesson 9
    assert th["exit"]["status"] == "no"         # exit tickets recommended repeatedly, never observed
    assert th["visual"]["status"] == "no"


@pytest.mark.parametrize("name", COURSES)
def test_build_both_formats(name, tmp_path):
    c = COURSES[name]
    cfg, *_ = _load(name)
    lessons, taught, learned, analysis = pipeline.run(c["reports"], cfg, c["learned"], use_llm=False, log=lambda m: None)
    clean = {k: v for k, v in analysis.items() if not k.startswith("_")}
    html = render(lessons, clean, pipeline.load_dims(), standalone=True, taught=taught, learned=learned)
    md = render_md(lessons, clean, pipeline.load_dims(), taught, learned)
    assert not re.findall(r"__[A-Z_]+__", html)
    assert '<a id="how"></a>' in md and re.search(r"^## .*איך לימדתי", md, re.M) and "### השיעורים" in md
    assert md.count("<span") == md.count("</span>")
    assert not re.search("[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF]", md)  # house style: no emoji
    plain = re.sub(r'<span style="[^"]*">|</span>', "", md)                     # what GitHub shows (styles stripped)
    assert "אומצה" in plain and "●" in plain and "█" in plain
    for anchor in ("overview", "taught", "how", "learned", "sec-recs", "sec-adopt", "sec-next", *(f"l{l['n']}" for l in lessons)):
        assert f'<a id="{anchor}"></a>' in md, anchor               # same ids as the HTML routes
    assert all(f"](#{a})" not in md or f'<a id="{a}"></a>' in md for a in re.findall(r"\]\(#([\w-]+)\)", md))  # no dead links
    assert md.count("<details>") == md.count("</details>")
    assert "זהו מתאם תצפיתי" in md                                  # observational framing kept
    assert ("חסר פידבק סטודנטים" in md) == (learned is None)
    assert "—" not in json.dumps(clean, ensure_ascii=False).replace(json.dumps(clean.get("item_dims")), "")


def test_guard_rejects_invented_numbers_and_banned_phrasing():
    facts = {"course": {"n_lessons": 10}, "x": [42]}
    bad = {"hero": {"sub": "נצפה ב-17 שיעורים. זה לא תרגול אלא הסבר."}}
    problems = narrative.check(bad, facts)
    assert any("17" in p for p in problems) and any("אלא" in p for p in problems)
    assert not narrative.check({"hero": {"sub": "נצפה ב-10 שיעורים, ב-42 פעמים."}}, facts)


def test_llm_path_falls_back_per_section(monkeypatch):
    cfg, lessons, taught, learned = _load("psychology")
    *_, facts = pipeline.compute(cfg, lessons, taught, learned)
    good_hero = {"h1": "הוראה חמה ומחוברת לחיים", "sub": "המימד הרגשי נצפה בכל 10 השיעורים."}
    reply = {"hero": good_hero, "insights": [{"title": "x", "text": "בשיעור 999 קרה משהו"}] * 3}
    usage = {"model": "claude-sonnet-5-5", "input_tokens": 1000, "output_tokens": 100}
    monkeypatch.setattr(narrative, "_call_llm", lambda facts, feedback=None, model=None: (reply, usage))
    narr, meta = narrative.build_narrative(facts, use_llm=True, log=lambda m: None)
    assert narr["hero"] == good_hero                       # valid section kept
    assert "999" not in json.dumps(narr["insights"], ensure_ascii=False)  # invalid section replaced
    assert meta["source"] == "llm" and meta["violations"]
    assert meta["calls"] == 2 and meta["cost_usd_est"] == round(2 * (1000 * 2 + 100 * 10) / 1e6, 4)  # first call + one retry
