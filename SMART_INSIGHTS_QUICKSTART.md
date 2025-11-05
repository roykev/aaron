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
- Overall positive assessment celebrating strengths
- Key takeaway message with a path forward
- Outstanding strength (what worked best)
- Top 3-4 strengths to continue
- Top 3-4 growth opportunities (framed positively)
- 4-5 suggested actions for next class
- Long-term growth opportunity

**Language approach:**
- ✅ Positive, encouraging, constructive tone
- ✅ Celebrates strengths before discussing growth areas
- ✅ Uses soft language like "opportunity to enhance" instead of "weakness"
- ✅ No exact percentages or specific numbers in outcomes
- ✅ Qualitative improvements (e.g., "better engagement" not "40% more questions")

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

## 🌟 Overall Assessment
The instructor demonstrates wonderful engagement techniques and creates
a warm learning environment. There are exciting opportunities to build
on these strengths by enhancing the scaffolding of complex concepts...

## 💡 Key Message
Continue leveraging your excellent questioning skills while building
more bridges between concepts to deepen student understanding

## ⭐ Outstanding Strength
### Curiosity
**What's exceptional:** Excellent use of provocative questions that
spark genuine student interest...
*Evidence:* "Students asked thoughtful questions throughout..."

## 🎯 Continue These Successful Practices
### 1. Emotional Engagement
**Success:** High enthusiasm and authentic passion for material
**Impact:** Creates a positive learning environment where students
feel excited to participate
**Evidence:** Multiple instances of excitement and wonder...

## 🌱 Opportunities for Growth
### 1. Scaffolding
**Opportunity:** There's potential to create even more connections
between concepts to support student learning
**Potential benefit:** Students could build understanding more
naturally as concepts flow into each other
**How to build on this:** Consider adding brief transitions that
explicitly link new topics to previous discussions
**Context:** Students mentioned wanting more context...

## 📋 Suggested Actions for Next Class
1. 🟢 **Try adding a brief recap at the start of each section**
   *Potential outcome:* Students will better connect new material
   to what they already know, leading to deeper retention
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
- Positive, encouraging tone throughout
- Celebrates strengths before discussing growth
- Avoids harsh language and exact numbers
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
