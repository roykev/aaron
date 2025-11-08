# Teacher Report Unified Mode Guide

## Overview

The teacher report pipeline can now intelligently combine multiple analyses into a **single LLM call** for massive efficiency gains, while still allowing you to **choose exactly which parts to generate**.

## Configuration Flexibility

You have **full control** over which parts to generate via `config.yaml`:

```yaml
teacher_reports:
  use_unified_mode: true         # Enable smart unified mode (recommended)
  generate_basic: true            # Class structure, examples, questions
  generate_deep: true             # Pedagogical analysis
  generate_story: true            # Storytelling analysis
  generate_smart_insights: true  # AI synthesis (requires deep + story)
  generate_markdown: true         # Pretty markdown reports
```

## How It Works

### Intelligent Unified Mode

The pipeline is **smart** about when to use unified mode:

- ✅ **2-3 parts enabled**: Uses unified mode (1 LLM call for all)
- ❌ **Only 1 part enabled**: Uses separate mode (no efficiency gain from unifying)
- ✅ **0 parts enabled**: Skips analysis, only generates markdown/insights if requested

### Example Scenarios

#### Scenario 1: All Three Parts (Maximum Efficiency)
```yaml
teacher_reports:
  use_unified_mode: true
  generate_basic: true
  generate_deep: true
  generate_story: true
```

**What happens:**
- 1 LLM call generates all three: output.txt, deep.txt, story.txt
- ~75% cost and time savings vs. 3 separate calls

**Log output:**
```
Mode: Unified (1 call for 3 parts)
🚀 UNIFIED MODE: Generating basic + deep + story in ONE LLM call
✅ Unified analysis completed in 45.2s
   Saved: output.txt, deep.txt, story.txt
```

---

#### Scenario 2: Only Deep + Story (Smart Insights Focus)
```yaml
teacher_reports:
  use_unified_mode: true
  generate_basic: false           # Skip basic
  generate_deep: true
  generate_story: true
  generate_smart_insights: true   # Needs deep + story
```

**What happens:**
- 1 LLM call generates deep.txt + story.txt
- Smart insights reads those files and generates synthesis
- Total: 2 LLM calls (vs. 3 in separate mode)

**Log output:**
```
Mode: Unified (1 call for 2 parts)
🚀 UNIFIED MODE: Generating deep + story in ONE LLM call
✅ Unified analysis completed in 38.5s
   Saved: deep.txt, story.txt
Step 4/5: Generating AI-powered smart insights...
✅ Smart insights saved
```

---

#### Scenario 3: Only Basic Analysis
```yaml
teacher_reports:
  use_unified_mode: true
  generate_basic: true
  generate_deep: false
  generate_story: false
```

**What happens:**
- Skips unified mode (only 1 part, no efficiency gain)
- Uses separate call for basic report
- Total: 1 LLM call

**Log output:**
```
Mode: Separate calls
Step 1/5: Generating basic teacher report (output.txt)...
✅ Basic report saved
```

---

#### Scenario 4: Only Markdown (No Analysis)
```yaml
teacher_reports:
  use_unified_mode: true
  generate_basic: false           # Already have output.txt
  generate_deep: false            # Already have deep.txt
  generate_story: false           # Already have story.txt
  generate_markdown: true         # Just beautify existing files
```

**What happens:**
- Skips all LLM analysis
- Only generates markdown from existing .txt files
- Total: 0 LLM calls

**Log output:**
```
Step 5/5: Generating markdown reports and snapshot...
✅ Markdown generation completed
```

---

#### Scenario 5: Force Separate Mode
```yaml
teacher_reports:
  use_unified_mode: false         # Disable unified mode
  generate_basic: true
  generate_deep: true
  generate_story: true
```

**What happens:**
- Makes 3 separate LLM calls (one for each part)
- Useful for debugging or if unified mode has issues
- Total: 3 LLM calls

**Log output:**
```
Mode: Separate calls
Step 1/5: Generating basic teacher report...
Step 2/5: Generating deep analysis...
Step 3/5: Generating storytelling analysis...
```

## Cost & Performance Comparison

| Configuration | LLM Calls | Relative Cost | Relative Time |
|---------------|-----------|---------------|---------------|
| All 3 parts (unified) | 1 | 33% | 33% |
| All 3 parts (separate) | 3 | 100% | 100% |
| 2 parts (unified) | 1 | 33% | 33% |
| 2 parts (separate) | 2 | 66% | 66% |
| 1 part only | 1 | 33% | 33% |
| + Smart insights | +1 | +33% | +33% |

*Percentages relative to 3 separate calls*

## Recommendations

### ✅ Best Practices

1. **Keep `use_unified_mode: true`** (default)
   - Automatically optimizes based on what you enable
   - No downside, only benefits

2. **Enable what you need**
   - Want quick overview? → Only `generate_basic: true`
   - Want deep analysis? → `generate_deep: true` + `generate_story: true`
   - Want everything? → Enable all three

3. **Use smart insights when you have deep + story**
   ```yaml
   generate_deep: true
   generate_story: true
   generate_smart_insights: true
   ```

4. **Regenerate markdown without re-analyzing**
   - Set all generate_* to `false`
   - Set `generate_markdown: true`
   - Instant markdown regeneration from existing files

### ⚠️ When to Disable Unified Mode

Disable `use_unified_mode` only if:
- Debugging JSON parsing issues
- Testing individual analysis prompts
- Comparing output quality (shouldn't differ)

## Output Files

Regardless of mode, you get the same files:

| Flag | Output File | Content |
|------|-------------|---------|
| `generate_basic` | `output.txt` | Sections, examples, questions, interactions, difficult topics |
| `generate_deep` | `deep.txt` | Communication, engagement, pedagogy, content (JSON) |
| `generate_story` | `story.txt` | Curiosity, coherence, emotional, narrative (JSON) |
| `generate_markdown` | `output.md` | Beautiful formatted basic report |
| `generate_markdown` | `deep.md` | Beautiful formatted deep report |
| `generate_markdown` | `story.md` | Beautiful formatted story report |
| `generate_smart_insights` | `smart_insights.json` | AI synthesis (raw) |
| `generate_smart_insights` | `smart_insights.md` | AI synthesis (beautiful) |

## Examples

### Example 1: Quick Class Overview
```yaml
teacher_reports:
  use_unified_mode: true
  generate_basic: true
  generate_deep: false
  generate_story: false
  generate_markdown: true
```
→ Generates: `output.txt`, `output.md` (1 LLM call)

### Example 2: Complete Analysis Package
```yaml
teacher_reports:
  use_unified_mode: true
  generate_basic: true
  generate_deep: true
  generate_story: true
  generate_smart_insights: true
  generate_markdown: true
```
→ Generates: Everything! (2 LLM calls: 1 unified + 1 for insights)

### Example 3: Pedagogical Focus Only
```yaml
teacher_reports:
  use_unified_mode: true
  generate_basic: false
  generate_deep: true
  generate_story: false
  generate_markdown: true
```
→ Generates: `deep.txt`, `deep.md` (1 LLM call)

## FAQ

**Q: Does unified mode affect quality?**
A: No! Same prompts, same LLM, same quality. Just more efficient.

**Q: What if unified mode fails?**
A: Automatic fallback to separate mode. You'll see: `❌ Unified analysis failed - falling back to separate mode`

**Q: Can I regenerate just one part later?**
A: Yes! Just enable that part and disable the others. It will use 1 LLM call for that part.

**Q: Is smart insights included in unified mode?**
A: No. Smart insights always runs separately because it analyzes the already-generated files.

**Q: Should I ever disable use_unified_mode?**
A: Rarely. Only for debugging. Unified mode is smart enough to handle all scenarios efficiently.

## Summary

✅ **Yes! You can choose exactly which parts to generate.**
✅ **Unified mode is smart and adapts automatically.**
✅ **No efficiency loss - it optimizes based on your choices.**
✅ **Same quality output whether unified or separate.**

Just set the flags for what you want, and the pipeline handles the rest!
