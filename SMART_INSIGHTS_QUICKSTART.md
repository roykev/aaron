# 🦉 Smart Insights - Quick Start Guide

## What You Asked For

You have 3 teacher report outputs:
- `output.txt` - Basic class analysis
- `deep.txt` - Deep pedagogical analysis (JSON)
- `story.txt` - Storytelling analysis (JSON)

You want to **call SnapshotGenerator with an LLM** to identify the **MOST IMPORTANT** insights and recommendations.

## ✅ Solution: Two Approaches

### Approach 1: LLM-Based Smart Insights (RECOMMENDED) 🤖

This uses an **LLM to intelligently analyze** deep.txt and story.txt to identify the most significant insights.

**To generate smart insights from your existing files:**

```bash
python teacher_side/generate_smart_insights.py
```

This will:
1. Load deep.txt and story.txt
2. Call OpenRouter LLM to analyze both files
3. Generate `smart_insights.json` - Raw LLM output
4. Generate `smart_insights.md` - Beautiful formatted report

**Output includes:**
- Overall assessment
- Key takeaway message
- Top strength (what worked best)
- Top 3-4 strengths to preserve
- Top 3-4 weaknesses to improve
- 4-5 priority actions for next class
- Long-term focus area

### Approach 2: Mechanical Snapshot (No LLM)

This uses the existing SnapshotGenerator that mechanically extracts items without AI analysis.

```bash
python teacher_side/generate_smart_snapshot.py
```

This generates:
- `teaching_snapshot.md` - Minimalist snapshot
- `teaching_snapshot_expanded.md` - Full detailed report

## 📁 File Locations

All outputs are saved to: `{videos_dir}/output/`

Where `videos_dir` is defined in your `config.yaml`

## 🎯 Recommendation

**Use Approach 1 (LLM-Based)** because:
- ✅ Actually analyzes the content intelligently
- ✅ Prioritizes by impact on learning
- ✅ Provides evidence-based recommendations
- ✅ Ranks items by importance
- ✅ Synthesizes insights across both analyses

**Use Approach 2 (Mechanical)** if:
- You want instant results without API calls
- You prefer a simpler rule-based approach
- You want both minimalist and expanded versions

## 🔧 Configuration

Edit `config.yaml` to control generation:

```yaml
teacher_reports:
  generate_basic: false          # Already have output.txt
  generate_deep: false           # Already have deep.txt
  generate_story: false          # Already have story.txt
  generate_smart_insights: true  # Generate AI insights ← NEW!
  generate_markdown: true        # Generate markdown reports

language: "Hebrew"  # or "English"
```

## 🚀 Quick Commands

### For your situation (already have the 3 files):

```bash
# Generate AI-powered smart insights (RECOMMENDED)
python teacher_side/generate_smart_insights.py

# Or use mechanical snapshot
python teacher_side/generate_smart_snapshot.py
```

### To run the complete pipeline (from scratch):

```bash
# Set flags in config.yaml first, then:
python teacher_side/run_teacher_pipeline.py
```

## 📊 Output Comparison

### LLM-Based Smart Insights (`smart_insights.md`):
```markdown
# 🦉 AaronOwl Smart Insights Report

## 📊 Overall Assessment
The instructor demonstrates strong engagement techniques...

## 💡 Key Takeaway
Focus on scaffolding complex concepts to improve student comprehension

## ⭐ Top Strength
### Curiosity
**What worked:** Excellent use of provocative questions...
*Evidence:* "Students asked 12 questions in first 15 minutes..."

## 🔒 Preserve - What's Working Well
### 1. Emotional Engagement
**Strength:** High enthusiasm and passion for material
**Why it matters:** Creates positive learning environment
**Evidence:** Multiple instances of "this is beautiful"...

## 📈 Improve - Priority Areas
### 1. Scaffolding
**Issue:** Large jumps between concepts
**Student impact:** Students struggled with advanced topics
**Solution:** Break complex ideas into smaller steps
**Evidence:** 3 difficult topics identified...

## 📋 Action Plan for Next Class
1. 🟢 **Add 2 minute recap at start of each section**
   *Expected outcome:* Better retention
```

### Mechanical Snapshot (`teaching_snapshot.md`):
```markdown
# 🦉 AaronOwl - תמונת מצב

## Class Title

**Main message:** General assessment

**Duration:** 60 minutes

## ✨ What Worked Great
**Curiosity:** First strength listed

## 🔒 To Preserve
1. Curiosity: [expandable details]
2. Coherence: [expandable details]
3. Emotional: [expandable details]
```

## 🎨 Key Difference

**LLM-Based:**
- Analyzes and prioritizes by impact
- Provides context and reasoning
- Evidence-based recommendations
- Actionable next steps

**Mechanical:**
- Simply takes first few items from each list
- No intelligent prioritization
- More compact format
- Faster generation

## 💡 Pro Tip

For the **best results**, run both:

```bash
# Get intelligent AI analysis
python teacher_side/generate_smart_insights.py

# Get quick reference snapshot
python teacher_side/generate_smart_snapshot.py
```

Then:
1. Read `smart_insights.md` for **actionable recommendations**
2. Use `teaching_snapshot.md` as a **quick reference**
3. Dive into `teaching_snapshot_expanded.md` for **full details**

## ⚙️ Requirements

- Python 3.7+
- OpenRouter API key (configured in your environment)
- Existing files: `output.txt`, `deep.txt`, `story.txt`

## 🐛 Troubleshooting

**"Missing required files"**
- Ensure output.txt, deep.txt, and story.txt exist in the output directory
- Check they contain valid data

**"Could not parse JSON"**
- Verify deep.txt and story.txt contain valid JSON
- They can be wrapped in markdown fences (```json...```)

**"LLM API error"**
- Check your OpenRouter API key is configured
- Verify network connectivity
- Check model availability in config.yaml

## 📚 More Information

See [README_SMART_SNAPSHOT.md](teacher_side/README_SMART_SNAPSHOT.md) for detailed documentation.
