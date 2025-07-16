# Prow CI Job Crawler

Enhanced Python script to crawl Prow CI job history and extract failed jobs with their artifacts URLs.

## Features

- **Fetch from web or JSON file**: Can crawl live data from Prow CI or use pre-saved JSON files
- **Failed job detection**: Automatically filters for jobs with "FAILURE" status
- **SpyglassLink crawling**: Fetches individual SpyglassLink pages to extract real artifacts URLs
- **PR number extraction**: Extracts PR numbers from failed jobs (when available)
- **Multiple output formats**: Human-readable, JSON, or filtered outputs
- **Flexible options**: Skip artifacts extraction for faster processing

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Make the script executable:

```bash
chmod +x prow_crawler.py
```

## Usage Examples

### Basic usage - fetch from web and extract artifacts URLs
```bash
python prow_crawler.py periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
```

### Use existing JSON file (faster)
```bash
python prow_crawler.py --json-file prow.json periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
```

### Skip artifacts extraction (much faster)
```bash
python prow_crawler.py --no-artifacts periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
```

### Output only artifacts URLs
```bash
python prow_crawler.py --artifacts-only periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
```

### Output only PR numbers
```bash
python prow_crawler.py --pr-only periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
```

### JSON output format
```bash
python prow_crawler.py --json periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
```

## What it does

1. **Fetches job history**: Either from Prow CI web interface or from a local JSON file
2. **Parses job data**: Extracts the `allBuilds` JSON data containing job information
3. **Filters failed jobs**: Identifies jobs with "FAILURE" status
4. **Crawls SpyglassLinks**: For each failed job, fetches the SpyglassLink page
5. **Extracts artifacts URLs**: Parses the HTML to find the actual artifacts URL (gcsweb-ci links)
6. **Reports results**: Provides comprehensive summaries and details

## Output

The script provides:

- **Job Summary**: Total jobs, failed count, success count
- **Failed Job Details**: Build ID, start time, duration, SpyglassLink, and artifacts URL
- **PR Numbers**: Extracted from failed jobs (when available)
- **Artifacts URLs**: Real URLs extracted from SpyglassLink pages

## Artifacts URL Extraction

The script crawls each failed job's SpyglassLink (e.g., `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...`) and extracts the artifacts URL from HTML like:

```html
<a href="https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly/1935518139554992128/">Artifacts</a>
```

This gives you the actual artifacts URL that you can use to access logs and test results.

## Performance Notes

- **With artifacts extraction**: Slower as it makes HTTP requests for each failed job's SpyglassLink
- **Without artifacts extraction** (`--no-artifacts`): Much faster, only processes the main JSON data
- **Using JSON file** (`--json-file`): Fastest, skips the initial web fetch

## JSON File Format

The script expects JSON data in the same format as extracted from Prow CI's `allBuilds` variable:

```json
[
  {
    "SpyglassLink": "/view/gs/test-platform-results/logs/...",
    "ID": "1935518139554992128",
    "Started": "2025-06-19T02:01:03Z",
    "Duration": 1248000000000,
    "Result": "FAILURE",
    "Refs": null
  }
]
``` 