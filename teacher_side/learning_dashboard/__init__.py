"""
Learning Dashboard System

A comprehensive system for analyzing student learning data and generating actionable teaching insights.

## Structure

- **common/**: Shared models, configuration, and utilities
- **class_level/**: Per-lecture analysis (4-panel dashboard)
- **course_level/**: Course-wide analysis (5-panel strategic dashboard)

## Usage

### Class-Level Analysis (single lecture)
```python
from teacher_side.learning_dashboard import LearningDashboardConfig
from teacher_side.learning_dashboard.class_level import (
    Layer0Pipeline, Layer1Pipeline, Layer15Pipeline,
    Layer2Pipeline, Layer3Pipeline
)

# Configure and run pipeline
config = LearningDashboardConfig.from_files(...)
layer0 = Layer0Pipeline(config)
layer0_output = layer0.run(lecture_id="...")
# ... run other layers
```

### Course-Level Analysis (all lectures)
```python
from teacher_side.learning_dashboard.course_level import CoursePipeline

# Run course-level analysis
pipeline = CoursePipeline(config)
course_report = pipeline.run()
```
"""

__version__ = "1.0.0"

# Re-export common classes for convenience
from .common import (
    LearningDashboardConfig,
    SignalType,
    EvidenceStrength,
    GapDirection,
    ReliabilityFlag,
)

__all__ = [
    "LearningDashboardConfig",
    "SignalType",
    "EvidenceStrength",
    "GapDirection",
    "ReliabilityFlag",
]