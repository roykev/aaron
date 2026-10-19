"""P0 robustness: odd inputs, course length, batch mode, the review loop and the dimension-level contract.
Fixtures are derived from the real example exports, so they keep the real report markup."""
import json
import re
from pathlib import Path

import pytest

from course_reports import cli, narrative, pipeline
from course_reports import signals as S
from course_reports.ingest import load_course, parse_export
from course_reports.render_html import render
from course_reports.render_md import render_md

EX = Path(__file__).resolve().parents[1] / "examples"
PSY = EX / "psychology"
CFG = {"name": "מבוא לפסיכולוגיה", "student_noun": "סטודנטיות"}


def _rows(name="psychology"):
    return [r for r in json.loads((EX / name / "export.json").read_text(encoding="utf-8"))["rows"] if r.get("snapshot_report")]


def _export(tmp_path, rows, name="export.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"rows": rows}, ensure_ascii=False), encoding="utf-8")
    return p


def _retitle(rep, suffix):
    return re.sub(r"^(## (?!Outstanding|Long-Term|Successful|Opportunities|Recommended).+)$", r"\1" + suffix, rep, count=1, flags=re.M)


def _build(tmp_path, reports, learned=None, cfg=CFG):
    lessons, taught, learned_d, analysis = pipeline.run([reports], cfg, learned, use_llm=False, log=lambda m: None)
    clean = {k: v for k, v in analysis.items() if not k.startswith("_")}
    dims = pipeline.load_dims()
    html = render(lessons, clean, dims, standalone=True, taught=taught or None, learned=learned_d)
    md = render_md(lessons, clean, dims, taught or None, learned_d)
    assert not re.findall(r"__[A-Z_]+__", html)
    return lessons, analysis, html, md


def test_missing_snapshot_rows_are_skipped(tmp_path, capsys):
    rows = _rows()[:5]
    rows[2] = dict(rows[2], snapshot_report="")
    lessons = parse_export(_export(tmp_path, rows))
    assert len(lessons) == 4
    assert "has no snapshot report, skipped" in capsys.readouterr().err


def test_sections_without_titles_warn_and_render(tmp_path, capsys):
    lessons, taught, _ = load_course([PSY / "export.json"])
    err = capsys.readouterr().err
    assert "lesson 11: 7 of 7 class-report sections have no title" in err
    assert taught[11]["untitled"] and not taught[4]["untitled"]
    _, _, html, md = _build(tmp_path, PSY / "export.json")
    assert "אין חלוקה לנושאים בדוח השיעור" in md
    assert "t.untitled" in html


def test_duplicated_lesson_numbers_keep_the_richer_report(tmp_path, capsys):
    rows = _rows()[:4]
    poor = dict(rows[1], snapshot_report=_retitle(rows[1]["snapshot_report"], " (טיוטה)"), lecturer_report="",
                event_time=rows[1]["event_time"].replace("20", "21", 1))
    poor["snapshot_report"] = re.sub(r"## Opportunities for Enhancement.*?(?=^## )", "", poor["snapshot_report"], flags=re.S | re.M)
    lessons = parse_export(_export(tmp_path, rows + [poor]))
    assert [l["n"] for l in lessons] == [4, 5, 6, 7]
    assert "(טיוטה)" not in next(l for l in lessons if l["n"] == 5)["title"]
    assert "lesson 5 appears twice" in capsys.readouterr().err


ENGLISH = {"המסר המרכזי": "Key Message", "משך השיעור": "Lecture Duration", "למה זה חשוב": "Why it matters",
           "ההזדמנות": "The Opportunity", "הפתרון": "The Solution", "התועלת הפוטנציאלית": "Potential Benefit",
           "פעולה מלאה": "Full Action"}


def test_english_labels_parse_like_hebrew(tmp_path):
    rows = _rows()[3:6]
    en = []
    for r in rows:
        rep = r["snapshot_report"]
        for he, eng in ENGLISH.items():
            rep = rep.replace(he, eng)
        en.append(dict(r, snapshot_report=rep))
    he_l = parse_export(_export(tmp_path, rows, "he.json"))
    en_l = parse_export(_export(tmp_path, en, "en.json"))
    for a, b in zip(he_l, en_l):
        assert a["message"] and a["message"] == b["message"]
        assert a["duration"] == b["duration"]
        assert [o["solution"] for o in a["opportunities"]] == [o["solution"] for o in b["opportunities"]]
        assert all(o["solution"] for o in b["opportunities"])
        assert [x["text"] for x in a["actions"]] == [x["text"] for x in b["actions"]]


@pytest.mark.parametrize("n", [4, 20])
def test_short_and_long_courses_build(tmp_path, n):
    base = _rows()
    rows = base[:n] if n <= len(base) else base + [
        dict(r, name=f"שיעור {i + 14}", event_time=r["event_time"].replace("202", "203", 1),
             snapshot_report=_retitle(r["snapshot_report"], f" ({i + 14})"))
        for i, r in enumerate(base[: n - len(base)])]
    lessons, analysis, html, md = _build(tmp_path, _export(tmp_path, rows))
    assert len(lessons) == n
    assert len({l["n"] for l in lessons}) == n
    assert all(analysis["dims"][d]["level"] in {"l1", "l2", "l3", "l4", "l5"} for d in analysis["dims"])
    assert f'<a id="l{lessons[-1]["n"]}"></a>' in md


def test_levels_scale_with_course_length():
    sig = {"s": {1, 2, 3}, "w": set()}           # strength in 3 lessons
    assert S.dim_state(sig, 10)["level"] == "l4"  # 3 of 10: strength
    assert S.dim_state(sig, 4)["level"] == "l5"   # 3 of 4: outstanding
    assert S.dim_state(sig, 20)["level"] == "l3"  # 3 of 20: balanced
    assert S.dim_state({"s": set(range(1, 13)), "w": set()}, 20)["level"] == "l5"


def test_template_reads_levels_instead_of_recomputing():
    t = (pipeline.ASSETS / "template.html").read_text(encoding="utf-8")
    assert "LEVELS" not in t and "min: 6" not in t   # the rule lives only in signals.dim_state
    assert "d.level" in t


def test_no_class_reports_drops_report_01(tmp_path):
    rows = [dict(r, lecturer_report="") for r in _rows()]
    _, analysis, html, md = _build(tmp_path, _export(tmp_path, rows), PSY / "learning_report.md")
    assert [c["id"] for c in analysis["hub"]["reports"]] == ["how", "learned"]
    assert "דוח 01" not in md


def test_no_learning_report_shows_missing_card(tmp_path):
    _, analysis, _, md = _build(tmp_path, EX / "informal/export.json", cfg={"name": "חינוך בלתי פורמלי"})
    card = next(c for c in analysis["hub"]["reports"] if c["id"] == "learned")
    assert card.get("missing") and "חסר פידבק סטודנטים" in md


def test_rerender_reproduces_edits(tmp_path):
    out = tmp_path / "out"
    args = ["--reports", str(PSY / "export.json"), "--learned", str(PSY / "learning_report.md"),
            "--course", str(PSY / "course.json"), "--out", str(out), "--slug", "p"]
    cli.main(["build", *args, "--no-llm"])
    a = json.loads((out / "p.analysis.json").read_text(encoding="utf-8"))
    a["hero"]["h1"] = "כותרת שנערכה ביד"
    a["dims"]["LS"]["note"] = "הערה שנערכה ביד על הממד."
    before = a["dims"]["CH"]["level"]
    a["item_dims"] = {k: (["CH"] if k.endswith("O") else v) for k, v in a["item_dims"].items()}  # every outstanding item -> autonomy
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
    cli.main(["build", *args, "--analysis", str(edited)])
    html = (out / "p.html").read_text(encoding="utf-8")
    md = (out / "p.md").read_text(encoding="utf-8")
    for s in ("כותרת שנערכה ביד", "הערה שנערכה ביד על הממד."):
        assert s in html and s in md
    again = json.loads((out / "p.analysis.json").read_text(encoding="utf-8"))
    assert before != "l5" and again["dims"]["CH"]["level"] == "l5"  # level recomputed from the edited mapping
    assert 'class="tile l5" id="dim-CH"' not in html  # tiles are built in JS from analysis.dims, not baked in
    assert '"CH": {' in html or '"CH":{' in html


def test_batch_keeps_going_and_reports(tmp_path):
    manifest = [
        {"name": "מבוא לפסיכולוגיה", "student_noun": "סטודנטיות", "slug": "psy",
         "reports": str(PSY / "export.json"), "learned": str(PSY / "learning_report.md")},
        {"name": "קורס שבור", "slug": "broken", "reports": [str(tmp_path / "missing.json")]},
        {"name": "חינוך בלתי פורמלי", "slug": "informal", "reports": str(EX / "informal/export.json")},
    ]
    m = tmp_path / "courses.json"
    m.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        cli.main(["batch", "--manifest", str(m), "--out", str(tmp_path / "out"), "--no-llm"])
    assert e.value.code == 1
    summary = {r["slug"]: r for r in json.loads((tmp_path / "out/summary.json").read_text(encoding="utf-8"))}
    assert summary["psy"]["status"] == "ok" and summary["informal"]["status"] == "ok"
    assert summary["broken"]["status"] == "failed" and "FileNotFoundError" in summary["broken"]["error"]
    assert summary["psy"]["narrative_source"] == "fallback" and summary["psy"]["lessons"] == 10
    assert (tmp_path / "out/informal.html").exists() and (tmp_path / "out/logs/broken.log").read_text(encoding="utf-8")
    assert any("no title" in w for w in summary["informal"]["warnings"])


def test_guard_catches_spelled_out_numbers():
    facts = {"course": {"n_lessons": 10}}
    assert narrative.check({"x": "נצפה בעשרת השיעורים"}, facts) == []
    assert any("שבעה" in p for p in narrative.check({"x": "נצפה בשבעה שיעורים"}, facts))
    assert narrative.check({"x": "שלושה שיעורים"}, facts) == []  # 0-5 are always allowed
