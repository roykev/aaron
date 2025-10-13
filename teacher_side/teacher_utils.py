import os.path
import time
import yaml
from utils.utils import get_logger
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib
import pandas as pd

from pathlib import Path
import re, json, csv, io, shutil, html
# ---- Color maps for font colors ----
INTERACTION_COLORS = {
    "student question": "darkorange",
    "discussion": "darkblue",
    "_default": "black"
}
EXAMPLES_COLORS = {
    "class": "green",
    "external": "purple",
    "_default": "black"
}

def read_blocks(text: str):
    """Split file into named blocks by lines like: ### name ###"""
    blocks = {}
    current = None
    buf = []
    for line in text.splitlines():
        m = re.match(r"^###\s*([A-Za-z_]+)\s*###\s*$", line.strip())
        if m:
            if current is not None:
                blocks[current] = "\n".join(buf).strip()
                buf = []
            current = m.group(1).lower()
        else:
            buf.append(line)
    if current is not None:
        blocks[current] = "\n".join(buf).strip()
    return blocks

def parse_csv_block(block: str):
    """Parse a CSV-like block with quotes/commas."""
    rows = []
    reader = csv.reader(io.StringIO(block), skipinitialspace=True)
    for row in reader:
        if not row:
            continue
        rows.append([c.strip() for c in row])
    return rows

def make_sections_md(rows, svg_data=None):
    """
    Generate markdown for sections with optional embedded SVG.

    Args:
        rows: List of rows with section data [id, start, end, title, duration]
        svg_data: Optional SVG string to embed directly in markdown

    Returns:
        Markdown string with sections and embedded visualization
    """
    out = ["## 📚 Sections"]

    for r in rows:
        _, start, end, title, duration = (r + [""]*5)[:5]
        title = title.strip().strip('"')
        out.append(f'1. **{start} – {end}** — *{title}* ({duration})')

    # Embed SVG directly in markdown if provided
    if svg_data:
        out.append('\n<details open>')
        out.append('<summary>Class Timeline Visualization</summary>\n')
        out.append(svg_data)
        out.append('</details>\n')

    return "\n".join(out)

def make_colored_table_html(headers, rows, key_col, palette):
    idx = {h.lower(): i for i, h in enumerate(headers)}
    if key_col.lower() not in idx:
        return make_plain_table_html(headers, rows)

    key_i = idx[key_col.lower()]
    parts = []
    parts.append('<table style="border-collapse:collapse;width:100%;">')
    parts.append("<thead><tr>")
    for h in headers:
        parts.append(f'<th style="border-bottom:1px solid #ccc;text-align:left;padding:6px 8px;">{html.escape(h)}</th>')
    parts.append("</tr></thead>")
    parts.append("<tbody>")
    for r in rows:
        r = (r + [""]*len(headers))[:len(headers)]
        key_val = (r[key_i] or "").strip().lower()
        color = palette.get(key_val, palette.get("_default", "black"))
        parts.append("<tr>")
        for c in r:
            parts.append(f'<td style="padding:6px 8px;vertical-align:top;border-bottom:1px solid #eee;color:{color};">{html.escape(c)}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def make_plain_table_html(headers, rows):
    parts = []
    parts.append('<table style="border-collapse:collapse;width:100%;">')
    parts.append("<thead><tr>")
    for h in headers:
        parts.append(f'<th style="border-bottom:1px solid #ccc;text-align:left;padding:6px 8px;">{html.escape(h)}</th>')
    parts.append("</tr></thead>")
    parts.append("<tbody>")
    for r in rows:
        r = (r + [""]*len(headers))[:len(headers)]
        parts.append("<tr>")
        for c in r:
            parts.append(f'<td style="padding:6px 8px;vertical-align:top;border-bottom:1px solid #eee;">{html.escape(c)}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)

def plot_class_schedule_numbered(df: pd.DataFrame, format: str = "svg") -> str:
    """
    Generate a class schedule visualization.

    Args:
        df: DataFrame with class schedule data
        format: Output format - "svg" returns SVG string, "png" returns base64 PNG

    Returns:
        String containing SVG markup or base64-encoded PNG data
    """
    import base64

    # ---- helpers ----
    def hhmmss_to_minutes(t: str) -> float:
        h, m, s = map(int, str(t).strip().split(":"))
        return h*60 + m + s/60
    def hhmmss_to_seconds(t: str) -> int:
        h, m, s = map(int, str(t).strip().split(":"))
        return h*3600 + m*60 + s

    # ---- normalize input ----
    if list(df.columns) == list(range(df.shape[1])) or df.columns[0] == 0:
        df.columns = ["ID","Start","End","Section","Duration"]
    if "Duration (sec)" not in df.columns:
        if "Duration" in df.columns:
            df["Duration (sec)"] = df["Duration"].apply(hhmmss_to_seconds)
        else:
            df["Duration (sec)"] = (
                df["End"].apply(hhmmss_to_seconds) - df["Start"].apply(hhmmss_to_seconds)
            )
    df["Start_min"] = df["Start"].apply(hhmmss_to_minutes)
    df["End_min"]   = df["End"].apply(hhmmss_to_minutes)

    # labels & colors
    n = len(df)
    idx_labels = [str(i+1) for i in range(n)]
    y_labels   = [f"{i+1}. {title}" for i, title in enumerate(df["Section"])]
    cmap = matplotlib.colormaps.get_cmap("tab20")
    colors = [cmap(i) for i in range(n)]

    # ---- figure: [labels] [gantt] [pie] ----
    fig = plt.figure(figsize=(14, 6), dpi=150)
    # make the labels column wider so long titles fit
    gs  = gridspec.GridSpec(1, 3, width_ratios=[1.6, 2.1, 1.0], wspace=0.25)

    # Left labels axis (outside column)
    axL = fig.add_subplot(gs[0])
    axL.set_xlim(0, 1)
    axL.set_ylim(-0.5, n-0.5)
    axL.invert_yaxis()
    axL.axis("off")

    # Gantt axis
    ax0 = fig.add_subplot(gs[1], sharey=axL)
    for i, row in df.iterrows():
        ax0.barh(
            y=i,
            width=row["End_min"] - row["Start_min"],
            left=row["Start_min"],
            height=0.55,
            color=colors[i],
            edgecolor="none",
            zorder=1,
        )
    ax0.set_yticks([])  # labels are in axL
    for s in ax0.spines.values():
        s.set_visible(False)
    ax0.set_xlabel("Time (minutes)")
    ax0.set_title("Class Time Breakdown (Timeline)")
    ax0.grid(axis="x", linestyle="--", alpha=0.3, zorder=0)

    # >>> draw labels AFTER bars, left-aligned, not clipped <<<
    for y, text in enumerate(y_labels):
        axL.text(0.0, y, text, ha="left", va="center", fontsize=10,
                 clip_on=False, zorder=10)

    # Pie (numbers only)
    ax1 = fig.add_subplot(gs[2])
    ax1.pie(
        df["Duration (sec)"],
        labels=idx_labels,
        autopct="%1.1f%%",
        startangle=140,
        colors=colors,
        labeldistance=1.05,
        pctdistance=0.75,
        wedgeprops={"linewidth": 0.6, "edgecolor": "black"},
        textprops={"fontsize": 9},
    )
    ax1.set_title("Proportion of Time")

    # Save to memory buffer instead of file
    buf = io.BytesIO()
    if format.lower() == "svg":
        fig.savefig(buf, format="svg", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue().decode("utf-8")
    else:  # png or other formats
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        buf.seek(0)
        # Return base64-encoded PNG
        return base64.b64encode(buf.read()).decode("utf-8")


def make_font_color_legend(title_text: str, mapping: dict) -> str:
    # mapping: {"class": "green", "external": "purple"} etc.
    parts = [f'<p style="margin-top:6px;"><em>{html.escape(title_text)}: ']
    items = []
    for label, color in mapping.items():
        if label == "_default":
            continue
        items.append(f'<span style="color:{color};font-weight:600;">{html.escape(label)}</span>')
    parts.append(" | ".join(items))
    parts.append("</em></p>")
    return "".join(parts)



def generate_report(dir_path):
    INPUT_TXT = Path(os.path.join(dir_path,"output.txt"))
    OUTPUT_MD =Path(os.path.join(dir_path,"output.md"))
    text = INPUT_TXT.read_text(encoding="utf-8")
    blocks = read_blocks(text)

    # Title
    title_json = json.loads(blocks["title"])
    md = [f'# {title_json.get("title", "Untitled")}', ""]

    # Sections - generate SVG inline instead of PNG file
    sections_rows = parse_csv_block(blocks["sections"])

    # Create DataFrame from sections for visualization
    df_sections = pd.DataFrame(sections_rows[1:], columns=["ID", "Start", "End", "Section", "Duration"])

    # Generate SVG data (not file)
    svg_data = plot_class_schedule_numbered(df_sections, format="svg")

    md.append(make_sections_md(sections_rows[1:], svg_data=svg_data))
    md.append("\n---\n")

    # Examples (colored by Reference)
    examples_rows = parse_csv_block(blocks["examples"])
    if examples_rows:
        headers = [h.strip() for h in examples_rows[0]]
        data = examples_rows[1:]
        md.append("## 💡 Examples")
        md.append(make_colored_table_html(headers, data, key_col="Reference", palette=EXAMPLES_COLORS))
        # legend
        md.append(make_font_color_legend("Row color by Reference",
                                         {"class": EXAMPLES_COLORS["class"],
                                          "external": EXAMPLES_COLORS["external"]}))

        md.append("\n---\n")

    # Open questions
    oq = json.loads(blocks["open_questions"])
    md.append("## ❓ Open Questions\n")
    md.append("### Simple")
    for q in oq.get("simple", []):
        md.append(f"- {q}")
    md.append("\n### Difficult")
    for q in oq.get("difficult", []):
        md.append(f"- {q}")
    md.append("\n---\n")

    # Interaction (colored by Type)
    inter_rows = parse_csv_block(blocks["interaction"])
    if inter_rows:
        headers = [h.strip() for h in inter_rows[0]]
        data = inter_rows[1:]
        md.append("## 👩‍🎓 Class Interaction")
        md.append(make_colored_table_html(headers, data, key_col="Type", palette=INTERACTION_COLORS))
        # legend
        md.append(make_font_color_legend("Row color by Type",
                                         {"student question": INTERACTION_COLORS["student question"],
                                          "discussion": INTERACTION_COLORS["discussion"]}))

        md.append("\n---\n")

    # Difficult topics (plain table)
    diff_rows = parse_csv_block(blocks["difficult_topics"])
    if diff_rows:
        headers = [h.strip() for h in diff_rows[0]]
        data = diff_rows[1:]
        md.append("## ⚠️ Difficult Topics")
        md.append(make_plain_table_html(headers, data))
    OUTPUT_MD = Path(os.path.join(dir_path,"output.md"))
    OUTPUT_MD.write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    print(f"Markdown saved to: {OUTPUT_MD}")









if __name__ == "__main__":
    # Example usage with your table
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Process video
    t0 = time.time()
    sections_file=os.path.join(config["videos_dir"],"sections.csv")
    # Define expected headers
    # When reading your file:
    df_raw = pd.read_csv(sections_file, header=None)  # or header=0 if you know it has headers
#    df = normalize_schedule_df(df_raw)

   # df =read_sections_file(sections_file)

    generate_report(config["videos_dir"])
    logger.info(f'Pipeline completed in {time.time() - t0:.3f}s')
