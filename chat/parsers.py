import os 
import json
from datetime import timedelta
import pdfplumber
from collections import defaultdict



def chunk_transcript(segments, chunk_size_sec=30):
    chunks = defaultdict(list)

    for s in segments:
        start_sec = time_to_seconds(s["start"])
        chunk_idx = int(start_sec // chunk_size_sec)
        chunks[chunk_idx].append(s)

    combined_chunks = []
    for chunk_idx in sorted(chunks.keys()):
        lines = chunks[chunk_idx]
        text = " ".join([l["text"] for l in lines])
        start = lines[0]["start"]
        end = lines[-1]["end"]
        combined_chunks.append({
            "text": text.strip(),
            "start": start,
            "end": end
        })

    return combined_chunks

def load_transcript(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    segments = []
    for line in data["lines"]:
        text = line["text"].strip()
        if text:
            segments.append({
                "text": text,
                "start": line["start"],
                "end": line["end"]
            })
    return segments
def parse_transcript_in_chunks(file_path,  chunk_size_sec=30):
    segments = load_transcript(file_path)
    chunks = chunk_transcript(segments,chunk_size_sec)
    return chunks
def parse_pdf_slides(path):
    slides = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                slides.append({
                    "slide": i + 1,
                    "text": text.strip(),
                    "source": "slides"
                })
    return slides
def time_to_seconds(tstr):
    h, m, s = tstr.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)

def load_summary(path, label):
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    return [{
        "text": text,
        "source": "summary",
        "reference": label
    }]
def parse_all(
    transcript_path,
    slide_path,
    short_summary_path,
    long_summary_path,
    concepts_path,
    quiz_path,
    course_id="marketing",
    lesson_id=None
):
    segments = []

    if transcript_path:
        raw_segments = load_transcript(transcript_path)
        transcript_chunks = chunk_transcript(raw_segments, chunk_size_sec=30)
        transcript_chunks = [
            {
                "text": s["text"],  # Actual transcript content
                "reference": f"video {lesson_id} ({s['start']} - {s['end']})",
                "source": "transcript",
                "start": s["start"],
                "end": s["end"]
            }
            for s in transcript_chunks
        ]

        segments += transcript_chunks

    if slide_path:
        slide_segments = parse_pdf_slides(slide_path)
        slide_segments = [
            {
                "text": s["text"],
                "reference": f"slide {lesson_id}-{s['slide']}",
                "source": "slides",
                "slide": s["slide"]
            }
            for s in slide_segments
        ]

        segments += slide_segments

    if quiz_path:
        quiz = load_quiz(quiz_path)
        quiz_segments = [
            {
                "text": q["text"],
                "reference": f"quiz {lesson_id}-{i + 1}",
                "source": "quiz"
            }
            for i, q in enumerate(quiz)
        ]
        segments += quiz_segments


    if short_summary_path:
        summary_segments = load_summary(short_summary_path, f"summary {course_id} (short)")
        summary_segments = [
            {
                "text": s["text"],
                "reference": s["reference"],
                "source": "short_summary"
            }
            for s in summary_segments
        ]
        segments+=summary_segments

    if long_summary_path:
        summary_segments = load_summary(long_summary_path, f"summary {course_id} (long)")
        summary_segments = [
            {
                "text": s["text"],
                "reference": s["reference"],
                "source": "long_summary"
            }
            for s in summary_segments
        ]
        segments += summary_segments

    if concepts_path:
        #concept_segments = load_concepts_with_text(concepts_path, transcript_chunks, course_id)
        #segments += concept_segments
        concepts = load_concepts(concepts_path)
        concept_segments = [
            {
                "text": c["text"],
                "reference": f"concept {course_id} - {c['reference']}",
                "source": "concept"
            }
            for c in concepts
        ]

        segments += concept_segments

    return segments
def load_concepts_with_text(concepts_path, transcript_segments, course_id):
    with open(concepts_path, encoding="utf-8") as f:
        data = json.load(f)

    def to_sec(t): return sum(float(x) * 60 ** i for i, x in enumerate(reversed(t.split(":"))))

    segments = []
    for item in data["concepts"]:
        concept = item["concept"]
        for t in item["times"]:
            start_sec = to_sec(t["start"])
            end_sec = to_sec(t["end"])
            # Find matching transcript segments
            matched = [
                s["text"]
                for s in transcript_segments
                if "start" in s and "end" in s and
                   to_sec(s["start"]) >= start_sec and to_sec(s["end"]) <= end_sec
            ]
            full_text = " ".join(matched).strip()
            if full_text:
                segments.append({
                    "text": full_text,
                    "source": "concept",
                    "reference": f"concept {course_id} - {concept} [{t['start']}–{t['end']}]"
                })
    return segments


def load_quiz(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    segments = []
    for i, q in enumerate(data["questions"]):
        q_text = q["question"]
        correct = [a["choice"] for a in q["answers"] if a.get("correct")]
        full_text = f"{q_text} — Correct answer(s): {', '.join(correct)}"
        segments.append({
            "text": full_text,
            "source": "quiz",
            "reference": f"question {i + 1}"
        })
    return segments


def load_concepts(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    segments = []
    for item in data["concepts"]:
        concept = item["concept"]
        for t in item["times"]:
            segments.append({
                "text": f"Concept: {concept}",
                "source": "concept",
                "reference": f"{concept} [{t['start']}–{t['end']}]"
            })
    return segments


if __name__ == "__main__":
    d_path = "/home/roy/FS/OneDrive/WORK/ideas/aaron/רייכמן/marketing/semesterA/arifacts/"
    file_path = os.path.join(d_path, "transcript.json")
    #segments = load_transcript(file_path)
    results= parse_transcript_in_chunks(file_path)
    print (results[0:3])

    # file_path = os.path.join(d_path, "שיעור מספר 4 מסע הלקוח.pdf")
    # slide_segments = parse_pdf_slides(file_path)
    # print(slide_segments[0:3])  # show first one
