#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
editor_server_v2.py

Run:
  python editor_server_v2.py

Open:
  http://127.0.0.1:8765

What it does:
- In-browser editor for Concepts and Quiz JSON.
- Choose type (Concepts / Quiz) in the UI.
- Load JSON via Paste or Upload.
- Edit/add/delete.
- Validate.
- Save / Save As to server folder: ./saved/<name>.json

Important limitation:
- A browser cannot expose the absolute path of an uploaded file, so the server cannot overwrite it.
  "Save" overwrites the currently selected server-side save target (default ./saved/untitled.json).
"""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8765

SAVED_DIR = os.path.realpath(os.path.join(os.getcwd(), "saved"))
os.makedirs(SAVED_DIR, exist_ok=True)


# -----------------------------
# Helpers
# -----------------------------

def write_text_atomic(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)

def safe_join_saved(user_rel_path: str) -> str:
    """Restrict save paths to ./saved/ (prevents path traversal)."""
    p = (user_rel_path or "").strip()
    if not p:
        raise ValueError("Empty save path")
    if p.startswith("/") or p.startswith("\\") or ":" in p:
        raise ValueError("Save path must be relative (no drive/absolute paths)")
    cand = os.path.realpath(os.path.join(SAVED_DIR, p))
    if not cand.startswith(SAVED_DIR + os.sep) and cand != SAVED_DIR:
        raise ValueError("Save path must stay within ./saved")
    return cand

def json_response(handler: BaseHTTPRequestHandler, obj, status=200):
    payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)

def text_response(handler: BaseHTTPRequestHandler, text: str, status=200, content_type="text/html; charset=utf-8"):
    payload = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)

def parse_json_body(handler: BaseHTTPRequestHandler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    return json.loads(raw.decode("utf-8"))


# -----------------------------
# Concepts: validate/normalize
# -----------------------------

TIME_RE = re.compile(r"^\s*(\d{1,2}:)?\d{1,2}:\d{1,2}\s*$")  # mm:ss or hh:mm:ss

def parse_time_to_secs(s: str):
    """
    Accept mm:ss or hh:mm:ss
    Return dict: {ok, secs, norm, err, suggestion}
    If mm/ss >=60 => invalid + carry suggestion.
    """
    if not isinstance(s, str):
        return {"ok": False, "err": "Time must be a string"}
    t = s.strip()
    if not t:
        return {"ok": False, "err": "Empty time"}
    if not TIME_RE.match(t):
        return {"ok": False, "err": "Invalid format (mm:ss or hh:mm:ss)"}

    parts = [p.strip() for p in t.split(":")]
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return {"ok": False, "err": "Time must contain integers"}

    if len(nums) == 2:
        hh = 0
        mm, ss = nums
    else:
        hh, mm, ss = nums

    if hh < 0 or mm < 0 or ss < 0:
        return {"ok": False, "err": "Negative not allowed"}

    total = hh * 3600 + mm * 60 + ss

    if mm >= 60 or ss >= 60:
        nh = total // 3600
        nm = (total % 3600) // 60
        ns = total % 60
        suggestion = f"{nh:02d}:{nm:02d}:{ns:02d}"
        return {"ok": False, "err": "Minutes/seconds must be < 60", "suggestion": suggestion}

    norm = f"{hh:02d}:{mm:02d}:{ss:02d}"
    return {"ok": True, "secs": total, "norm": norm}

def normalize_concepts(data: dict) -> dict:
    out = {"concepts": []}
    concepts = data.get("concepts", [])
    if not isinstance(concepts, list):
        concepts = []

    for c in concepts:
        if not isinstance(c, dict):
            continue
        name = str(c.get("concept", "")).strip()
        times_in = c.get("times", [])
        if not isinstance(times_in, list):
            times_in = []
        times_out = []
        for seg in times_in:
            if not isinstance(seg, dict):
                continue
            s = str(seg.get("start", "")).strip()
            e = str(seg.get("end", "")).strip()
            ps = parse_time_to_secs(s)
            pe = parse_time_to_secs(e)
            if ps.get("ok"):
                s = ps["norm"]
            if pe.get("ok"):
                e = pe["norm"]
            times_out.append({"start": s, "end": e})

        def seg_key(seg):
            p = parse_time_to_secs(seg.get("start", ""))
            return (0, p["secs"]) if p.get("ok") else (1, 10**12)
        times_out.sort(key=seg_key)

        out["concepts"].append({"concept": name, "times": times_out})

    out["concepts"].sort(key=lambda x: (x.get("concept", "").lower(),))
    return out

def validate_concepts(data: dict) -> list[dict]:
    issues = []
    if not isinstance(data, dict) or "concepts" not in data or not isinstance(data["concepts"], list):
        return [{"where": "root", "field": "concepts", "message": "Missing concepts[]"}]

    for ci, c in enumerate(data["concepts"]):
        if not isinstance(c, dict):
            issues.append({"where": f"concept[{ci}]", "field": "concept", "message": "Concept must be object"})
            continue

        name = str(c.get("concept", "")).strip()
        if not name:
            issues.append({"where": f"concept[{ci}]", "field": "concept", "message": "Empty concept name"})

        times = c.get("times")
        if not isinstance(times, list) or len(times) == 0:
            issues.append({"where": f"concept[{ci}]", "field": "times", "message": "No time segments"})
            continue

        for si, seg in enumerate(times):
            if not isinstance(seg, dict):
                issues.append({"where": f"concept[{ci}].times[{si}]", "field": "segment", "message": "Segment must be object"})
                continue
            s = str(seg.get("start", ""))
            e = str(seg.get("end", ""))

            ps = parse_time_to_secs(s)
            pe = parse_time_to_secs(e)

            if not ps.get("ok"):
                issues.append({"where": f"concept[{ci}].times[{si}]", "field": "start",
                              "message": ps.get("err"), "value": s, "suggestion": ps.get("suggestion")})
            if not pe.get("ok"):
                issues.append({"where": f"concept[{ci}].times[{si}]", "field": "end",
                              "message": pe.get("err"), "value": e, "suggestion": pe.get("suggestion")})

            if ps.get("ok") and pe.get("ok"):
                if ps["secs"] >= pe["secs"]:
                    issues.append({"where": f"concept[{ci}].times[{si}]", "field": "range",
                                  "message": "Start must be < End",
                                  "value": f"{ps['norm']}..{pe['norm']}"})
    return issues


# -----------------------------
# Quiz: validate/normalize
# -----------------------------

def normalize_quiz(data: dict) -> dict:
    """
    Adds per-question: allow_multiple_correct (default False).
    correct stored as string "true" (your schema).
    """
    out = {"questions": []}
    questions = data.get("questions", [])
    if not isinstance(questions, list):
        questions = []

    for q in questions:
        if not isinstance(q, dict):
            continue

        qt = str(q.get("question", "")).strip()
        allow_multi = bool(q.get("allow_multiple_correct", False))

        answers_in = q.get("answers", [])
        if not isinstance(answers_in, list):
            answers_in = []
        answers_out = []
        for a in answers_in:
            if not isinstance(a, dict):
                continue
            choice = str(a.get("choice", "")).strip()
            obj = {"choice": choice}
            if a.get("correct") == "true":
                obj["correct"] = "true"
            answers_out.append(obj)

        out["questions"].append({
            "question": qt,
            "allow_multiple_correct": allow_multi,
            "answers": answers_out
        })
    return out

def validate_quiz(data: dict) -> list[dict]:
    issues = []
    if not isinstance(data, dict) or "questions" not in data or not isinstance(data["questions"], list):
        return [{"where": "root", "field": "questions", "message": "Missing questions[]"}]

    for qi, q in enumerate(data["questions"]):
        if not isinstance(q, dict):
            issues.append({"where": f"question[{qi}]", "field": "question", "message": "Question must be object"})
            continue

        text = str(q.get("question", "")).strip()
        if not text:
            issues.append({"where": f"question[{qi}]", "field": "question", "message": "Empty question text"})

        answers = q.get("answers")
        if not isinstance(answers, list) or len(answers) < 2:
            issues.append({"where": f"question[{qi}]", "field": "answers", "message": "Must have at least 2 answers"})
            continue

        correct_idxs = []
        for ai, a in enumerate(answers):
            if not isinstance(a, dict):
                issues.append({"where": f"question[{qi}].answers[{ai}]", "field": "answer", "message": "Answer must be object"})
                continue
            choice = str(a.get("choice", "")).strip()
            if not choice:
                issues.append({"where": f"question[{qi}].answers[{ai}]", "field": "choice", "message": "Empty answer text"})
            if a.get("correct") == "true":
                correct_idxs.append(ai)

        if len(correct_idxs) == 0:
            issues.append({"where": f"question[{qi}]", "field": "correct", "message": "No correct answer marked"})

        allow_multi = bool(q.get("allow_multiple_correct", False))
        if not allow_multi and len(correct_idxs) > 1:
            issues.append({"where": f"question[{qi}]", "field": "correct",
                          "message": "Multiple correct not allowed (toggle is OFF)",
                          "value": str(len(correct_idxs))})

    return issues


# -----------------------------
# Session state (in-memory)
# -----------------------------

STATE = {
    "doc_type": "concepts",             # "concepts" | "quiz"
    "filename": "untitled.json",        # just for UI
    "save_rel_path": "untitled.json",   # relative inside ./saved/
    "data": {"concepts": []},           # current doc
}


# -----------------------------
# HTML UI (single page)
# -----------------------------

INDEX_HTML = r"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Editor: Quiz / Concepts</title>
<style>
:root{
  --bg:#E6ECF9; --card:#fff; --border:#D4E9C5; --primary:#2E6BCF; --pweak:rgba(46,107,207,.12);
  --danger:#b42318; --dweak:rgba(180,35,24,.08); --text:#1f2a44; --muted:#6c7a96;
  --shadow:0 10px 30px rgba(20,35,80,.08); --r:14px; --rs:10px;
}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:var(--bg);color:var(--text)}
.wrap{max-width:1100px;margin:18px auto;padding:0 14px 22px}
.panel{background:var(--card);border-radius:var(--r);box-shadow:var(--shadow);border:1px solid rgba(46,107,207,.10);overflow:hidden}
.toolbar{position:sticky;top:0;z-index:10;background:#fff;padding:12px 14px;border-bottom:1px solid rgba(46,107,207,.10);
display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
.title h1{margin:0;font-size:16px;font-weight:800}
.sub{font-size:12px;color:var(--muted)}
.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.btn{border:1px solid rgba(46,107,207,.18);background:#fff;color:var(--text);padding:8px 12px;border-radius:10px;font-size:13px;cursor:pointer;white-space:nowrap}
.btn:hover{background:rgba(46,107,207,.06)}
.btn.primary{background:var(--primary);color:#fff;border-color:var(--primary)}
.btn.primary:hover{filter:brightness(.96)}
.btn.ghost{border-color:transparent;color:var(--muted)}
.btn.danger{border-color:rgba(180,35,24,.25);color:var(--danger)}
.input, select{width:100%;border:1px solid var(--border);border-radius:12px;padding:9px 10px;font-size:13px;outline:none;background:#fff}
.input:focus, select:focus{border-color:rgba(46,107,207,.55);box-shadow:0 0 0 3px rgba(46,107,207,.10)}
.content{padding:12px 14px 16px}
.toprow{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:12px}
.status{font-size:12px;color:var(--muted);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:11px;padding:3px 8px;border-radius:999px;background:var(--pweak);color:var(--primary);border:1px solid rgba(46,107,207,.16)}
.badge.bad{background:var(--dweak);color:var(--danger);border-color:rgba(180,35,24,.18)}
.grid{display:grid;gap:12px}
.card{border:1px solid var(--border);border-radius:var(--r);background:#fff;padding:12px}
.cardhead{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.cardhead .left{flex:1;min-width:260px}
.cardhead .right{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.label{font-size:12px;color:var(--muted);margin:0 0 6px}
.times{display:grid;gap:8px}
.timeRow{display:grid;grid-template-columns:1fr 1fr auto auto;gap:8px;align-items:center;padding:8px;border-radius:var(--rs);
border:1px solid rgba(212,233,197,.85);background:#fff}
.timeRow.invalid{border-color:rgba(180,35,24,.25);background:var(--dweak)}
.mini{border:1px solid rgba(46,107,207,.18);background:#fff;padding:7px 10px;border-radius:10px;font-size:12px;cursor:pointer;color:var(--text);white-space:nowrap}
.mini:hover{background:rgba(46,107,207,.06)}
.mini.primary{border-color:rgba(46,107,207,.18);color:var(--primary);background:rgba(46,107,207,.06)}
.mini.danger{border-color:rgba(180,35,24,.25);color:var(--danger)}
.msg{margin-top:6px;font-size:12px;color:var(--danger);display:none}
.msg.show{display:block}
hr.sep{border:none;border-top:1px solid rgba(46,107,207,.10);margin:10px 0}
.small{font-size:12px;color:var(--muted)}

.qAnswers{display:grid;gap:8px}
.ansRow{display:grid;grid-template-columns:34px 1fr auto;gap:8px;align-items:center;padding:8px;border-radius:var(--rs);
border:1px solid rgba(212,233,197,.85);background:#fff}
.ansRow.correct{background:rgba(210,237,190,.35);border-color:rgba(210,237,190,.9)}
.ansRow.invalid{border-color:rgba(180,35,24,.25);background:var(--dweak)}
.ansRow input[type="radio"], .ansRow input[type="checkbox"]{width:16px;height:16px;accent-color:var(--primary);margin:0 auto;cursor:pointer}

.modal{position:fixed;inset:0;background:rgba(0,0,0,.25);display:none;align-items:center;justify-content:center;padding:16px;z-index:50}
.modal.open{display:flex}
.modalbox{width:min(760px,96vw);background:#fff;border-radius:14px;border:1px solid rgba(46,107,207,.10);box-shadow:var(--shadow);overflow:hidden}
.modalhead{padding:12px 14px;border-bottom:1px solid rgba(46,107,207,.10);display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.modalbody{padding:12px 14px 14px}
textarea.jsonbox{width:100%;min-height:300px;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;font-size:12px}
.row2{display:flex;gap:10px;flex-wrap:wrap}
.row2 > div{flex:1;min-width:220px}
</style>
</head>
<body>
<div class="wrap">
  <div class="panel">
    <div class="toolbar">
      <div class="title">
        <h1>Editor: Quiz / Concepts</h1>
        <div class="sub">
          Doc type + Load inside the page • Save writes to <b>./saved/</b>
        </div>
      </div>
      <div class="controls">
        <button class="btn" id="pasteBtn">Paste JSON</button>
        <button class="btn" id="uploadBtn">Upload JSON</button>
        <input id="fileInput" type="file" accept=".json,application/json,text/plain" style="display:none"/>
        <button class="btn ghost" id="reloadBtn">Reload last saved</button>
        <button class="btn" id="saveAsBtn">Save As…</button>
        <button class="btn primary" id="saveBtn">Save</button>
      </div>
    </div>

    <div class="content">
      <div class="toprow">
        <div class="row2" style="width:100%">
          <div>
            <div class="label">Doc type</div>
            <select id="docType">
              <option value="concepts">Concepts</option>
              <option value="quiz">Quiz</option>
            </select>
          </div>
          <div>
            <div class="label">Save target (relative to ./saved/)</div>
            <input class="input" id="saveTarget" placeholder="e.g. concepts.v2.json" />
            <div class="small" id="saveTargetHint"></div>
          </div>
          <div>
            <div class="label">Search</div>
            <input class="input" id="search" placeholder="Search..." />
          </div>
        </div>
      </div>

      <div class="toprow">
        <div class="status">
          <span class="badge" id="countBadge">0</span>
          <span class="badge bad" id="issuesBadge" style="display:none">0 issues</span>
          <span id="statusText">Ready.</span>
        </div>
        <button class="btn" id="addBtn">+ Add</button>
      </div>

      <div id="cards" class="grid"></div>
    </div>
  </div>
</div>

<!-- Paste modal -->
<div class="modal" id="pasteModal" aria-hidden="true">
  <div class="modalbox">
    <div class="modalhead">
      <strong>Paste JSON</strong>
      <div class="controls">
        <button class="btn ghost" id="closePaste">Close</button>
        <button class="btn primary" id="applyPaste">Load</button>
      </div>
    </div>
    <div class="modalbody">
      <textarea class="input jsonbox" id="pasteArea" spellcheck="false"></textarea>
      <div class="small" style="margin-top:8px">
        For Concepts: <code>{"concepts":[...]}</code> • For Quiz: <code>{"questions":[...]}</code>
      </div>
    </div>
  </div>
</div>

<!-- Save As modal -->
<div class="modal" id="saveModal" aria-hidden="true">
  <div class="modalbox">
    <div class="modalhead">
      <strong>Save As</strong>
      <div class="controls">
        <button class="btn ghost" id="closeSaveAs">Close</button>
        <button class="btn primary" id="confirmSaveAs">Save</button>
      </div>
    </div>
    <div class="modalbody">
      <div class="small">Relative path within <b>./saved/</b></div>
      <input class="input" id="saveAsPath" placeholder="new_file.json" />
    </div>
  </div>
</div>

<script>
let state = null;     // current doc data
let docType = "concepts";
let dirty = false;
let issues = [];

const cardsEl = document.getElementById("cards");
const searchEl = document.getElementById("search");
const docTypeEl = document.getElementById("docType");
const countBadge = document.getElementById("countBadge");
const issuesBadge = document.getElementById("issuesBadge");
const statusText = document.getElementById("statusText");
const addBtn = document.getElementById("addBtn");
const reloadBtn = document.getElementById("reloadBtn");
const saveBtn = document.getElementById("saveBtn");
const saveAsBtn = document.getElementById("saveAsBtn");
const saveTarget = document.getElementById("saveTarget");
const saveTargetHint = document.getElementById("saveTargetHint");

const pasteBtn = document.getElementById("pasteBtn");
const uploadBtn = document.getElementById("uploadBtn");
const fileInput = document.getElementById("fileInput");

const pasteModal = document.getElementById("pasteModal");
const pasteArea = document.getElementById("pasteArea");
const closePaste = document.getElementById("closePaste");
const applyPaste = document.getElementById("applyPaste");

const saveModal = document.getElementById("saveModal");
const saveAsPath = document.getElementById("saveAsPath");
const closeSaveAs = document.getElementById("closeSaveAs");
const confirmSaveAs = document.getElementById("confirmSaveAs");

function setStatus(msg){ statusText.textContent = msg; }
function setDirty(v=true){
  dirty=v;
  setStatus(dirty ? "Unsaved changes." : "Saved / Clean.");
}

function openModal(m){ m.classList.add("open"); m.setAttribute("aria-hidden","false"); }
function closeModal(m){ m.classList.remove("open"); m.setAttribute("aria-hidden","true"); }

closePaste.addEventListener("click", ()=>closeModal(pasteModal));
pasteModal.addEventListener("click", (e)=>{ if(e.target===pasteModal) closeModal(pasteModal); });
closeSaveAs.addEventListener("click", ()=>closeModal(saveModal));
saveModal.addEventListener("click", (e)=>{ if(e.target===saveModal) closeModal(saveModal); });

function filtered(list, keyFn){
  const q = (searchEl.value||"").trim().toLowerCase();
  if(!q) return list;
  return list.filter(x => (keyFn(x)||"").toLowerCase().includes(q));
}

async function apiGetState(){
  const r = await fetch("/api/state");
  const j = await r.json();
  if(!j.ok){ alert(j.error); return; }
  docType = j.doc_type;
  state = j.data;
  docTypeEl.value = docType;
  saveTarget.value = j.save_rel_path || "untitled.json";
  saveTargetHint.textContent = "Full path: ./saved/" + saveTarget.value;
  dirty = false;
  await apiValidate();
  render();
  setStatus("Loaded last saved (server session).");
}

async function apiSetType(newType){
  const r = await fetch("/api/set_type", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ doc_type: newType })
  });
  const j = await r.json();
  if(!j.ok){ alert(j.error); return; }
  docType = j.doc_type;
  state = j.data;
  dirty = false;
  await apiValidate();
  render();
}

async function apiLoadJson(obj, filenameHint){
  const r = await fetch("/api/load_json", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ doc_type: docType, data: obj, filename: filenameHint || "untitled.json" })
  });
  const j = await r.json();
  if(!j.ok){ alert(j.error); return; }
  state = j.data;
  saveTarget.value = j.save_rel_path || "untitled.json";
  saveTargetHint.textContent = "Full path: ./saved/" + saveTarget.value;
  dirty = true;
  await apiValidate();
  render();
  setStatus("Loaded JSON into editor.");
}

async function apiValidate(){
  const r = await fetch("/api/validate", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ doc_type: docType, data: state })
  });
  const j = await r.json();
  if(!j.ok){ alert(j.error); return; }
  issues = j.issues || [];
  issuesBadge.style.display = issues.length ? "inline-flex" : "none";
  issuesBadge.textContent = issues.length ? (issues.length + " issues") : "";
  saveBtn.disabled = issues.length > 0;
}

async function apiSave(mode, relPath){
  const target = (mode==="overwrite") ? (saveTarget.value||"untitled.json") : relPath;
  const r = await fetch("/api/save", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ doc_type: docType, data: state, save_rel_path: target })
  });
  const j = await r.json();
  if(!j.ok){ alert("Save failed: " + j.error); return false; }
  saveTarget.value = j.save_rel_path;
  saveTargetHint.textContent = "Full path: ./saved/" + saveTarget.value;
  setDirty(false);
  await apiValidate();
  render();
  setStatus(j.message || "Saved.");
  return true;
}


// ------------------
// Concepts UI
// ------------------
const TIME_RE = /^\s*(\d{1,2}:)?\d{1,2}:\d{1,2}\s*$/;

function parseTimeToSecs(s){
  if(typeof s !== "string") return {ok:false, err:"Time must be a string"};
  const t = s.trim();
  if(!t) return {ok:false, err:"Empty time"};
  if(!TIME_RE.test(t)) return {ok:false, err:"Format mm:ss or hh:mm:ss"};
  const parts = t.split(":").map(x=>x.trim());
  const nums = parts.map(x=>Number(x));
  if(nums.some(n=>!Number.isFinite(n))) return {ok:false, err:"Must be integers"};
  let hh=0, mm=0, ss=0;
  if(nums.length===2){ mm=nums[0]; ss=nums[1]; } else { hh=nums[0]; mm=nums[1]; ss=nums[2]; }
  if(hh<0||mm<0||ss<0) return {ok:false, err:"Negative not allowed"};
  const total = hh*3600 + mm*60 + ss;
  if(mm>=60 || ss>=60){
    const nh=Math.floor(total/3600);
    const nm=Math.floor((total%3600)/60);
    const ns=total%60;
    const sug = String(nh).padStart(2,"0")+":"+String(nm).padStart(2,"0")+":"+String(ns).padStart(2,"0");
    return {ok:false, err:"Minutes/seconds must be < 60", suggestion:sug};
  }
  const norm = String(hh).padStart(2,"0")+":"+String(mm).padStart(2,"0")+":"+String(ss).padStart(2,"0");
  return {ok:true, secs:total, norm};
}

function conceptsSortInPlace(){
  for(const c of state.concepts){
    c.times.sort((a,b)=>{
      const pa=parseTimeToSecs(a.start||"");
      const pb=parseTimeToSecs(b.start||"");
      if(pa.ok && pb.ok) return pa.secs - pb.secs;
      if(pa.ok) return -1;
      if(pb.ok) return 1;
      return 0;
    });
  }
  state.concepts.sort((a,b)=> (a.concept||"").localeCompare((b.concept||""), "he", {sensitivity:"base"}));
}

function renderConcepts(){
  conceptsSortInPlace();
  const list = filtered(state.concepts, c=>c.concept);
  countBadge.textContent = state.concepts.length + " concepts";

  cardsEl.innerHTML = "";
  list.forEach((c)=>{
    const realIndex = state.concepts.indexOf(c);

    const card = document.createElement("div");
    card.className="card";

    const head = document.createElement("div");
    head.className="cardhead";

    const left = document.createElement("div");
    left.className="left";
    left.innerHTML = `<div class="label">Concept name</div>`;
    const nameInput = document.createElement("input");
    nameInput.className="input";
    nameInput.value = c.concept || "";
    nameInput.addEventListener("input",(e)=>{
      state.concepts[realIndex].concept = e.target.value;
      setDirty(true);
      apiValidate();
    });
    nameInput.addEventListener("blur", ()=>{ render(); });
    left.appendChild(nameInput);

    const right = document.createElement("div");
    right.className="right";
    const addSeg = document.createElement("button");
    addSeg.className="mini primary";
    addSeg.textContent = "+ segment";
    addSeg.addEventListener("click", ()=>{
      state.concepts[realIndex].times.push({start:"00:00:00", end:"00:00:10"});
      setDirty(true); apiValidate(); render();
    });

    const del = document.createElement("button");
    del.className="mini danger";
    del.textContent="Delete concept";
    del.addEventListener("click", ()=>{
      if(!confirm(`Delete "${c.concept}"?`)) return;
      state.concepts.splice(realIndex,1);
      setDirty(true); apiValidate(); render();
    });

    right.appendChild(addSeg);
    right.appendChild(del);

    head.appendChild(left);
    head.appendChild(right);

    const times = document.createElement("div");
    times.className="times";

    (c.times||[]).forEach((seg, si)=>{
      const rowWrap = document.createElement("div");
      const row = document.createElement("div");
      row.className="timeRow";

      const start = document.createElement("input");
      start.className="input";
      start.value = seg.start || "";
      start.placeholder="Start (hh:mm:ss / mm:ss)";

      const end = document.createElement("input");
      end.className="input";
      end.value = seg.end || "";
      end.placeholder="End (hh:mm:ss / mm:ss)";

      const jump = document.createElement("button");
      jump.className="mini";
      jump.textContent="▶︎";
      jump.title="Hook: player.seek(start)";
      jump.addEventListener("click", ()=>{
        const p = parseTimeToSecs(start.value);
        if(!p.ok){ alert(p.err + (p.suggestion?("\\nSuggestion: "+p.suggestion):"")); return; }
        alert("Seek seconds: "+p.secs+" ("+p.norm+")");
      });

      const delSeg = document.createElement("button");
      delSeg.className="mini danger";
      delSeg.textContent="🗑";
      delSeg.addEventListener("click", ()=>{
        state.concepts[realIndex].times.splice(si,1);
        setDirty(true); apiValidate(); render();
      });

      const msg = document.createElement("div");
      msg.className="msg";

      function validateRow(){
        row.classList.remove("invalid");
        msg.classList.remove("show");
        msg.textContent="";

        const ps = parseTimeToSecs(start.value);
        if(!ps.ok){ row.classList.add("invalid"); msg.classList.add("show"); msg.textContent = ps.err + (ps.suggestion?(" • suggest: "+ps.suggestion):""); return false; }
        const pe = parseTimeToSecs(end.value);
        if(!pe.ok){ row.classList.add("invalid"); msg.classList.add("show"); msg.textContent = pe.err + (pe.suggestion?(" • suggest: "+pe.suggestion):""); return false; }
        if(ps.secs >= pe.secs){ row.classList.add("invalid"); msg.classList.add("show"); msg.textContent="Start must be < End"; return false; }
        return true;
      }

      function commit(){
        const ps = parseTimeToSecs(start.value);
        const pe = parseTimeToSecs(end.value);
        if(ps.ok) start.value = ps.norm;
        if(pe.ok) end.value = pe.norm;

        state.concepts[realIndex].times[si].start = start.value.trim();
        state.concepts[realIndex].times[si].end = end.value.trim();
        setDirty(true);
        apiValidate();
      }

      start.addEventListener("input", ()=>{ validateRow(); commit(); });
      end.addEventListener("input", ()=>{ validateRow(); commit(); });
      start.addEventListener("blur", ()=>{ validateRow(); commit(); render(); });
      end.addEventListener("blur", ()=>{ validateRow(); commit(); render(); });

      validateRow();

      row.appendChild(start);
      row.appendChild(end);
      row.appendChild(jump);
      row.appendChild(delSeg);

      rowWrap.appendChild(row);
      rowWrap.appendChild(msg);
      times.appendChild(rowWrap);
    });

    if(!c.times || c.times.length===0){
      const empty = document.createElement("div");
      empty.className="msg show";
      empty.style.color="var(--muted)";
      empty.textContent="No segments. Add one.";
      times.appendChild(empty);
    }

    card.appendChild(head);
    card.appendChild(times);
    cardsEl.appendChild(card);
  });
}


// ------------------
// Quiz UI
// ------------------
function ensureQuizCorrectness(q){
  // Keep correct as "true" only
  for(const a of q.answers){
    if(a.correct !== "true") delete a.correct;
  }
  // If no correct exists, force first answer to correct
  if(!q.answers.some(x=>x.correct==="true") && q.answers.length){
    q.answers[0].correct="true";
  }
}

function renderQuiz(){
  const list = filtered(state.questions, q=>q.question);
  countBadge.textContent = state.questions.length + " questions";
  cardsEl.innerHTML = "";

  list.forEach((q)=>{
    const realIndex = state.questions.indexOf(q);
    const card = document.createElement("div");
    card.className="card";

    const head = document.createElement("div");
    head.className="cardhead";

    const left = document.createElement("div");
    left.className="left";
    left.innerHTML = `<div class="label">Question</div>`;
    const qInput = document.createElement("input");
    qInput.className="input";
    qInput.value = q.question || "";
    qInput.addEventListener("input",(e)=>{
      state.questions[realIndex].question = e.target.value;
      setDirty(true); apiValidate();
    });
    left.appendChild(qInput);

    const right = document.createElement("div");
    right.className="right";

    // Toggle: allow multiple correct
    const toggleWrap = document.createElement("label");
    toggleWrap.className="small";
    toggleWrap.style.display="flex";
    toggleWrap.style.alignItems="center";
    toggleWrap.style.gap="6px";
    toggleWrap.style.border="1px solid rgba(46,107,207,.18)";
    toggleWrap.style.padding="6px 10px";
    toggleWrap.style.borderRadius="10px";
    toggleWrap.style.cursor="pointer";

    const allowMulti = document.createElement("input");
    allowMulti.type="checkbox";
    allowMulti.checked = !!q.allow_multiple_correct;
    allowMulti.addEventListener("change", ()=>{
      state.questions[realIndex].allow_multiple_correct = allowMulti.checked;
      // If turning OFF, keep only the first correct
      if(!allowMulti.checked){
        const idx = state.questions[realIndex].answers.findIndex(a=>a.correct==="true");
        for(const a of state.questions[realIndex].answers) delete a.correct;
        if(idx >= 0) state.questions[realIndex].answers[idx].correct="true";
        else if(state.questions[realIndex].answers.length) state.questions[realIndex].answers[0].correct="true";
      }
      ensureQuizCorrectness(state.questions[realIndex]);
      setDirty(true); apiValidate(); render();
    });

    const toggleTxt = document.createElement("span");
    toggleTxt.textContent = "Allow multiple correct";

    toggleWrap.appendChild(allowMulti);
    toggleWrap.appendChild(toggleTxt);

    const addAns = document.createElement("button");
    addAns.className="mini primary";
    addAns.textContent="+ answer";
    addAns.addEventListener("click", ()=>{
      state.questions[realIndex].answers.push({choice:"New answer"});
      ensureQuizCorrectness(state.questions[realIndex]);
      setDirty(true); apiValidate(); render();
    });

    const delQ = document.createElement("button");
    delQ.className="mini danger";
    delQ.textContent="Delete";
    delQ.addEventListener("click", ()=>{
      if(!confirm("Delete question?")) return;
      state.questions.splice(realIndex,1);
      setDirty(true); apiValidate(); render();
    });

    right.appendChild(toggleWrap);
    right.appendChild(addAns);
    right.appendChild(delQ);

    head.appendChild(left);
    head.appendChild(right);

    const answers = document.createElement("div");
    answers.className="qAnswers";

    const multi = !!q.allow_multiple_correct;
    const inputType = multi ? "checkbox" : "radio";

    (q.answers||[]).forEach((a, ai)=>{
      const rowWrap = document.createElement("div");
      const row = document.createElement("div");
      row.className="ansRow" + (a.correct==="true" ? " correct" : "");

      const mark = document.createElement("input");
      mark.type = inputType;
      mark.name = "q-"+realIndex+"-correct";
      mark.checked = a.correct==="true";

      mark.addEventListener("change", ()=>{
        if(!multi){
          for(const x of state.questions[realIndex].answers) delete x.correct;
          state.questions[realIndex].answers[ai].correct="true";
        }else{
          if(mark.checked) state.questions[realIndex].answers[ai].correct="true";
          else delete state.questions[realIndex].answers[ai].correct;
          ensureQuizCorrectness(state.questions[realIndex]);
        }
        setDirty(true); apiValidate(); render();
      });

      const aInput = document.createElement("input");
      aInput.className="input";
      aInput.value = a.choice || "";
      aInput.addEventListener("input",(e)=>{
        state.questions[realIndex].answers[ai].choice = e.target.value;
        setDirty(true); apiValidate();
      });

      const delA = document.createElement("button");
      delA.className="mini danger";
      delA.textContent="🗑";
      delA.addEventListener("click", ()=>{
        if(state.questions[realIndex].answers.length<=2){
          alert("Need at least 2 answers.");
          return;
        }
        const wasCorrect = state.questions[realIndex].answers[ai].correct==="true";
        state.questions[realIndex].answers.splice(ai,1);
        if(wasCorrect) ensureQuizCorrectness(state.questions[realIndex]);
        setDirty(true); apiValidate(); render();
      });

      const msg = document.createElement("div");
      msg.className="msg";
      function validateRow(){
        row.classList.remove("invalid");
        msg.classList.remove("show");
        msg.textContent="";
        const txt = (aInput.value||"").trim();
        if(!txt){
          row.classList.add("invalid");
          msg.classList.add("show");
          msg.textContent="Empty answer text";
          return false;
        }
        return true;
      }
      aInput.addEventListener("blur", ()=>{
        state.questions[realIndex].answers[ai].choice = (aInput.value||"").trim();
        setDirty(true); apiValidate(); validateRow(); render();
      });
      validateRow();

      row.appendChild(mark);
      row.appendChild(aInput);
      row.appendChild(delA);
      rowWrap.appendChild(row);
      rowWrap.appendChild(msg);
      answers.appendChild(rowWrap);
    });

    const footer = document.createElement("div");
    footer.className="small";
    footer.style.marginTop="10px";
    footer.textContent = multi
      ? "Multi-correct enabled: you can mark several answers."
      : "Single-correct mode: exactly one answer must be correct.";

    card.appendChild(head);
    card.appendChild(answers);
    card.appendChild(footer);
    cardsEl.appendChild(card);
  });
}


// ------------------
// Render router
// ------------------
function render(){
  if(!state) return;
  if(docType==="concepts") renderConcepts();
  else renderQuiz();
}


// ------------------
// UI Events
// ------------------
docTypeEl.addEventListener("change", async ()=>{
  const newType = docTypeEl.value;
  if(dirty && !confirm("Switch type and discard current unsaved changes?")) {
    docTypeEl.value = docType;
    return;
  }
  await apiSetType(newType);
});

saveTarget.addEventListener("input", ()=>{
  saveTargetHint.textContent = "Full path: ./saved/" + (saveTarget.value||"");
});

searchEl.addEventListener("input", render);

addBtn.addEventListener("click", ()=>{
  if(docType==="concepts"){
    state.concepts.push({concept:"New concept", times:[{start:"00:00:00", end:"00:00:10"}]});
  } else {
    state.questions.push({
      question:"New question",
      allow_multiple_correct:false,
      answers:[
        {choice:"Answer A", correct:"true"},
        {choice:"Answer B"},
        {choice:"Answer C"},
        {choice:"Answer D"}
      ]
    });
  }
  setDirty(true); apiValidate(); render();
  window.scrollTo({top: document.body.scrollHeight, behavior:"smooth"});
});

reloadBtn.addEventListener("click", async ()=>{
  if(dirty && !confirm("Discard unsaved changes and reload last saved?")) return;
  await apiGetState();
});

saveBtn.addEventListener("click", async ()=>{
  await apiValidate();
  if(issues.length){ alert("Fix validation issues before saving."); return; }
  await apiSave("overwrite", null);
});

saveAsBtn.addEventListener("click", ()=>{
  saveAsPath.value = saveTarget.value || "untitled.json";
  openModal(saveModal);
  saveAsPath.focus();
});

confirmSaveAs.addEventListener("click", async ()=>{
  const p = (saveAsPath.value||"").trim();
  if(!p){ alert("Provide a filename"); return; }
  await apiValidate();
  if(issues.length){ alert("Fix validation issues before Save As."); return; }
  const ok = await apiSave("save_as", p);
  if(ok) closeModal(saveModal);
});

// Paste JSON
pasteBtn.addEventListener("click", ()=>{
  pasteArea.value = "";
  openModal(pasteModal);
  pasteArea.focus();
});
applyPaste.addEventListener("click", ()=>{
  try{
    const obj = JSON.parse(pasteArea.value);
    apiLoadJson(obj, "pasted.json");
    closeModal(pasteModal);
  }catch(e){
    alert("Invalid JSON: " + e.message);
  }
});

// Upload JSON
uploadBtn.addEventListener("click", ()=> fileInput.click());
fileInput.addEventListener("change", async (e)=>{
  const f = e.target.files && e.target.files[0];
  if(!f) return;
  try{
    const txt = await f.text();
    const obj = JSON.parse(txt);
    await apiLoadJson(obj, f.name);
  }catch(err){
    alert("Upload failed: " + err.message);
  }finally{
    fileInput.value = "";
  }
});

// Boot
apiGetState();
</script>
</body>
</html>
"""


# -----------------------------
# API + Server
# -----------------------------

def normalize_by_type(doc_type: str, data: dict) -> dict:
    if doc_type == "concepts":
        return normalize_concepts(data)
    if doc_type == "quiz":
        return normalize_quiz(data)
    raise ValueError("Unknown doc_type")

def validate_by_type(doc_type: str, data: dict) -> list[dict]:
    if doc_type == "concepts":
        return validate_concepts(data)
    if doc_type == "quiz":
        return validate_quiz(data)
    raise ValueError("Unknown doc_type")

def empty_doc(doc_type: str) -> dict:
    return {"concepts": []} if doc_type == "concepts" else {"questions": []}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            return text_response(self, INDEX_HTML)

        if parsed.path == "/api/state":
            return json_response(self, {
                "ok": True,
                "doc_type": STATE["doc_type"],
                "filename": STATE["filename"],
                "save_rel_path": STATE["save_rel_path"],
                "data": STATE["data"],
            })

        return json_response(self, {"ok": False, "error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = parse_json_body(self)
        except Exception as e:
            return json_response(self, {"ok": False, "error": f"Invalid JSON body: {e}"}, 400)

        if parsed.path == "/api/set_type":
            try:
                dt = body.get("doc_type")
                if dt not in ("concepts", "quiz"):
                    raise ValueError("doc_type must be 'concepts' or 'quiz'")
                STATE["doc_type"] = dt
                STATE["filename"] = "untitled.json"
                STATE["save_rel_path"] = "untitled.json"
                STATE["data"] = empty_doc(dt)
                return json_response(self, {"ok": True, "doc_type": dt, "data": STATE["data"]})
            except Exception as e:
                return json_response(self, {"ok": False, "error": str(e)}, 400)

        if parsed.path == "/api/load_json":
            try:
                dt = body.get("doc_type")
                if dt not in ("concepts", "quiz"):
                    raise ValueError("doc_type must be 'concepts' or 'quiz'")
                data = body.get("data")
                if not isinstance(data, dict):
                    raise ValueError("data must be an object")
                filename = str(body.get("filename") or "untitled.json")
                # Normalize to chosen type
                normalized = normalize_by_type(dt, data)

                STATE["doc_type"] = dt
                STATE["filename"] = filename
                # default save target: same name, but under ./saved/
                STATE["save_rel_path"] = filename if filename.endswith(".json") else (filename + ".json")
                STATE["data"] = normalized

                return json_response(self, {"ok": True, "data": normalized, "save_rel_path": STATE["save_rel_path"]})
            except Exception as e:
                return json_response(self, {"ok": False, "error": str(e)}, 400)

        if parsed.path == "/api/validate":
            try:
                dt = body.get("doc_type")
                data = body.get("data")
                if dt not in ("concepts", "quiz"):
                    raise ValueError("doc_type must be 'concepts' or 'quiz'")
                if not isinstance(data, dict):
                    raise ValueError("data must be an object")
                issues = validate_by_type(dt, data)
                return json_response(self, {"ok": True, "issues": issues})
            except Exception as e:
                return json_response(self, {"ok": False, "error": str(e)}, 400)

        if parsed.path == "/api/save":
            try:
                dt = body.get("doc_type")
                data = body.get("data")
                rel_path = body.get("save_rel_path")
                if dt not in ("concepts", "quiz"):
                    raise ValueError("doc_type must be 'concepts' or 'quiz'")
                if not isinstance(data, dict):
                    raise ValueError("data must be an object")
                rel_path = str(rel_path or "untitled.json").strip()
                if not rel_path.endswith(".json"):
                    rel_path += ".json"

                normalized = normalize_by_type(dt, data)
                issues = validate_by_type(dt, normalized)
                if issues:
                    return json_response(self, {"ok": False, "error": f"Validation failed ({len(issues)} issues).", "issues": issues}, 400)

                out_path = safe_join_saved(rel_path)
                write_text_atomic(out_path, json.dumps(normalized, ensure_ascii=False, indent=2))

                # persist state as "last saved"
                STATE["doc_type"] = dt
                STATE["data"] = normalized
                STATE["save_rel_path"] = rel_path

                return json_response(self, {
                    "ok": True,
                    "save_rel_path": rel_path,
                    "message": f"Saved to ./saved/{rel_path}"
                })
            except Exception as e:
                return json_response(self, {"ok": False, "error": str(e)}, 400)

        return json_response(self, {"ok": False, "error": "Not found"}, 404)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"✅ Editor running: http://{HOST}:{PORT}")
    print(f"   Save folder: {SAVED_DIR}")
    print("   Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
