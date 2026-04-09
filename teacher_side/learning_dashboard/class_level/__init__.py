"""
Class-level analysis: generates per-lecture dashboards.

Analyzes a single lecture and produces a 4-panel dashboard:
1. Quick Snapshot - lesson performance overview
2. Issues & What To Do - struggling topics + actionable suggestions
3. What Worked Well - successful concepts
4. Teaching vs Learning Gap - mismatches between investment and outcome
"""
from .layer0_data import Layer0Pipeline, DataLoader
from .layer1_clustering import Layer1Pipeline
from .layer15_mapping import Layer15Pipeline
from .layer2_ranking import Layer2Pipeline
from .layer3_narrative import Layer3Pipeline
from .html_renderer import render_html_dashboard

__all__ = [
    "Layer0Pipeline",
    "DataLoader",
    "Layer1Pipeline",
    "Layer15Pipeline",
    "Layer2Pipeline",
    "Layer3Pipeline",
    "render_html_dashboard",
]