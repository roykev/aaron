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
    """Split file into named blocks by lines like: ### name ### or ### Task: name ###"""
    blocks = {}
    current = None
    buf = []
    for line in text.splitlines():
        # Match patterns like "### name ###" or "### Task: name ###" or "### any text ###"
        m = re.match(r"^###\s*(?:Task:\s*)?(.+?)\s*###\s*$", line.strip())
        if m:
            if current is not None:
                blocks[current] = "\n".join(buf).strip()
                buf = []
            # Extract the task name and normalize it (lowercase, replace spaces/colons with underscores)
            current = re.sub(r'[:\s]+', '_', m.group(1).strip().lower())
        else:
            buf.append(line)
    if current is not None:
        blocks[current] = "\n".join(buf).strip()
    return blocks

def parse_csv_block(block: str):
    """Parse a CSV-like block with quotes/commas."""
    # Strip markdown code fences if present
    block = block.strip()
    if block.startswith("```csv"):
        block = block[6:]  # Remove ```csv
    elif block.startswith("```"):
        block = block[3:]  # Remove ```
    if block.endswith("```"):
        block = block[:-3]  # Remove ```

    block = block.strip()

    rows = []
    reader = csv.reader(io.StringIO(block), skipinitialspace=True)
    for row in reader:
        if not row:
            continue
        rows.append([c.strip() for c in row])
    return rows

def strip_markdown_json_fence(text: str) -> str:
    """
    Remove markdown code fences from JSON text.
    Handles formats like:
    ```json
    {...}
    ```
    or just
    ```
    {...}
    ```
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]  # Remove ```json
    if text.startswith("```"):
        text = text[3:]  # Remove ```
    if text.endswith("```"):
        text = text[:-3]  # Remove ```
    return text.strip()

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

def get_output_dir(config):
    """
    Get or create the output directory under videos_dir/output/

    Args:
        config: Configuration dictionary

    Returns:
        Path to output directory
    """
    output_dir = os.path.join(config["videos_dir"], "output")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

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


def parse_json_from_file(file_path: Path) -> list:
    """
    Robustly parse JSON from a file, handling markdown code fences and other formatting issues.
    Also handles multiple separate JSON objects in the file (combined into an array).

    Args:
        file_path: Path to the file containing JSON

    Returns:
        Parsed JSON data as a list

    Raises:
        json.JSONDecodeError: If JSON cannot be parsed after cleanup
    """
    text = file_path.read_text(encoding="utf-8").strip()

    # Try to extract all JSON objects from the file
    # Handle format like:
    # ```json
    # ### Module1
    # {...}
    # ```
    # ```json
    # ### Module2
    # {...}
    # ```

    # Split by ```json or ``` markers to find all JSON blocks
    blocks = []
    current_block = []
    in_json_block = False

    for line in text.split('\n'):
        line_stripped = line.strip()

        if line_stripped.startswith('```json') or line_stripped == '```':
            if in_json_block:
                # End of JSON block
                if current_block:
                    blocks.append('\n'.join(current_block))
                    current_block = []
                in_json_block = False
            else:
                # Start of JSON block
                in_json_block = True
        elif in_json_block:
            # Skip header lines like "### ModuleName"
            if not line_stripped.startswith('###'):
                current_block.append(line)

    # Add last block if any
    if current_block:
        blocks.append('\n'.join(current_block))

    # If no blocks found with fences, try parsing the whole text
    if not blocks:
        blocks = [text]

    # Parse each block as JSON and collect all objects
    all_objects = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Find JSON structure in this block - check for array first, then object
        start_idx = -1
        start_char = None

        # Try to find array first
        array_idx = block.find('[')
        obj_idx = block.find('{')

        # Use whichever comes first (array or object)
        if array_idx != -1 and (obj_idx == -1 or array_idx < obj_idx):
            start_idx = array_idx
            start_char = '['
        elif obj_idx != -1:
            start_idx = obj_idx
            start_char = '{'
        else:
            continue

        # Find matching closing bracket/brace
        stack = []
        pairs = {'[': ']', '{': '}'}
        closing = {']': '[', '}': '{'}
        end_idx = -1

        for i in range(start_idx, len(block)):
            char = block[i]
            if char in pairs:
                stack.append(char)
            elif char in closing:
                if stack and stack[-1] == closing[char]:
                    stack.pop()
                    if not stack:
                        end_idx = i + 1
                        break

        if end_idx != -1:
            json_text = block[start_idx:end_idx]
            try:
                obj = json.loads(json_text)
                if isinstance(obj, dict):
                    all_objects.append(obj)
                elif isinstance(obj, list):
                    all_objects.extend(obj)
            except json.JSONDecodeError:
                continue

    if all_objects:
        return all_objects

    # Fallback: try original simple parsing
    # Look for a JSON array
    array_start = text.find('[')
    if array_start != -1:
        start_idx = array_start
        stack = []
        pairs = {'[': ']', '{': '}'}
        closing = {']': '[', '}': '{'}

        for i in range(start_idx, len(text)):
            char = text[i]
            if char in pairs:
                stack.append(char)
            elif char in closing:
                if stack and stack[-1] == closing[char]:
                    stack.pop()
                    if not stack:
                        end_idx = i + 1
                        json_text = text[start_idx:end_idx]
                        data = json.loads(json_text)
                        if isinstance(data, list):
                            return data
                        elif isinstance(data, dict):
                            return [data]
                        break

    raise ValueError(f"Could not parse any JSON from {file_path}")


def generate_analysis_report(dir_path, input_filename, output_filename, report_title, report_description, emoji_map=None):
    """
    Generic function to generate a markdown report from JSON analysis files.

    Args:
        dir_path: Directory containing the input file
        input_filename: Name of input file (e.g., "story.txt", "deep.txt")
        output_filename: Name of output markdown file (e.g., "story.md", "deep.md")
        report_title: Title for the report
        report_description: Description text for the report
        emoji_map: Optional dictionary mapping module names to emojis

    Returns:
        None (writes to output markdown file)
    """
    INPUT_TXT = Path(os.path.join(dir_path, input_filename))
    OUTPUT_MD = Path(os.path.join(dir_path, output_filename))

    # Read and parse JSON content
    text = INPUT_TXT.read_text(encoding="utf-8")
    # Remove markdown code fence if present
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]  # Remove ```json
    if text.endswith("```"):
        text = text[:-3]  # Remove ```

    data = json.loads(text.strip())

    # Default emoji map if not provided
    if emoji_map is None:
        emoji_map = {}

    # Start building markdown
    md = [
        f"# {report_title}",
        "",
        report_description,
        "",
        "---",
        ""
    ]

    # Process each module
    for module_data in data:
        module_name = module_data.get("module", "Unknown")
        emoji = emoji_map.get(module_name.lower(), "📌")

        strengths = module_data.get("strengths", [])
        weaknesses = module_data.get("weaknesses", [])
        recommendations = module_data.get("recommendations", [])
        evidence = module_data.get("evidence", [])

        md.append(f"## {emoji} {module_name.title()}")
        md.append("")

        # Create table with 4 columns: Strengths, Weaknesses, Recommendations, Evidence
        md.append("<table>")
        md.append("<tr><th>✅ Strengths</th><th>⚠️ Weaknesses</th><th>💡 Recommendations</th><th>📝 Evidence</th></tr>")

        # Build single row with all four columns
        md.append("<tr>")

        # Strengths column
        if strengths:
            strengths_html = "<ul>" + "".join(f"<li>{s}</li>" for s in strengths) + "</ul>"
            md.append(f"<td style='vertical-align: top;'>{strengths_html}</td>")
        else:
            md.append("<td style='vertical-align: top;'>-</td>")

        # Weaknesses column
        if weaknesses:
            weaknesses_html = "<ul>" + "".join(f"<li>{w}</li>" for w in weaknesses) + "</ul>"
            md.append(f"<td style='vertical-align: top;'>{weaknesses_html}</td>")
        else:
            md.append("<td style='vertical-align: top;'>-</td>")

        # Recommendations column
        if recommendations:
            recommendations_html = "<ul>" + "".join(f"<li>{r}</li>" for r in recommendations) + "</ul>"
            md.append(f"<td style='vertical-align: top;'>{recommendations_html}</td>")
        else:
            md.append("<td style='vertical-align: top;'>-</td>")

        # Evidence column
        if evidence:
            evidence_html = "<ul>" + "".join(f"<li>{e}</li>" for e in evidence) + "</ul>"
            md.append(f"<td style='vertical-align: top;'>{evidence_html}</td>")
        else:
            md.append("<td style='vertical-align: top;'>-</td>")

        md.append("</tr>")
        md.append("</table>")
        md.append("")
        md.append("---")
        md.append("")

    # Write to file
    OUTPUT_MD.write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    print(f"Report saved to: {OUTPUT_MD}")


def generate_story_report(dir_path):
    """
    Generate a markdown report from story.txt containing storytelling analysis.
    Uses bullet format for each module.

    Args:
        dir_path: Directory containing story.txt

    Returns:
        None (writes to story.md file)
    """
    INPUT_TXT = Path(os.path.join(dir_path, "story.txt"))
    OUTPUT_MD = Path(os.path.join(dir_path, "story.md"))

    emoji_map = {
        "curiosity": "🔍",
        "coherence": "🔗",
        "emotional": "❤️",
        "narrative": "📖",
        "concrete2abstract": "🎯",
        "characters": "👥"
    }

    # Read and parse JSON content using robust parser
    try:
        data = parse_json_from_file(INPUT_TXT)
        print(f"DEBUG: Parsed data type: {type(data)}")
        print(f"DEBUG: Data length: {len(data) if isinstance(data, list) else 'N/A'}")
        if isinstance(data, list) and data:
            print(f"DEBUG: First item type: {type(data[0])}")
            print(f"DEBUG: First item content: {data[0]}")
    except Exception as e:
        print(f"Error loading story.txt: {e}")
        raise

    # Validate data structure
    if not isinstance(data, list):
        raise ValueError(f"Expected list of module objects, got {type(data)}. Data: {str(data)[:500]}")

    if data and not isinstance(data[0], dict):
        # Maybe the LLM wrapped the array in another structure?
        # Try to extract the actual data
        print(f"WARNING: First item is {type(data[0])}, not dict")
        print(f"Full data structure: {data}")
        raise ValueError(f"Expected list of dictionaries, but first item is {type(data[0])}. Full data: {str(data)[:500]}")

    # Start building markdown
    md = [
        "# 📊 Storytelling Analysis Report",
        "",
        "This report analyzes the storytelling effectiveness of the lecture across multiple dimensions.",
        "",
        "---",
        ""
    ]

    # Process each module with bullet format
    for module_data in data:
        if not isinstance(module_data, dict):
            print(f"Warning: Skipping non-dict item: {module_data}")
            continue

        module_name = module_data.get("module", "Unknown")
        emoji = emoji_map.get(module_name.lower(), "📌")

        strengths = module_data.get("strengths", [])
        weaknesses = module_data.get("weaknesses", [])
        recommendations = module_data.get("recommendations", [])
        evidence = module_data.get("evidence", [])

        md.append(f"## {emoji} {module_name.title()}")
        md.append("")

        # Strengths
        if strengths:
            md.append("**✅ Strengths:**")
            for s in strengths:
                md.append(f"- {s}")
            md.append("")

        # Weaknesses
        if weaknesses:
            md.append("**⚠️ Weaknesses:**")
            for w in weaknesses:
                md.append(f"- {w}")
            md.append("")

        # Recommendations
        if recommendations:
            md.append("**💡 Recommendations:**")
            for r in recommendations:
                md.append(f"- {r}")
            md.append("")

        # Evidence
        if evidence:
            md.append("**📝 Evidence:**")
            for e in evidence:
                md.append(f"- {e}")
            md.append("")

        md.append("---")
        md.append("")

    # Write to file
    OUTPUT_MD.write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    print(f"Report saved to: {OUTPUT_MD}")


def generate_deep_report(dir_path):
    """
    Generate a markdown report from deep.txt containing deep learning analysis.
    Uses bullet format for each module.

    Args:
        dir_path: Directory containing deep.txt

    Returns:
        None (writes to deep.md file)
    """
    INPUT_TXT = Path(os.path.join(dir_path, "deep.txt"))
    OUTPUT_MD = Path(os.path.join(dir_path, "deep.md"))

    emoji_map = {
        "communication": "💬",
        "content": "📚",
        "pedagogical": "🎓",
        "engagement": "⚡"
    }

    # Read and parse JSON content using robust parser
    try:
        data = parse_json_from_file(INPUT_TXT)
        print(f"DEBUG: Parsed data type: {type(data)}")
        print(f"DEBUG: Data length: {len(data) if isinstance(data, list) else 'N/A'}")
        if isinstance(data, list) and data:
            print(f"DEBUG: First item type: {type(data[0])}")
            print(f"DEBUG: First item content: {data[0]}")
    except Exception as e:
        print(f"Error loading deep.txt: {e}")
        raise

    # Validate data structure
    if not isinstance(data, list):
        raise ValueError(f"Expected list of module objects, got {type(data)}")

    if data and not isinstance(data[0], dict):
        raise ValueError(f"Expected list of dictionaries, but first item is {type(data[0])}. Data preview: {str(data)[:200]}")

    # Start building markdown
    md = [
        "# 🎯 Deep Analysis Report",
        "",
        "This report provides an in-depth analysis of the lecture's effectiveness across key teaching dimensions.",
        "",
        "---",
        ""
    ]

    # Process each module with bullet format
    for module_data in data:
        if not isinstance(module_data, dict):
            print(f"Warning: Skipping non-dict item: {module_data}")
            continue

        module_name = module_data.get("module", "Unknown")
        emoji = emoji_map.get(module_name.lower(), "📌")

        strengths = module_data.get("strengths", [])
        weaknesses = module_data.get("weaknesses", [])
        recommendations = module_data.get("recommendations", [])
        evidence = module_data.get("evidence", [])

        md.append(f"## {emoji} {module_name.title()}")
        md.append("")

        # Strengths
        if strengths:
            md.append("**✅ Strengths:**")
            for s in strengths:
                md.append(f"- {s}")
            md.append("")

        # Weaknesses
        if weaknesses:
            md.append("**⚠️ Weaknesses:**")
            for w in weaknesses:
                md.append(f"- {w}")
            md.append("")

        # Recommendations
        if recommendations:
            md.append("**💡 Recommendations:**")
            for r in recommendations:
                md.append(f"- {r}")
            md.append("")

        # Evidence
        if evidence:
            md.append("**📝 Evidence:**")
            for e in evidence:
                md.append(f"- {e}")
            md.append("")

        md.append("---")
        md.append("")

    # Write to file
    OUTPUT_MD.write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    print(f"Report saved to: {OUTPUT_MD}")



def generate_report(dir_path):
    """Generate a beautiful, styled markdown report from output.txt"""
    INPUT_TXT = Path(os.path.join(dir_path,"output.txt"))
    OUTPUT_MD = Path(os.path.join(dir_path,"output.md"))
    text = INPUT_TXT.read_text(encoding="utf-8")
    blocks = read_blocks(text)

    # Title - handle both string and JSON formats
    title_block = blocks.get("title", blocks.get("task_title", ""))
    try:
        # Strip markdown fence if present
        title_block = strip_markdown_json_fence(title_block)
        if title_block.startswith('{'):
            title_json = json.loads(title_block)
            title = title_json.get("title", "Untitled")
        else:
            # If it's just a plain string, use it directly
            title = title_block.strip() or "Untitled"
    except (json.JSONDecodeError, AttributeError):
        title = "Untitled"

    md = []

    # Beautiful header with styling
    md.append("# 📘 Class Analysis Report")
    md.append("")
    md.append(f"<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 12px; color: white; margin-bottom: 25px;'>")
    md.append(f"<h2 style='margin: 0; color: white;'>{title}</h2>")
    md.append(f"<p style='margin: 10px 0 0 0; opacity: 0.9; font-size: 0.95em;'>Comprehensive class analysis with examples, interactions, and insights</p>")
    md.append("</div>")
    md.append("")

    # Sections - with better styling
    sections_rows = parse_csv_block(blocks.get("sections", ""))
    if sections_rows and len(sections_rows) > 1:
        md.append("## 📚 Class Structure")
        md.append("")
        md.append("<div style='background: #f8fafc; padding: 20px; border-radius: 10px; margin: 15px 0;'>")

        for row in sections_rows[1:]:
            if len(row) >= 4:
                num, start, end, section_title = row[0], row[1], row[2], row[3]
                duration = row[4] if len(row) > 4 else ""
                md.append(f"<details style='margin: 8px 0;'>")
                md.append(f"<summary style='cursor: pointer; padding: 10px; background: white; border-radius: 6px; border-left: 3px solid #3b82f6;'>")
                md.append(f"<strong>{num}. {section_title}</strong> <span style='color: #6b7280; font-size: 0.9em;'>({start} - {end})</span>")
                md.append("</summary>")
                md.append(f"<div style='padding: 10px; margin-top: 5px;'>")
                md.append(f"<p><strong>⏱️ Duration:</strong> {duration}</p>")
                md.append(f"<p><strong>⏰ Time Range:</strong> {start} to {end}</p>")
                md.append("</div>")
                md.append("</details>")

        md.append("</div>")
        md.append("")
        md.append("---")
        md.append("")

    # Examples with improved styling
    examples_rows = parse_csv_block(blocks.get("examples", ""))
    if examples_rows and len(examples_rows) > 1:
        md.append("## 💡 Examples from Class")
        md.append("")
        md.append("<p style='color: #6b7280; font-style: italic;'>Real examples used during instruction</p>")
        md.append("")

        headers = [h.strip() for h in examples_rows[0]]

        for i, row in enumerate(examples_rows[1:], 1):
            if len(row) >= len(headers):
                example_dict = dict(zip(headers, row))
                topic = example_dict.get('Topic', 'Unknown')
                example = example_dict.get('Example', '')
                reference = example_dict.get('Reference', example_dict.get('reference', 'class'))

                # Color based on reference
                if 'external' in reference.lower():
                    border_color = '#9333ea'
                    bg_color = '#faf5ff'
                else:
                    border_color = '#22c55e'
                    bg_color = '#f0fdf4'

                md.append(f"<details style='margin: 10px 0;'>")
                md.append(f"<summary style='cursor: pointer; padding: 12px; background: {bg_color}; border-radius: 8px; border-left: 4px solid {border_color};'>")
                md.append(f"<strong>{i}. {topic}</strong> <span style='font-size: 0.85em; color: #6b7280;'>({reference})</span>")
                md.append("</summary>")
                md.append(f"<div style='padding: 15px; background: #f9fafb; border-radius: 5px; margin-top: 5px;'>")
                md.append(f"<p>{example}</p>")
                md.append("</div>")
                md.append("</details>")

        md.append("")
        md.append("<p style='font-size: 0.85em; color: #6b7280; margin-top: 10px;'>")
        md.append("<span style='color: #22c55e;'>●</span> Class examples  ")
        md.append("<span style='color: #9333ea;'>●</span> External examples")
        md.append("</p>")
        md.append("")
        md.append("---")
        md.append("")

    # Open questions with card layout
    oq_text = blocks.get("open_questions", "{}")
    oq_text = strip_markdown_json_fence(oq_text)
    try:
        oq = json.loads(oq_text)
    except json.JSONDecodeError:
        oq = {}

    if oq:
        md.append("## ❓ Questions for Students")
        md.append("")
        md.append("<p style='color: #6b7280; font-style: italic;'>Thought-provoking questions to assess understanding</p>")
        md.append("")

        # Simple questions
        simple = oq.get("simple", oq.get("simple_questions", []))
        if simple:
            md.append("<details open>")
            md.append("<summary style='cursor: pointer; font-size: 1.1em; padding: 10px; background: #ecfdf5; border-radius: 8px; margin: 10px 0;'>")
            md.append(f"<strong>🟢 Foundational Questions</strong> <span style='color: #6b7280; font-size: 0.9em;'>({len(simple)} questions)</span>")
            md.append("</summary>")
            md.append("<div style='padding: 15px;'>")
            for i, q in enumerate(simple, 1):
                md.append(f"<p><strong>{i}.</strong> {q}</p>")
            md.append("</div>")
            md.append("</details>")
            md.append("")

        # Difficult questions
        difficult = oq.get("difficult", oq.get("difficult_questions", []))
        if difficult:
            md.append("<details open>")
            md.append("<summary style='cursor: pointer; font-size: 1.1em; padding: 10px; background: #fef3c7; border-radius: 8px; margin: 10px 0;'>")
            md.append(f"<strong>🟡 Advanced Questions</strong> <span style='color: #6b7280; font-size: 0.9em;'>({len(difficult)} questions)</span>")
            md.append("</summary>")
            md.append("<div style='padding: 15px;'>")
            for i, q in enumerate(difficult, 1):
                md.append(f"<p><strong>{i}.</strong> {q}</p>")
            md.append("</div>")
            md.append("</details>")
            md.append("")

        md.append("---")
        md.append("")

    # Interactions with timeline feel
    inter_rows = parse_csv_block(blocks.get("interaction", ""))
    if inter_rows and len(inter_rows) > 1:
        md.append("## 💬 Class Interactions")
        md.append("")
        md.append("<p style='color: #6b7280; font-style: italic;'>Student engagement and participation moments</p>")
        md.append("")

        headers = [h.strip() for h in inter_rows[0]]

        for row in inter_rows[1:]:
            if len(row) >= len(headers):
                inter_dict = dict(zip(headers, row))
                time = inter_dict.get('Time', '')
                itype = inter_dict.get('Type', 'interaction')
                description = inter_dict.get('Description', '')

                # Style based on type
                if 'question' in itype.lower():
                    emoji = '❓'
                    color = '#f59e0b'
                    bg = '#fef3c7'
                elif 'discussion' in itype.lower():
                    emoji = '💭'
                    color = '#3b82f6'
                    bg = '#dbeafe'
                else:
                    emoji = '💬'
                    color = '#8b5cf6'
                    bg = '#f3e8ff'

                md.append(f"<div style='margin: 12px 0; padding: 12px; background: {bg}; border-left: 4px solid {color}; border-radius: 6px;'>")
                md.append(f"<p style='margin: 0;'><strong>{emoji} {time}</strong> - <em style='color: {color};'>{itype}</em></p>")
                md.append(f"<p style='margin: 8px 0 0 0;'>{description}</p>")
                md.append("</div>")

        md.append("")
        md.append("---")
        md.append("")

    # Difficult topics with solutions
    diff_rows = parse_csv_block(blocks.get("difficult_topics", ""))
    if diff_rows and len(diff_rows) > 1:
        md.append("## ⚠️ Challenging Topics")
        md.append("")
        md.append("<p style='color: #dc2626; font-style: italic;'>Areas where students needed additional support</p>")
        md.append("")

        headers = [h.strip() for h in diff_rows[0]]

        for i, row in enumerate(diff_rows[1:], 1):
            if len(row) >= len(headers):
                diff_dict = dict(zip(headers, row))
                topic = diff_dict.get('Topic', 'Unknown')
                reason = diff_dict.get('Reason for difficulty', diff_dict.get('Reason', ''))
                recommendation = diff_dict.get('Recommendation for improvement', diff_dict.get('Recommendation', ''))

                md.append(f"<details style='margin: 10px 0;'>")
                md.append(f"<summary style='cursor: pointer; padding: 12px; background: #fef2f2; border-radius: 8px; border-left: 4px solid #ef4444;'>")
                md.append(f"<strong>{i}. {topic}</strong>")
                md.append("</summary>")
                md.append(f"<div style='padding: 15px; background: #f9fafb; border-radius: 5px; margin-top: 5px;'>")
                if reason:
                    md.append(f"<p><strong>🔍 Why it's challenging:</strong> {reason}</p>")
                if recommendation:
                    md.append(f"<p><strong>💡 Suggestion:</strong> {recommendation}</p>")
                md.append("</div>")
                md.append("</details>")

        md.append("")

    OUTPUT_MD = Path(os.path.join(dir_path,"output.md"))
    OUTPUT_MD.write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    print(f"✅ Beautiful markdown report saved to: {OUTPUT_MD}")





if __name__ == "__main__":
    # Example usage with your table
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Process video
    t0 = time.time()
    #1 basic
    sections_file=os.path.join(config["videos_dir"],"sections.csv")
#     # Define expected headers
#     # When reading your file:
#     df_raw = pd.read_csv(sections_file, header=None)  # or header=0 if you know it has headers
#     df = normalize_schedule_df(df_raw)
# #
#     df =read_sections_file(sections_file)
#
  #  generate_report(config["videos_dir"])
    #2 deep
   # generate_deep_report(config["videos_dir"])
    ## story telling
    generate_story_report(config["videos_dir"])
    logger.info(f'Pipeline completed in {time.time() - t0:.3f}s')
