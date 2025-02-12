import io
import os
import pandas as pd
from datetime import datetime, timedelta
def parse_time(time_str):
    """Parse time in format 'HH:MM:SS.sss'."""
    return datetime.strptime(time_str, "%H:%M:%S.%f")


def generate_html(name, date, summary, scenes_df, screenshots_dir,output_path):
    # Ensure scenes are sorted by their start time
    scenes_df = scenes_df.sort_values(by="start_tc")

    # Calculate total duration
    start_time = parse_time(scenes_df.iloc[0]['start_tc'])
    end_time = parse_time(scenes_df.iloc[-1]['end_tc'])
    total_duration = str(end_time - start_time)

    # Get the list of screenshot files, assuming they are named numerically (0.jpg, 1.jpg, ...)
    screenshot_files = sorted(os.listdir(screenshots_dir), key=lambda x: int(x.split('.')[0]))

    # HTML Header
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{name} - Lecture Summary</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                line-height: 1.6;
            }}
            h1, h2, h3 {{
                color: #333;
            }}
            .toc {{
                margin-top: 20px;
                padding: 10px;
                background-color: #f4f4f4;
                border: 1px solid #ddd;
            }}
            .toc a {{
                text-decoration: none;
                color: #007BFF;
            }}
            .scene {{
                margin-top: 40px;
                padding: 10px;
                border-bottom: 1px solid #ddd;
            }}
            .comments {{
                margin-top: 20px;
                padding: 10px;
                border: 1px dashed #aaa;
                background-color: #fafafa;
            }}
            .back-to-toc {{
                margin-top: 10px;
                display: inline-block;
                text-decoration: none;
                color: #007BFF;
            }}
            img {{
                width: 300px;  /* Set fixed width */
                height: auto; /* Maintain aspect ratio */
                display: block;
                margin: 10px 0; /* Add spacing around images */
            }}
        </style>
    </head>
    <body>
        <h1>{name}</h1>
        <p><strong>Date:</strong> {date}</p>
        <p><strong>Total Duration:</strong> {total_duration}</p>
        <p><strong>Summary:</strong> {summary}</p>
        <div id="toc" class="toc">
            <h2>Table of Contents</h2>
            <ul>
    """
    # Add TOC links
    for i, row in scenes_df.iterrows():
        html += f'<li><a href="#scene-{i}">Scene {i + 1}: {row["summary"]}</a></li>'
    html += """
            </ul>
        </div>
    """

    # Add scene sections
    for i, row in scenes_df.iterrows():
        screenshot_path = os.path.join(screenshots_dir, screenshot_files[i])
        html += f"""
        <div id="scene-{i}" class="scene">
            <h3>Scene {i + 1}</h3>
            <p><strong>From:</strong> {row['start_tc']} | <strong>To:</strong> {row['end_tc']}</p>
            <p><strong>Description:</strong> {row['summary']}</p>
            <img src="{screenshot_path}" alt="Screenshot for Scene {i + 1}" style="max-width:100%;height:auto;">
            <div class="comments">
                <p><strong>Comments & Questions:</strong></p>
                <textarea rows="4" style="width:100%;"></textarea>
            </div>
            <a href="#toc" class="back-to-toc">Back to Table of Contents</a>
        </div>
        """

    # HTML Footer
    html += """
    </body>
    </html>
    """

    # Save to a file
    with open(output_path, "w") as file:
        file.write(html)

    return output_path
if __name__ == '__main__':
    dirpath = "/home/roy/OneDriver/WORK/ideas/aaron/Miller/AI for business/2024/2/2"
    # Example input data
    name = "AI for business"
    date = "2024-11-17"
    summary_file = os.path.join(dirpath,"short.txt")
    with io.open(summary_file, 'r', encoding='utf8') as f:
        summary = f.read()

    #summary = "This lecture explores the impact of artificial intelligence on modern educational practices."
    df_file=os.path.join(dirpath,"out.csv")
    scenes_df = pd.read_csv(df_file)


    # Example screenshots directory
    screenshots_dir = os.path.join(dirpath,"scenes")
    output_path= os.path.join(dirpath,"printout.html")
    # Generate HTML and return file path
    generate_html(name, date, summary, scenes_df, screenshots_dir,output_path)


