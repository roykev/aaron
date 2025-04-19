import os
import pandas as pd
import csv
import base64
from io import BytesIO
from datetime import datetime
import matplotlib.pyplot as plt
import pdfkit
import json

def time_to_seconds(t):
    h, m, s = map(int, t.split(':')) if t.count(':') == 2 else (0, *map(int, t.split(':')))
    return h * 3600 + m * 60 + s

def is_hebrew(text):
    return any('֐' <= c <= 'ת' for c in text)

def load_csv_safe(path, expected_cols=None, has_headers=True):
    try:
        try:
            df = pd.read_csv(path, header=0 if has_headers else None, quotechar='"', quoting=csv.QUOTE_MINIMAL, skipinitialspace=True)
        except pd.errors.ParserError:
            df = pd.read_csv(path, header=0 if has_headers else None, quotechar='"', quoting=csv.QUOTE_MINIMAL, engine='python')
        if not has_headers and expected_cols:
            df.columns = expected_cols
        return df
    except Exception as e:
        with open(path, 'r', encoding='utf-8') as f:
            sample = f.read().splitlines()[:3]
        raise ValueError(f"Error reading {os.path.basename(path)}: {e}\nSample lines:\n" + "\n".join(sample))

def load_open_questions_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            simple = data.get("simple_questions", [])
            difficult = data.get("difficult_questions", [])
            return {
                "simple": simple,
                "difficult": difficult
            }
    except Exception as e:
        raise ValueError(f"Error reading open_questions.json: {e}")
    except Exception as e:
        raise ValueError(f"Error reading open_questions.json: {e}")

def render_title(artifact_dir):
    path = os.path.join(artifact_dir, "title.csv")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                raw = f.read().replace("'", '"').replace(", }", "}")
                return json.loads(raw.strip())["title"]
        except Exception as e:
            raise ValueError(f"Error parsing title.csv: {e}")
    return "Unknown Title"

def render_summary(artifact_dir):
    path = os.path.join(artifact_dir, "short.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
            align = "right" if is_hebrew(text) else "left"
            return f'<p style="text-align: {align};">' + "<br>".join(line.strip() for line in text.strip().split("\n")) + "</p>"
    return "<em>No summary available</em>"

def render_sections(artifact_dir):
    path = os.path.join(artifact_dir, "sections.csv")
    if not os.path.exists(path): return "", ""
    try:
        df = load_csv_safe(path, ['Section #', 'Start', 'End', 'Title', 'Duration'], has_headers=False)
        df['Start_sec'] = df['Start'].apply(time_to_seconds)
        df['End_sec'] = df['End'].apply(time_to_seconds)
        df['Duration_sec'] = df['End_sec'] - df['Start_sec']
        rows = "".join(
            f"<tr><td>{int(r['Section #'])}</td><td>{r['Start']}</td><td>{r['End']}</td><td>{r['Title']}</td><td>{r['Duration_sec']}</td></tr>"
            for _, r in df.iterrows())
        html = f"""
            <h2>⏱️ Class Sections Breakdown</h2>
            <table><tr><th>#</th><th>Start</th><th>End</th><th>Title</th><th>Duration (sec)</th></tr>{rows}</table>
        """
        fig, ax = plt.subplots(figsize=(8, 6))
        labels = [f"{int(r['Section #'])}. {r['Title']}" for _, r in df.iterrows()]
        ax.pie(df['Duration_sec'], labels=labels, autopct='%1.1f%%', startangle=140)
        ax.set_title("Class Time Distribution by Section")
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight')
        chart_img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        buf.close()
        return html, chart_img_base64
    except Exception as e:
        raise ValueError(f"Error processing sections.csv: {e}")

def render_interactions(artifact_dir):
    print("--- DEBUG: loading interactions ---")
    path = os.path.join(artifact_dir, "interaction.csv")
    if not os.path.exists(path): return ""
    try:
        df = load_csv_safe(path, has_headers=True)
        expected_cols = ['Time', 'Type', 'Description']
        print(df.head())
        df = df.astype(str).fillna('').copy()
        df = df[df[expected_cols].apply(lambda row: all(cell.strip() for cell in row), axis=1)]
        rows = "".join(
            f"<tr class='interaction-{(r.get('Type', '') or 'unknown').split()[0].lower()}'>"
            f"<td>{r.get('Time', '')}</td><td>{r.get('Type', '')}</td><td>{r.get('Description', '')}</td></tr>"
            for _, r in df.iterrows())
        if rows:
            alignment = "right" if any(is_hebrew(r.get('Description', '')) for _, r in df.iterrows()) else "left"
            return f"""
                <h2>💬 Class Interactions</h2>
                <table style='text-align: {alignment};'><tr><th>Time</th><th>Type</th><th>Description</th></tr>{rows}</table>
            """
    except Exception as e:
        raise ValueError(f"Error processing interaction.csv: {e}")
    return ""

def render_difficult_topics(artifact_dir):
    path = os.path.join(artifact_dir, "difficult_topics.csv")
    if not os.path.exists(path): return ""
    try:
        df = load_csv_safe(path, has_headers=True)
        required_cols = ['Topic', 'Reason for difficulty', 'Recommendation for improvement']
        if not all(col in df.columns for col in required_cols):
            return ""
        rows = "".join(
            f"<tr><td><strong>{r['Topic']}</strong></td><td>{r['Reason for difficulty']}</td><td>{r['Recommendation for improvement']}</td></tr>"
            for _, r in df.iterrows())
        alignment = "right" if any(is_hebrew(str(x)) for x in df['Topic']) else "left"
        return f"""
            <h2>❗ Difficult Topics</h2>
            <table style='text-align: {alignment};'><tr><th>Topic</th><th>Reason</th><th>Recommendation</th></tr>{rows}</table>
        """
    except Exception as e:
        raise ValueError(f"Error processing difficult_topics.csv: {e}")

def render_open_questions(artifact_dir):
    csv_path = os.path.join(artifact_dir, "open_questions.csv")
    json_path = os.path.join(artifact_dir, "open_questions.json")
    try:
        if os.path.exists(csv_path):
            df = load_csv_safe(csv_path, ['Question', 'Comment'], has_headers=True)
            rows = "".join(f"<tr><td>{r['Question']}</td><td>{r['Comment']}</td></tr>" for _, r in df.iterrows())
            alignment = "right" if any(is_hebrew(str(x)) for x in df['Question']) else "left"
            return f"""
                <h2>❓ Open Questions</h2>
                <table style='text-align: {alignment};'><tr><th>Question</th><th>Comment</th></tr>{rows}</table>
            """
        elif os.path.exists(json_path):
            questions = load_open_questions_json(json_path)
            alignment = "right" if any(is_hebrew(q) for q in questions['simple'] + questions['difficult']) else "left"
            simple_rows = "".join(f"<li>{q}</li>" for q in questions['simple'])
            difficult_rows = "".join(f"<li>{q}</li>" for q in questions['difficult'])
            return f"""
                <h2>❓ Open Questions</h2>
                <h3>Simple Questions</h3>
                <ul style='text-align: {alignment};'>{simple_rows}</ul>
                <h3>Difficult Questions</h3>
                <ul style='text-align: {alignment};'>{difficult_rows}</ul>
            """
    except Exception as e:
        raise ValueError(f"Error processing open_questions data: {e}")
    return ""

def generate_teacher_report_html(artifact_dir, class_date_str):
    class_date = datetime.strptime(class_date_str, "%d/%m/%Y").strftime("%B %d, %Y")
    title = render_title(artifact_dir)
    summary_html = render_summary(artifact_dir)
    sections_html, chart_img_base64 = render_sections(artifact_dir)
    interaction_html = render_interactions(artifact_dir)
    difficult_html = render_difficult_topics(artifact_dir)
    open_questions_html = render_open_questions(artifact_dir)

    html = f"""
    <!DOCTYPE html>
    <html lang=\"en\">
    <head>
        <meta charset=\"UTF-8\">
        <title>Teacher Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1, h2, h3 {{ color: #2c3e50; }}
            .section {{ margin-bottom: 30px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .class-title {{ font-size: 20px; font-weight: bold; }}
            .interaction-discussion td {{ background-color: #e6f7ff; }}
            .interaction-student td {{ background-color: #fff9e6; }}
            .interaction-teacher td {{ background-color: #ffe6f0; }}
            img {{ max-width: 100%; height: auto; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h1 style=\"font-size: 32px; color: #0d47a1;\">Teacher Report</h1>
        <div class=\"section\">
            <p class=\"class-title\" style=\"font-size: 22px; color: #1a237e;\">📘 Class Title: {title}</p>
            <p style=\"font-size: 16px;\">📅 <strong>Date:</strong> {class_date}</p>
        </div>
        <div class=\"section\">
            <h2>📝 Class Summary</h2>
            {summary_html}
        </div>
        <div class=\"section\">
            {sections_html}
            {'<img src="data:image/png;base64,' + chart_img_base64 + '">' if chart_img_base64 else ''}
        </div>
        <div class=\"section\">{interaction_html}</div>
        <div class=\"section\">{difficult_html}</div>
        <div class=\"section\">{open_questions_html}</div>
    </body>
    </html>
    """
    return html

def export_report_to_pdf(html_string, output_pdf_path):
    pdfkit.from_string(html_string, output_pdf_path)  # requires wkhtmltopdf installed




if __name__ == '__main__':
    dir_name="/home/roy/FS/OneDrive/WORK/ideas/aaron/hadasa/maoz/demo/"
    dir_name="/home/roy/FS/OneDrive/WORK/ideas/aaron/hadasa/keren"
    h_report = generate_teacher_report_html(dir_name, "25/03/2025")
    pdf_name = os.path.join(dir_name,"teacher_report.pdf")
    export_report_to_pdf(h_report,pdf_name)