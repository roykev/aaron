"""
FinalGrade target: loads teacher-supplied grades CSV and merges on email.

Expected CSV format (two columns, header required):
  email,final_grade
  student@institution.ac.il,82
  ...

The file never leaves the teacher's machine in the federation workflow.
"""
from pathlib import Path

import pandas as pd

from .base import TargetStrategy


class FinalGrade(TargetStrategy):
    name = "final_grade"

    def __init__(self, grades_csv: str):
        self.grades_path = Path(grades_csv)

    def build(self, features: pd.DataFrame) -> pd.Series:
        if not self.grades_path.exists():
            raise FileNotFoundError(f"Grades file not found: {self.grades_path}")

        grades = pd.read_csv(self.grades_path)
        grades.columns = [c.strip().lower() for c in grades.columns]

        if 'email' not in grades.columns or 'final_grade' not in grades.columns:
            raise ValueError("Grades CSV must have 'email' and 'final_grade' columns")

        grades['email'] = grades['email'].str.lower().str.strip()
        grades = grades.set_index('email')['final_grade']

        target = features.index.map(grades)
        matched = target.notna().sum()
        print(f"Final grade target: {matched}/{len(features)} students matched")
        return target.rename('target')

    def description(self) -> str:
        return f"Final course grade from {self.grades_path.name}"
