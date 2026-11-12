"""
HTML Dashboard Renderer
Generates a simple HTML page with 4 panels from the markdown output.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict
import markdown


def render_html_dashboard(
    panels: Dict[str, str],
    lecture_name: str,
    output_path: Path,
) -> Path:
    """
    Render the 4-panel dashboard as HTML.

    Args:
        panels: Dict with keys: quick_snapshot, issues, worked_well, gaps
        lecture_name: Name of the lecture
        output_path: Path to save HTML file

    Returns:
        Path to generated HTML file
    """
    # Convert markdown to HTML for each panel
    html_panels = {}
    for key, content in panels.items():
        # Use markdown library to convert to HTML
        html_content = markdown.markdown(content, extensions=['extra', 'nl2br'])
        html_panels[key] = html_content

    # Create HTML template
    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Learning Dashboard - {lecture_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
            direction: rtl;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            background: white;
            border-radius: 15px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}

        h1 {{
            color: #667eea;
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        .subtitle {{
            color: #666;
            font-size: 1rem;
        }}

        .dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 2rem;
            margin-bottom: 2rem;
        }}

        .panel {{
            background: white;
            border-radius: 15px;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}

        .panel:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.15);
        }}

        .panel-snapshot {{
            grid-column: 1 / -1;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}

        .panel-snapshot h2 {{
            color: white;
        }}

        .panel-snapshot strong {{
            color: #fff;
            background: rgba(255,255,255,0.2);
            padding: 0.2rem 0.5rem;
            border-radius: 5px;
        }}

        .panel-issues {{
            border-left: 5px solid #ef4444;
        }}

        .panel-worked {{
            border-left: 5px solid #10b981;
        }}

        .panel-gaps {{
            border-left: 5px solid #f59e0b;
        }}

        h2 {{
            color: #1f2937;
            font-size: 1.5rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #e5e7eb;
        }}

        h3 {{
            color: #374151;
            font-size: 1.2rem;
            margin-top: 1.5rem;
            margin-bottom: 0.5rem;
        }}

        p {{
            color: #4b5563;
            line-height: 1.6;
            margin-bottom: 1rem;
        }}

        strong {{
            color: #1f2937;
            font-weight: 600;
        }}

        blockquote {{
            border-right: 4px solid #667eea;
            padding-right: 1rem;
            margin: 1rem 0;
            font-style: italic;
            color: #6b7280;
        }}

        .panel-snapshot blockquote {{
            border-right-color: rgba(255,255,255,0.5);
            color: rgba(255,255,255,0.9);
        }}

        ul {{
            margin-right: 1.5rem;
            margin-bottom: 1rem;
        }}

        li {{
            color: #4b5563;
            line-height: 1.6;
            margin-bottom: 0.5rem;
        }}

        .empty-panel {{
            text-align: center;
            padding: 3rem 2rem;
            color: #9ca3af;
            font-style: italic;
        }}

        footer {{
            text-align: center;
            color: white;
            margin-top: 2rem;
            padding: 1rem;
            font-size: 0.9rem;
            opacity: 0.8;
        }}

        @media (max-width: 768px) {{
            .dashboard {{
                grid-template-columns: 1fr;
            }}

            body {{
                padding: 1rem;
            }}

            .panel {{
                padding: 1.5rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Learning Dashboard</h1>
            <div class="subtitle">{lecture_name}</div>
        </header>

        <div class="dashboard">
            <!-- Quick Snapshot Panel -->
            <div class="panel panel-snapshot">
                <h2>📸 Quick Snapshot</h2>
                <div class="panel-content">
                    {html_panels.get('quick_snapshot', '<p class="empty-panel">No snapshot data available</p>')}
                </div>
            </div>

            <!-- Issues Panel -->
            <div class="panel panel-issues">
                <h2>⚠️ Issues & What To Do</h2>
                <div class="panel-content">
                    {html_panels.get('issues', '<p class="empty-panel">No significant issues detected in available data.</p>')}
                </div>
            </div>

            <!-- Worked Well Panel -->
            <div class="panel panel-worked">
                <h2>✅ What Worked Well</h2>
                <div class="panel-content">
                    {html_panels.get('worked_well', '<p class="empty-panel">Insufficient data to confirm what worked this lesson.</p>')}
                </div>
            </div>

            <!-- Gaps Panel -->
            <div class="panel panel-gaps">
                <h2>📉 Teaching vs Learning Gap</h2>
                <div class="panel-content">
                    {html_panels.get('gaps', '<p class="empty-panel">No significant teaching-learning mismatches detected.</p>')}
                </div>
            </div>
        </div>

        <footer>
            Generated by Learning Dashboard System | Claude-powered analysis
        </footer>
    </div>
</body>
</html>
"""

    # Write HTML to file
    output_path.write_text(html, encoding='utf-8')

    return output_path