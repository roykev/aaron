"""
Course-level analysis: aggregates across all lectures.

Analyzes all lectures in a course and produces a 5-panel strategic dashboard:
1. Course Snapshot - engagement, segments, overall performance
2. What Students Struggle With - recurring concepts + problematic lessons
3. What Consistently Worked - teaching patterns that work across ≥2 lessons
4. Teaching vs Learning Gap - systemic gaps (≥2 lessons, consistent direction)
5. Prerequisite & Knowledge Gaps - foundational gaps students lack

Runs 2-3 times per semester (e.g., weeks 5, 10, 13).
"""

from .layer0_normalize import CourseLayer0Pipeline
from .layer1_aggregate import CourseLayer1Pipeline

__all__ = [
    "CourseLayer0Pipeline",
    "CourseLayer1Pipeline",
]