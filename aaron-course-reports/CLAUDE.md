# Instructions for coding agents

Start with `AGENT_TASK.md`: the task, the rules the code must keep, priorities and acceptance criteria.
Content and design rules for the reports are in `docs/GUIDELINES.md`. Do not change the report design or section order without asking.

- Run `pytest -q` before and after every change.
- Never add LLM calls before Layer 3 (`narrative.py`). Every number in a report is computed in code.
- Never pass student-level data to the LLM or into the Markdown output.
- Hebrew copy: no em dashes, no "לא X אלא Y", no emoji.
