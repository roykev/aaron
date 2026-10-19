"""Command line: course-reports {build,batch,items,eval}.

  build  inputs -> analysis.json + report.html / report.md
  batch  build every course in a manifest, write summary.json
  items  list parsed report items and their keys (for reviewing the dimension mapping)
  eval   compare the computed analysis with a hand-made golden analysis.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

from . import pipeline
from .render_html import logo_data_uri, render
from .render_md import render_md


def _cfg(args):
    cfg = json.loads(Path(args.course).read_text(encoding="utf-8")) if args.course else {}
    if args.name:
        cfg["name"] = args.name
    if not cfg.get("name"):
        raise SystemExit("course name is required: --name or a course.json with a 'name' field")
    return cfg


def build_course(cfg, reports, out, slug, learned=None, fmt="both", use_llm=True, classifier="lexicon",
                 model=None, overrides=None, analysis_path=None, logo=None, artifact=False, log=print, first_reply=None):
    """Build one course: compute (or load a reviewed) analysis.json and render it. Returns the analysis."""
    if analysis_path:  # re-render a reviewed analysis.json without recomputing
        from .ingest import load_course
        lessons, taught, learned_d = load_course(reports, learned)
        analysis = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
        pipeline.refresh_dim_states(analysis, len(lessons))
        if cfg.get("student_noun"):  # analysis files written before student_noun joined the render contract
            analysis["course"].setdefault("student_noun", cfg["student_noun"])
    else:
        lessons, taught, learned_d, analysis = pipeline.run(
            reports, cfg, learned_path=learned, use_llm=use_llm,
            classifier=classifier, overrides=overrides, model=model, log=log, first_reply=first_reply)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{slug}.analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=1), encoding="utf-8")
    clean = {k: v for k, v in analysis.items() if not k.startswith("_")}
    dims = pipeline.load_dims()
    fmts = {"html", "md"} if fmt == "both" else {fmt}
    if "html" in fmts:
        html = render(lessons, clean, dims, standalone=not artifact,
                      logo=logo_data_uri(logo or (pipeline.ASSETS / "aaronowl-logo.png")),
                      taught=taught or None, learned=learned_d)
        (out / f"{slug}.html").write_text(html, encoding="utf-8")
    if "md" in fmts:
        (out / f"{slug}.md").write_text(render_md(lessons, clean, dims, taught or None, learned_d), encoding="utf-8")
    src = analysis.get("_meta", {}).get("narrative", {}).get("source", "reviewed")
    log(f"wrote {out}/{slug}.[{','.join(sorted(fmts))}] + analysis.json · {len(lessons)} lessons · narrative: {src}")
    analysis.setdefault("_meta", {})["n_lessons"] = len(lessons)
    return analysis


def cmd_build(args):
    cfg = _cfg(args)
    overrides = json.loads(Path(args.overrides).read_text(encoding="utf-8")) if args.overrides else None
    build_course(cfg, args.reports, args.out, args.slug or "report", learned=args.learned, fmt=args.format,
                 use_llm=not args.no_llm, classifier=args.classifier, model=args.model, overrides=overrides,
                 analysis_path=args.analysis, logo=args.logo, artifact=args.artifact,
                 log=lambda m: print(m, file=sys.stderr))


def _slugify(name, i):
    s = re.sub(r"[^\w\-]+", "-", name, flags=re.U).strip("-").lower()
    return s or f"course-{i}"


def cmd_batch(args):
    """Build every course in a manifest. Keeps going on failure; exits non-zero if any course failed."""
    mpath = Path(args.manifest)
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    courses = manifest.get("courses", manifest) if isinstance(manifest, dict) else manifest
    base = mpath.parent
    out = Path(args.out)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    rel = lambda x: str(x if Path(x).is_absolute() else base / x)
    slugs, seen = [], set()
    for i, c in enumerate(courses, 1):
        slug = c.get("slug") or _slugify(c.get("name", ""), i)
        while slug in seen:
            slug += f"-{i}"
        seen.add(slug)
        slugs.append(slug)
    inputs = lambda c: ([rel(r) for r in ([c["reports"]] if isinstance(c["reports"], str) else c["reports"])],
                        rel(c["learned"]) if c.get("learned") else None,
                        {k: v for k, v in c.items() if k not in ("reports", "learned", "slug")})

    replies, batch_errors = {}, {}
    if args.llm_batch and not args.no_llm:  # phase 1: every course's narrative request in one Message Batch
        from . import llm_batch
        facts = {}
        for i, c in enumerate(courses):
            try:
                reports, learned, cfg = inputs(c)
                facts[f"c{i}"] = pipeline.course_facts(reports, cfg, learned, args.classifier)
            except Exception:
                pass  # phase 2 rebuilds this course and records the real error
        if facts:
            replies, batch_errors = llm_batch.run(facts, out, model=args.model, batch_id=args.batch_id, poll=args.poll)

    summary = []
    for i, (c, slug) in enumerate(zip(courses, slugs), 1):
        lines = []
        with open(out / "logs" / f"{slug}.log", "w", encoding="utf-8") as fh:
            def log(m, fh=fh):
                lines.append(m)
                fh.write(m + "\n")
                fh.flush()
            row = {"slug": slug, "name": c.get("name", "")}
            try:
                if not c.get("name"):
                    raise ValueError("course entry has no 'name'")
                if not c.get("reports"):
                    raise ValueError("course entry has no 'reports'")
                reports, learned, cfg = inputs(c)
                cid = f"c{i - 1}"
                if cid in batch_errors:
                    log(f"narrative: batch request failed ({batch_errors[cid]}); calling the model directly")
                with _stderr_to(log):
                    a = build_course(cfg, reports, out, slug, learned=learned,
                                     fmt=args.format, use_llm=not args.no_llm, classifier=args.classifier,
                                     model=args.model, log=log, first_reply=replies.get(cid))
                nar = a.get("_meta", {}).get("narrative", {})
                row.update(status="ok", lessons=a["_meta"].get("n_lessons"), narrative_source=nar.get("source"),
                           llm_cost_usd_est=nar.get("cost_usd_est"), llm_batch=nar.get("batch"),
                           guard_violations=nar.get("violations", []), narrative_error=nar.get("error"),
                           warnings=[m for m in lines if m.startswith("warning")])
            except Exception as e:  # keep going; the summary records the failure
                import traceback
                log(traceback.format_exc())
                row.update(status="failed", error=f"{e.__class__.__name__}: {e}")
        summary.append({k: v for k, v in row.items() if v not in (None, [])})
        print(f"[{i}/{len(courses)}] {slug}: {row['status']}" + (f" ({row.get('error')})" if row["status"] == "failed" else
              f" · {row.get('lessons')} lessons · narrative {row.get('narrative_source')}"), file=sys.stderr)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    failed = [r["slug"] for r in summary if r["status"] != "ok"]
    cost = sum(r.get("llm_cost_usd_est") or 0 for r in summary)
    print(f"batch: {len(summary) - len(failed)} ok, {len(failed)} failed · LLM ~${cost:.3f} · {out / 'summary.json'}")
    if failed:
        raise SystemExit(1)


class _stderr_to:
    """Route the parsers' stderr notes into the course log while a course builds."""

    def __init__(self, log):
        self.log = log

    def write(self, s):
        for line in s.splitlines():
            if line.strip():
                self.log(line)

    def flush(self):
        pass

    def __enter__(self):
        self._old, sys.stderr = sys.stderr, self
        return self

    def __exit__(self, *exc):
        sys.stderr = self._old


def cmd_items(args):
    from .ingest import load_course
    from .signals import LexiconClassifier, iter_items
    lessons, _, _ = load_course(args.reports)
    clf = LexiconClassifier()
    for key, kind, n, title, body in iter_items(lessons):
        print(f"{key:<6} {kind} {','.join(clf.classify(title, body)) or '-':<8} {title}")


def cmd_eval(args):
    from .ingest import load_course
    from . import signals as S
    cfg = _cfg(args)
    lessons, taught, learned = load_course(args.reports, args.learned)
    item_dims, themes, units, facts = pipeline.compute(cfg, lessons, taught, learned, args.classifier)
    gold = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    g = gold["item_dims"]
    keys = [k for k in item_dims if k in g]
    top1 = sum(1 for k in keys if item_dims[k] and item_dims[k][0] in g[k]) / len(keys)
    overlap = sum(1 for k in keys if set(item_dims[k]) & set(g[k])) / len(keys)
    ids = [d["id"] for d in pipeline.load_dims()["dims"]]
    sp, sg = S.dim_signals(item_dims, ids), S.dim_signals(g, ids)
    lv = lambda st: int(S.dim_state(st, len(lessons))["level"][1])
    exact = sum(1 for d in ids if lv(sp[d]) == lv(sg[d]))
    near = sum(1 for d in ids if abs(lv(sp[d]) - lv(sg[d])) <= 1)
    gold_adopt = {a["rec"]: a["status"] for a in gold.get("adopt", [])}
    report = {"items": len(keys), "top1_in_gold": round(top1, 3), "any_overlap": round(overlap, 3),
              "dim_level_exact": f"{exact}/16", "dim_level_within_one": f"{near}/16",
              "recurring_themes": [(t["id"], len(t["lessons"]), t["status"]) for t in themes if len(t["lessons"]) >= 2],
              "golden_adoption": gold_adopt}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if args.min_overlap and overlap < args.min_overlap:
        raise SystemExit(f"any_overlap {overlap:.2f} is below --min-overlap {args.min_overlap}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="course-reports", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--reports", nargs="+", required=True, help="Aaron export JSON (recommended) and/or Teaching Snapshot .txt files")
        p.add_argument("--learned", help="course learning report (Aaron 'what students learned' .md)")
        p.add_argument("--course", help="course.json: name, student_noun, optional units/title")
        p.add_argument("--name", help="course name (overrides course.json)")
        p.add_argument("--classifier", choices=["lexicon", "embeddings"], default="lexicon")

    b = sub.add_parser("build")
    common(b)
    b.add_argument("--out", required=True, help="output directory")
    b.add_argument("--slug", help="output file name stem")
    b.add_argument("--format", choices=["html", "md", "both"], default="both")
    b.add_argument("--no-llm", action="store_true", help="deterministic prose only (no API call)")
    b.add_argument("--model", help="LLM model id (default: env AARON_LLM_MODEL)")
    b.add_argument("--overrides", help="JSON deep-merged over the generated analysis (human edits)")
    b.add_argument("--analysis", help="render this reviewed analysis.json instead of recomputing")
    b.add_argument("--logo", help="logo file for the seal")
    b.add_argument("--artifact", action="store_true", help="HTML without <!doctype>/<head> wrapper")
    b.set_defaults(fn=cmd_build)

    bt = sub.add_parser("batch", help="build every course in a manifest")
    bt.add_argument("--manifest", required=True, help="JSON list of courses: course.json fields + reports, learned, slug")
    bt.add_argument("--out", required=True)
    bt.add_argument("--format", choices=["html", "md", "both"], default="both")
    bt.add_argument("--no-llm", action="store_true")
    bt.add_argument("--model")
    bt.add_argument("--classifier", choices=["lexicon", "embeddings"], default="lexicon")
    bt.add_argument("--llm-batch", action=argparse.BooleanOptionalAction, default=True,
                    help="send all narrative calls as one Message Batch: half price, minutes to hours (default); "
                         "--no-llm-batch calls the model per course")
    bt.add_argument("--batch-id", help="resume: collect the results of an already-submitted batch (see out/llm_batch.json)")
    bt.add_argument("--poll", type=int, default=30, help="seconds between batch status checks")
    bt.set_defaults(fn=cmd_batch)

    i = sub.add_parser("items")
    i.add_argument("--reports", nargs="+", required=True)
    i.set_defaults(fn=cmd_items)

    e = sub.add_parser("eval")
    common(e)
    e.add_argument("--golden", required=True)
    e.add_argument("--min-overlap", type=float)
    e.set_defaults(fn=cmd_eval)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
