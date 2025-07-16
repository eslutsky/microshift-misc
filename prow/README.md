# Prow CI Job Crawler

Enhanced Python script to crawl Prow CI job history, extract failed jobs, and download their artifacts using gsutil.

## Features

- **Fetch from web or JSON file**: Can crawl live data from Prow CI or use pre-saved JSON files
- **Failed job detection**: Automatically filters for jobs with "FAILURE" status
- **SpyglassLink crawling**: Fetches individual SpyglassLink pages to extract real artifacts URLs
- **Artifacts downloading**: Download artifacts using gsutil for automated analysis
- **PR number extraction**: Extracts PR numbers from failed jobs (when available)
- **Multiple output formats**: Human-readable, JSON, artifacts-only, or PR-only outputs
- **Flexible options**: Skip artifacts extraction for faster processing, dry-run mode
- **GCS path conversion**: Converts artifacts URLs to gsutil-compatible GCS paths
- **Local directory management**: Automatically creates organized directory structure for downloads

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Make sure you have `gsutil` installed and configured for downloading artifacts:

```bash
# Install gsutil (if not already installed)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Or use your system package manager
# Ubuntu/Debian: apt install google-cloud-sdk
# RHEL/CentOS: yum install google-cloud-sdk
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

### Download artifacts for all failed jobs
```bash
python prow_crawler.py --download-artifacts periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
```

### Download artifacts with custom directory
```bash
python prow_crawler.py --download-artifacts --artifacts-dir my_artifacts periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
```

### Dry run - show gsutil commands without executing
```bash
python prow_crawler.py --download-artifacts --dry-run periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
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
6. **Downloads artifacts** (optional): Uses gsutil to download all artifacts locally
7. **Reports results**: Provides comprehensive summaries and download statistics

## Artifacts Downloading with gsutil

The script can automatically download artifacts for failed jobs using `gsutil`:

### How it works:
1. **URL Conversion**: Converts gcsweb URLs to GCS paths
   - From: `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/job-name/1234567890/`
   - To: `gs://test-platform-results/logs/job-name/1234567890`

2. **Directory Creation**: Creates organized local directory structure:
   ```
   artifacts/
   ├── job_1234567890/
   ├── job_1234567891/
   └── job_1234567892/
   ```

3. **gsutil Execution**: Runs `gsutil -m cp -r` commands to download recursively

### Download Options:
- `--download-artifacts`: Download artifacts for all failed jobs
- `--artifacts-dir DIR`: Specify custom base directory (default: `artifacts`)
- `--dry-run`: Show gsutil commands without executing them
- Timeout: 5-minute timeout per download to prevent hanging

### Example gsutil commands generated:
```bash
gsutil -m cp -r gs://test-platform-results/logs/periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly/1234567890 artifacts/job_1234567890/
```

## Output

The script provides:

- **Job Summary**: Total jobs, failed count, success count
- **Failed Job Details**: Build ID, start time, duration, SpyglassLink, and artifacts URL
- **PR Numbers**: Extracted from failed jobs (when available)
- **Artifacts URLs**: Real URLs extracted from SpyglassLink pages
- **GCS Paths**: gsutil-compatible paths for manual downloads
- **Download Summary**: Success/failure statistics for artifact downloads

## Artifacts URL Extraction

The script crawls each failed job's SpyglassLink (e.g., `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...`) and extracts the artifacts URL from HTML like:

```html
<a href="https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly/1935518139554992128/">Artifacts</a>
```

This gives you the actual artifacts URL that you can use to access logs and test results.


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
    "Refs": {
      "pulls": [
        {"number": 1234}
      ]
    }
  }
]
```

## Prerequisites

- Python 3.6+
- `requests` library
- `beautifulsoup4` library
- `gsutil` (Google Cloud SDK) for downloading artifacts
- Internet access to Prow CI and GCS
- GCS authentication configured for downloading artifacts 