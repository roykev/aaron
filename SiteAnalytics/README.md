# Site Analytics - Mixpanel Export Tool

A Python tool for extracting and analyzing site analytics from Mixpanel with support for filtering and blacklist management.

## Features

- Export events from Mixpanel using their Raw Data Export API
- Bypass the 100-entry limit in the Mixpanel web interface
- YAML-based configuration for easy management
- Blacklist support to exclude demo accounts and test data
- Support for large date ranges with chunked exports
- Automatic filtering of blacklisted user IDs and course IDs

## Installation

Install the required dependencies:

```bash
pip install requests pandas pyyaml
```

## Configuration

### API Secret Configuration

The tool supports multiple ways to provide your Mixpanel API Secret (in order of precedence):

1. **Command-line argument**: `--secret YOUR_SECRET`
2. **Environment variable**: `export MIXPANEL_SECRET="your_secret"` (current session)
3. **~/.bashrc file**: `export MIXPANEL_SECRET="your_secret"` (persistent)
4. **Config file**: Set in `config.yaml` under `mixpanel.api_secret`

**Recommended**: Add to your `~/.bashrc` file:
```bash
echo 'export MIXPANEL_SECRET="your_actual_secret_here"' >> ~/.bashrc
source ~/.bashrc
```

### Using YAML Configuration (Recommended)

1. Copy and edit the `config.yaml` file:

```yaml
# Mixpanel API credentials
mixpanel:
  api_secret: "YOUR_API_SECRET_HERE"  # Optional if using ~/.bashrc
  project_id: null  # Optional: Your Mixpanel Project ID

# Export settings
export:
  from_date: "2025-12-01"
  to_date: "2025-12-25"
  output_file: "mixpanel_export.csv"  # Used if output_dir is not set
  output_dir: "/path/to/export/directory"  # Auto-generates filename: from_to_export.csv
  chunk_days: null  # Set to a number (e.g., 7) to export in chunks
  event: null  # Optional: Filter by specific event name

# Blacklist configuration
blacklist:
  user_ids:
    - "demo_user"
    - "test_user_123"

  course_ids:
    - "demo_course"
    - "test_course_456"
```

2. Get your Mixpanel API Secret:
   - Log into Mixpanel
   - Go to Project Settings > Project Details
   - Copy your API Secret

3. Add IDs to blacklist:
   - Add any demo user IDs to `blacklist.user_ids`
   - Add any test course IDs to `blacklist.course_ids`

## Usage

### Using Configuration File

```bash
# Use default config.yaml
python mixpanel_export.py --config config.yaml

# Or simply (will auto-detect config.yaml)
python mixpanel_export.py
```

### Using Command-Line Arguments

```bash
# Basic export
python mixpanel_export.py --secret YOUR_API_SECRET --from 2025-12-01 --to 2025-12-25

# Export specific event type
python mixpanel_export.py --secret YOUR_API_SECRET --from 2025-12-01 --to 2025-12-25 --event "Login"

# Export large date range in chunks
python mixpanel_export.py --secret YOUR_API_SECRET --from 2025-01-01 --to 2025-12-31 --chunk-days 7

# Specify output file
python mixpanel_export.py --secret YOUR_API_SECRET --from 2025-12-01 --to 2025-12-25 -o my_export.csv
```

### Command-Line Options

- `--config PATH`: Path to YAML configuration file (default: config.yaml)
- `--secret SECRET`: Mixpanel API Secret
- `--from DATE`: Start date in YYYY-MM-DD format
- `--to DATE`: End date in YYYY-MM-DD format
- `--event NAME`: Filter by specific event name (optional)
- `-o FILE`, `--output FILE`: Output CSV filename
- `--chunk-days N`: Export in chunks of N days (useful for large date ranges)
- `--project-id ID`: Mixpanel Project ID (optional)

**Note:** Command-line arguments take precedence over configuration file values.

## Blacklist Filtering

The tool automatically filters out events based on the blacklists defined in `config.yaml`:

- **User ID Blacklist**: Excludes events from specified user IDs (checks both `distinct_id` and `user_id` properties)
- **Course ID Blacklist**: Excludes events from specified course IDs

This is useful for:
- Removing demo account data
- Filtering out test users
- Excluding internal development/testing events

## Output

The tool exports data to a CSV file with:
- Event name
- Timestamp (both Unix timestamp and readable datetime)
- User/distinct ID
- All event properties (nested objects are JSON-encoded)

## Examples

### Example 1: Simple Export with Config
```bash
python mixpanel_export.py
```

### Example 2: Override Dates from Config
```bash
python mixpanel_export.py --from 2025-12-01 --to 2025-12-31
```

### Example 3: Large Export with Chunks
```bash
python mixpanel_export.py --chunk-days 7
```

## Project Structure

```
SiteAnalytics/
├── mixpanel_export.py   # Main export script
├── config.yaml          # Configuration file
└── README.md           # This file
```

## Future Enhancements

Potential additions for analytics:
- Data visualization dashboards
- User behavior analysis
- Course engagement metrics
- Custom report generation
- Integration with other analytics platforms

## Troubleshooting

**Error: Configuration file not found**
- Make sure `config.yaml` exists in the same directory as the script
- Or specify a custom path with `--config`

**Error: API secret is required**
- Add your API secret to `config.yaml` under `mixpanel.api_secret`
- Or provide it via `--secret` command-line argument

**No events exported**
- Check your date range
- Verify your API secret is correct
- Ensure your blacklist isn't filtering out all events

## License

This is a utility tool for internal use.