# Disable Anthropic Feature

## Overview

This feature allows you to completely disable Anthropic API usage in the teacher report pipeline. This is useful for:

- **Cost control** - Avoid using paid Anthropic API when free alternatives are available
- **API quota management** - Prevent hitting Anthropic rate limits
- **Testing alternative models** - Ensure you're only using non-Anthropic models

## Configuration

Add the `disable_anthropic` flag to your `config.yaml`:

```yaml
llm:
  # Backend selection: false = Anthropic (default), true = OpenRouter
  use_openrouter: true

  # Disable Anthropic completely - if true, will reject any Anthropic models
  # This ensures no Anthropic API calls are made, useful for cost control
  disable_anthropic: true

  # When disable_anthropic: true, use only non-Anthropic models
  model: "moonshotai/kimi-k2:free"
  # Other options:
  # model: "google/gemini-2.0-flash-exp:free"
  # model: "deepseek/deepseek-chat-v3.1:free"
```

## How It Works

When `disable_anthropic: true` is set, the system will:

1. **Validate at startup** - Check configuration before running any analysis
2. **Reject Anthropic backend** - Ensure `use_openrouter: true` is set
3. **Reject Anthropic models** - Block model names containing "anthropic" or "claude"
4. **Exit with clear error** - Provide helpful error messages if validation fails

## Example: Enable Anthropic Blocking

```yaml
llm:
  use_openrouter: true
  disable_anthropic: true
  model: "moonshotai/kimi-k2:free"  # ✅ OK - Free non-Anthropic model
```

This configuration will:
- Use OpenRouter API (not direct Anthropic)
- Block any Anthropic/Claude models
- Use the free Moonshot Kimi model instead

## Example: Configuration Errors

### Error 1: Anthropic Backend with Blocking Enabled
```yaml
llm:
  use_openrouter: false  # ❌ ERROR
  disable_anthropic: true
  model: "claude-sonnet-4"
```

**Error message:**
```
❌ ERROR: disable_anthropic=true but use_openrouter=false
   Cannot use Anthropic backend when Anthropic is disabled.
   Set use_openrouter: true in config.yaml
```

### Error 2: Anthropic Model with Blocking Enabled
```yaml
llm:
  use_openrouter: true
  disable_anthropic: true
  model: "anthropic/claude-sonnet-4.5"  # ❌ ERROR - Contains "claude"
```

**Error message:**
```
❌ ERROR: disable_anthropic=true but model contains Anthropic/Claude: anthropic/claude-sonnet-4.5
   Please use a non-Anthropic model like:
   - moonshotai/kimi-k2:free
   - google/gemini-2.0-flash-exp:free
   - deepseek/deepseek-chat-v3.1:free
```

## Recommended Free Models

When using `disable_anthropic: true`, use these free OpenRouter models:

| Model | Provider | Strengths |
|-------|----------|-----------|
| `moonshotai/kimi-k2:free` | Moonshot AI | Excellent for multilingual analysis, great for Hebrew |
| `google/gemini-2.0-flash-exp:free` | Google | Fast, good reasoning, multimodal |
| `deepseek/deepseek-chat-v3.1:free` | DeepSeek | Strong performance, good for technical content |
| `meta-llama/llama-3.2-3b-instruct:free` | Meta | Lightweight, fast inference |

## Affected Scripts

This validation is implemented in:

1. **`run_teacher_pipeline.py`** - Main pipeline orchestration
2. **`generate_smart_insights.py`** - Standalone smart insights generator

## Testing Your Configuration

To test if your configuration is valid:

```bash
# Test with the main pipeline (won't run analysis, just validates config)
python teacher_side/run_teacher_pipeline.py

# Test with smart insights generator
python teacher_side/generate_smart_insights.py /path/to/output
```

If `disable_anthropic: true` is set incorrectly, you'll see clear error messages before any API calls are made.

## Disabling the Feature

To allow Anthropic usage again, simply set:

```yaml
llm:
  disable_anthropic: false  # or remove this line entirely
```

Default is `false` (Anthropic allowed).