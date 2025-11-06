#!/usr/bin/env python3
"""
Script to list open PRs with failed or running tests in the current GitHub repository.
Requires GitHub CLI (gh) to be installed and authenticated.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import yaml


class ProwJobAnalyzer:
    """Analyzer for Prow CI job history to extract failed jobs"""

    BASE_URL = "https://prow.ci.openshift.org/job-history/gs/test-platform-results/logs/"
    PROW_BASE_URL = "https://prow.ci.openshift.org"

    def __init__(self, job_name: str):
        self.job_name = job_name
        self.job_url = urljoin(self.BASE_URL, job_name)

    def fetch_job_history(self) -> str:
        """Fetch the job history HTML page"""
        try:
            response = requests.get(self.job_url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching job history: {e}")
            sys.exit(1)

    def extract_builds_json(self, html_content: str) -> List[Dict[str, Any]]:
        """Extract and parse the allBuilds JSON from HTML"""
        try:
            all_builds_pattern = r'var allBuilds = (.+);'
            match = re.search(all_builds_pattern, html_content)

            if not match:
                print("Error: Could not find allBuilds variable in HTML")
                sys.exit(1)

            json_str = match.group(1)
            builds_data = json.loads(json_str)
            return builds_data

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error extracting builds data: {e}")
            sys.exit(1)

    def get_failed_jobs(self, builds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter builds to get only failed jobs"""
        failed_jobs = []

        for build in builds:
            if build.get('Result') == 'FAILURE':
                failed_jobs.append(build)

        return failed_jobs

    def fetch_spyglass_page(self, spyglass_link: str) -> Optional[str]:
        """Fetch the SpyglassLink page content"""
        try:
            full_url = urljoin(self.PROW_BASE_URL, spyglass_link)
            response = requests.get(full_url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching SpyglassLink {spyglass_link}: {e}")
            return None

    def extract_artifacts_url(self, html_content: str) -> Optional[str]:
        """Extract artifacts URL from SpyglassLink HTML"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            artifacts_link = soup.find('a', string='Artifacts')
            if artifacts_link and artifacts_link.get('href'):
                return artifacts_link['href']

            for link in soup.find_all('a', href=True):
                if 'gcsweb-ci' in link['href'] or 'Artifacts' in link.get_text():
                    return link['href']

            return None

        except Exception as e:
            print(f"Error parsing HTML for artifacts URL: {e}")
            return None

    def get_artifacts_urls_for_failed_jobs(self, failed_jobs: List[Dict[str, Any]]) -> Dict[str, str]:
        """Get artifacts URLs for all failed jobs"""
        artifacts_urls = {}

        for job in failed_jobs:
            build_id = job.get('ID', 'Unknown')
            spyglass_link = job.get('SpyglassLink')

            if not spyglass_link:
                continue

            html_content = self.fetch_spyglass_page(spyglass_link)
            if not html_content:
                continue

            artifacts_url = self.extract_artifacts_url(html_content)
            if artifacts_url:
                artifacts_urls[build_id] = artifacts_url

        return artifacts_urls


def fetch_prow_job_names() -> List[str]:
    """Fetch job names from the GitHub config file"""
    config_url = "https://raw.githubusercontent.com/openshift/release/refs/heads/master/ci-operator/config/openshift/microshift/.config.prowgen"

    try:
        response = requests.get(config_url, timeout=30)
        response.raise_for_status()

        config_data = yaml.safe_load(response.text)

        # Handle the actual structure: config_data is a dict with 'slack_reporter' containing a list
        if isinstance(config_data, dict) and 'slack_reporter' in config_data:
            slack_reporter_data = config_data['slack_reporter']
            if isinstance(slack_reporter_data, list) and len(slack_reporter_data) > 0:
                # Get the first (and likely only) item in the slack_reporter list
                reporter_config = slack_reporter_data[0]
                if isinstance(reporter_config, dict) and 'job_names' in reporter_config:
                    job_names = reporter_config['job_names']
                    if job_names:
                        return job_names

        print("Warning: No job names found in config file")
        return []

    except requests.RequestException as e:
        print(f"Error fetching config file: {e}")
        return []
    except yaml.YAMLError as e:
        print(f"Error parsing config YAML: {e}")
        return []
    except Exception as e:
        print(f"Error processing config data: {e}")
        return []


def construct_full_job_name(job_name: str, release_version: str = "4.21") -> str:
    """Construct full Prow job name from config job name and release version"""
    return f"periodic-ci-openshift-microshift-release-{release_version}-periodics-{job_name}"


def parse_job_start_time(start_time_str: str) -> Optional[datetime]:
    """Parse job start time from string format like '2025-10-21T00:31:08Z'"""
    try:
        # Parse ISO format timestamp
        return datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None


def is_within_time_window(start_time_str: str, hours_back: int) -> bool:
    """Check if job start time is within the specified time window"""
    if not start_time_str or start_time_str == 'Unknown':
        return False

    start_time = parse_job_start_time(start_time_str)
    if not start_time:
        return False

    # Calculate cutoff time (current time minus hours_back)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    return start_time >= cutoff_time


def get_cache_directory() -> Path:
    """Get or create cache directory"""
    cache_dir = Path.home() / ".cache" / "list_failed_prs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cache_file_path(job_name: str) -> Path:
    """Get cache file path for a specific job"""
    cache_dir = get_cache_directory()
    # Replace special characters with underscores for safe filename
    safe_job_name = re.sub(r'[^\w\-]', '_', job_name)
    return cache_dir / f"{safe_job_name}.json"


def is_cache_valid(cache_file: Path, max_age_hours: int = 1) -> bool:
    """Check if cache file exists and is not too old"""
    if not cache_file.exists():
        return False

    file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
    return file_age < timedelta(hours=max_age_hours)


def load_cached_job_data(job_name: str) -> Optional[List[Dict[str, Any]]]:
    """Load job data from cache if available and valid"""
    cache_file = get_cache_file_path(job_name)

    if not is_cache_valid(cache_file):
        return None

    try:
        with open(cache_file, 'r') as f:
            data = json.load(f)
            return data.get('builds', [])
    except (IOError, json.JSONDecodeError) as e:
        print(f"Warning: Error reading cache file {cache_file}: {e}")
        return None


def save_job_data_to_cache(job_name: str, builds_data: List[Dict[str, Any]]) -> None:
    """Save job data to cache"""
    cache_file = get_cache_file_path(job_name)

    try:
        cache_data = {
            'job_name': job_name,
            'cached_at': datetime.now().isoformat(),
            'builds': builds_data
        }

        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)

    except IOError as e:
        print(f"Warning: Error writing cache file {cache_file}: {e}")


def clear_cache_for_job(job_name: str) -> bool:
    """Clear cache for a specific job"""
    cache_file = get_cache_file_path(job_name)
    try:
        if cache_file.exists():
            cache_file.unlink()
            return True
        return False
    except IOError as e:
        print(f"Warning: Error clearing cache file {cache_file}: {e}")
        return False


def clear_all_cache() -> int:
    """Clear all cache files and return count of files removed"""
    cache_dir = get_cache_directory()
    removed_count = 0

    for cache_file in cache_dir.glob("*.json"):
        try:
            cache_file.unlink()
            removed_count += 1
        except IOError as e:
            print(f"Warning: Error removing cache file {cache_file}: {e}")

    return removed_count


def count_failed_jobs_in_window(job_name: str, hours_back: int = 12, use_cache: bool = True) -> Dict[str, Any]:
    """Count all failed jobs for a specific job name within the time window"""
    try:
        # Try to load from cache first if caching is enabled
        builds = None
        if use_cache:
            builds = load_cached_job_data(job_name)
            if builds:
                print(f"  Using cached data for {job_name}")

        # If no cached data or caching disabled, fetch from API
        if builds is None:
            analyzer = ProwJobAnalyzer(job_name)

            # Fetch job history
            html_content = analyzer.fetch_job_history()

            # Extract builds data
            builds = analyzer.extract_builds_json(html_content)

            # Save to cache if caching is enabled
            if use_cache:
                save_job_data_to_cache(job_name, builds)

        # Get failed jobs (need analyzer instance for this)
        if 'analyzer' not in locals():
            analyzer = ProwJobAnalyzer(job_name)
        failed_jobs = analyzer.get_failed_jobs(builds)

        # Filter failed jobs by time window and count them
        failed_jobs_in_window = []
        for job in failed_jobs:
            start_time = job.get('Started', 'Unknown')
            if is_within_time_window(start_time, hours_back):
                failed_jobs_in_window.append(job)

        # Get the latest failed job info if available
        latest_failed_info = None
        if failed_jobs_in_window:
            latest_failed = failed_jobs_in_window[0]
            build_id = latest_failed.get('ID', 'Unknown')
            spyglass_link = latest_failed.get('SpyglassLink', '')

            artifacts_url = ''
            if spyglass_link:
                html_content = analyzer.fetch_spyglass_page(spyglass_link)
                if html_content:
                    artifacts_url = analyzer.extract_artifacts_url(html_content) or ''

            # Get PR numbers if available
            pr_numbers = []
            refs = latest_failed.get('Refs', {})
            if refs:
                pulls = refs.get('pulls', [])
                pr_numbers = [pull.get('number') for pull in pulls if pull.get('number')]

            # Construct full URLs
            spyglass_url = urljoin(analyzer.PROW_BASE_URL, spyglass_link) if spyglass_link else ''

            latest_failed_info = {
                'build_id': build_id,
                'started': latest_failed.get('Started', 'Unknown'),
                'duration': latest_failed.get('Duration', 'Unknown'),
                'spyglass_url': spyglass_url,
                'artifacts_url': artifacts_url,
                'pr_numbers': pr_numbers,
                'result': latest_failed.get('Result', 'Unknown')
            }

        return {
            'job_name': job_name,
            'total_failures': len(failed_jobs_in_window),
            'latest_failed': latest_failed_info,
            'failure_details': [
                {
                    'build_id': job.get('ID', 'Unknown'),
                    'started': job.get('Started', 'Unknown'),
                    'duration': job.get('Duration', 'Unknown'),
                    'result': job.get('Result', 'Unknown')
                }
                for job in failed_jobs_in_window
            ]
        }

    except Exception as e:
        print(f"Warning: Failed to fetch data for job {job_name}: {e}")
        return {
            'job_name': job_name,
            'total_failures': 0,
            'latest_failed': None,
            'failure_details': []
        }


def get_latest_failed_job(job_name: str, hours_back: int = 12, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """Get the latest failed job for a specific job name"""
    try:
        # Try to load from cache first if caching is enabled
        builds = None
        if use_cache:
            builds = load_cached_job_data(job_name)
            if builds:
                print(f"  Using cached data for {job_name}")

        # If no cached data or caching disabled, fetch from API
        if builds is None:
            analyzer = ProwJobAnalyzer(job_name)

            # Fetch job history
            html_content = analyzer.fetch_job_history()

            # Extract builds data
            builds = analyzer.extract_builds_json(html_content)

            # Save to cache if caching is enabled
            if use_cache:
                save_job_data_to_cache(job_name, builds)

        # Get failed jobs (need analyzer instance for this)
        if 'analyzer' not in locals():
            analyzer = ProwJobAnalyzer(job_name)
        failed_jobs = analyzer.get_failed_jobs(builds)

        if not failed_jobs:
            return None

        # Filter failed jobs by time window and get the most recent one within the window
        recent_failed_jobs = []
        for job in failed_jobs:
            start_time = job.get('Started', 'Unknown')
            if is_within_time_window(start_time, hours_back):
                recent_failed_jobs.append(job)

        if not recent_failed_jobs:
            return None

        # Get the most recent failed job within the time window (first in the filtered list)
        latest_failed = recent_failed_jobs[0]

        # Get artifacts URL for this specific job
        build_id = latest_failed.get('ID', 'Unknown')
        spyglass_link = latest_failed.get('SpyglassLink', '')

        artifacts_url = ''
        if spyglass_link:
            html_content = analyzer.fetch_spyglass_page(spyglass_link)
            if html_content:
                artifacts_url = analyzer.extract_artifacts_url(html_content) or ''

        # Get PR numbers if available
        pr_numbers = []
        refs = latest_failed.get('Refs', {})
        if refs:
            pulls = refs.get('pulls', [])
            pr_numbers = [pull.get('number') for pull in pulls if pull.get('number')]

        # Construct full URLs
        spyglass_url = urljoin(analyzer.PROW_BASE_URL, spyglass_link) if spyglass_link else ''

        return {
            'build_id': build_id,
            'job_name': job_name,
            'started': latest_failed.get('Started', 'Unknown'),
            'duration': latest_failed.get('Duration', 'Unknown'),
            'spyglass_url': spyglass_url,
            'artifacts_url': artifacts_url,
            'pr_numbers': pr_numbers,
            'result': latest_failed.get('Result', 'Unknown')
        }

    except Exception as e:
        print(f"Warning: Failed to fetch data for job {job_name}: {e}")
        return None


def get_periodic_job_data(job_name: str, hours_back: int = 12, use_cache: bool = True) -> List[Dict[str, Any]]:
    """Get periodic job data for failed jobs (single job - legacy function)"""
    latest_failed = get_latest_failed_job(job_name, hours_back, use_cache)
    return [latest_failed] if latest_failed else []


def get_multiple_periodic_jobs_data(release_version: str = "4.21", specific_job: Optional[str] = None, hours_back: int = 12, use_cache: bool = True) -> List[Dict[str, Any]]:
    """Get periodic job data for multiple jobs from config file"""
    if specific_job:
        # Handle single specific job
        full_job_name = construct_full_job_name(specific_job, release_version)
        return get_periodic_job_data(full_job_name, hours_back, use_cache)

    # Fetch job names from config
    print("Fetching job names from config file...")
    job_names = fetch_prow_job_names()

    if not job_names:
        print("No job names found in config file")
        return []

    print(f"Found {len(job_names)} jobs in config, fetching latest failures...")

    periodic_issues = []
    failed_count = 0

    for job_name in job_names:
        full_job_name = construct_full_job_name(job_name, release_version)
        print(f"  Checking {job_name}...")

        latest_failed = get_latest_failed_job(full_job_name, hours_back, use_cache)
        if latest_failed:
            periodic_issues.append(latest_failed)
            failed_count += 1

    print(f"Found {failed_count} jobs with recent failures out of {len(job_names)} total jobs")
    return periodic_issues


def get_multiple_periodic_jobs_counts(release_version: str = "4.21", specific_job: Optional[str] = None, hours_back: int = 12, use_cache: bool = True) -> List[Dict[str, Any]]:
    """Get failure counts for multiple jobs from config file"""
    if specific_job:
        # Handle single specific job
        full_job_name = construct_full_job_name(specific_job, release_version)
        return [count_failed_jobs_in_window(full_job_name, hours_back, use_cache)]

    # Fetch job names from config
    print("Fetching job names from config file...")
    job_names = fetch_prow_job_names()

    if not job_names:
        print("No job names found in config file")
        return []

    print(f"Found {len(job_names)} jobs in config, counting failures...")

    job_counts = []
    total_failures = 0

    for job_name in job_names:
        full_job_name = construct_full_job_name(job_name, release_version)
        print(f"  Counting failures for {job_name}...")

        job_count_data = count_failed_jobs_in_window(full_job_name, hours_back, use_cache)
        job_counts.append(job_count_data)  # Include jobs with 0 failures too
        total_failures += job_count_data['total_failures']

    print(f"Found {total_failures} total failures across {len(job_counts)} jobs with failures out of {len(job_names)} total jobs")
    return job_counts


def get_multi_release_counts(release_versions: List[str], specific_job: Optional[str] = None, hours_back: int = 12, use_cache: bool = True) -> Dict[str, Any]:
    """Get failure counts for multiple releases in a matrix format"""
    # Get job names from config (same for all releases)
    job_names = fetch_prow_job_names()
    if not job_names:
        print("No job names found in config file")
        return {"job_names": [], "releases": [], "matrix": {}}

    # Filter job names if specific job is requested
    if specific_job:
        job_names = [job for job in job_names if job == specific_job]
        if not job_names:
            print(f"Job '{specific_job}' not found in config")
            return {"job_names": [], "releases": [], "matrix": {}}

    print(f"Found {len(job_names)} job(s), collecting data for {len(release_versions)} release(s)...")

    # Initialize matrix structure
    matrix = {}

    # Collect data for each release
    for release_version in release_versions:
        print(f"  Processing release {release_version}...")
        release_data = {}

        for job_name in job_names:
            full_job_name = construct_full_job_name(job_name, release_version)
            print(f"    Checking {job_name} for release {release_version}...")

            job_count_data = count_failed_jobs_in_window(full_job_name, hours_back, use_cache)
            release_data[job_name] = job_count_data

        matrix[release_version] = release_data

    return {
        "job_names": job_names,
        "releases": release_versions,
        "matrix": matrix
    }


def create_hyperlink(url: str, text: str, use_hyperlinks: bool = True) -> str:
    """Create a Gnome Terminal hyperlink with custom display text."""
    if not url:
        return text
    if not use_hyperlinks:
        return f"{text} ({url})"
    # ANSI escape sequence for hyperlinks: \033]8;;URL\033\\TEXT\033]8;;\033\\
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def run_gh_command(args: List[str], org: str = "openshift", repo: str = "microshift") -> Dict[str, Any]:
    """Run a GitHub CLI command and return parsed JSON result."""
    try:
        cmd = ["gh"] + args + ["--repo", f"{org}/{repo}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running gh command: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}", file=sys.stderr)
        sys.exit(1)


def has_failed_or_running_tests(status_checks: List[Dict[str, Any]]) -> bool:
    """Check if any status checks have failed or are running."""
    if not status_checks:
        return False

    for check in status_checks:
        state = check.get("state")
        if state in ["FAILURE", "PENDING"]:
            return True
    return False


def get_failed_checks(status_checks: List[Dict[str, Any]]) -> List[str]:
    """Get list of failed check names."""
    failed_checks = []
    for check in status_checks:
        if check.get("state") == "FAILURE":
            context = check.get("context", "Unknown")
            failed_checks.append(context)
    return failed_checks


def get_running_checks(status_checks: List[Dict[str, Any]]) -> List[str]:
    """Get list of running check names."""
    running_checks = []
    for check in status_checks:
        if check.get("state") == "PENDING":
            context = check.get("context", "Unknown")
            running_checks.append(context)
    return running_checks


def _get_filter_description(author_filter: Optional[str], subject_filter: Optional[str]) -> str:
    """Generate filter description for display."""
    filter_parts = []
    if author_filter:
        filter_parts.append(f"author: {author_filter}")
    if subject_filter:
        filter_parts.append(f"subject: {subject_filter}")

    if not filter_parts:
        return ""
    elif len(filter_parts) == 1:
        return f" {filter_parts[0]}"
    else:
        return f" {' OR '.join(filter_parts)}"


def generate_html_report(issues_data: List[Dict[str, Any]], author_filter: Optional[str], subject_filter: Optional[str] = None, org: str = "openshift", repo: str = "microshift", mode: str = "prs", job_name: Optional[str] = None, release_version: str = "4.21", hours_back: int = 12, multi_release_data: Optional[Dict[str, Any]] = None) -> str:
    """Generate HTML report for PRs with failed or running tests or periodic jobs."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if mode == "prs":
        title = f"{org}/{repo} PR Test Status Report"
        report_type = "PRs"
    elif mode == "count":
        if multi_release_data:
            releases_str = ", ".join(multi_release_data.get("releases", []))
            if job_name:
                title = f"Multi-Release Failure Count - {job_name} ({releases_str})"
            else:
                title = f"MicroShift Multi-Release Failure Count ({releases_str})"
            report_type = "Multi-Release Failure Counts"
        elif job_name:
            title = f"Failure Count Report - {job_name} (v{release_version})"
            report_type = "Failure Counts"
        else:
            title = f"MicroShift Failure Count Report (v{release_version})"
            report_type = "Failure Counts"
    else:
        if job_name:
            title = f"Prow Periodic Job Report - {job_name} (v{release_version})"
        else:
            title = f"MicroShift Periodic Jobs Report (v{release_version})"
        report_type = "Periodic Jobs"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-top: 80px;
            margin-bottom: 20px;
        }}
        .summary {{
            background: white;
            padding: 8px;
            border-radius: 8px;
            margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .pr-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .pr-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .pr-title a {{
            color: #0969da;
            text-decoration: none;
        }}
        .pr-title a:hover {{
            text-decoration: underline;
        }}
        .pr-meta {{
            color: #656d76;
            margin-bottom: 15px;
        }}
        .checks-section {{
            margin-top: 15px;
        }}
        .checks-title {{
            font-weight: bold;
            margin-bottom: 8px;
        }}
        .failed {{
            color: #d1242f;
        }}
        .running {{
            color: #bf8700;
        }}
        .check-item {{
            margin: 5px 0;
            padding-left: 20px;
        }}
        .check-item a {{
            color: inherit;
            text-decoration: none;
        }}
        .check-item a:hover {{
            text-decoration: underline;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }}
        .stat {{
            background: #f6f8fa;
            padding: 3px 10px;
            border-radius: 6px;
            border-left: 4px solid #0969da;
        }}
        .timestamp {{
            text-align: right;
            color: #656d76;
            font-size: 14px;
            margin-top: 20px;
        }}
        .count-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }}
        .count-table th,
        .count-table td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        .count-table th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: bold;
            font-size: 14px;
        }}
        .count-table tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        .count-table tr:hover {{
            background-color: #e8f4ff;
        }}
        .failure-count {{
            text-align: center;
            font-weight: bold;
        }}
        .failure-count.high {{
            color: #d1242f;
        }}
        .failure-count.medium {{
            color: #bf8700;
        }}
        .failure-count.low {{
            color: #0969da;
        }}
        .failure-count.zero {{
            color: #28a745;
        }}
        .latest-failure {{
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }}
        .job-name {{
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        {f"<small><p>{_get_filter_description(author_filter, subject_filter)}</p></small>" if mode == "prs" else f"<small><p>{'Job: ' + job_name if job_name else 'All MicroShift Jobs'} | Release: {release_version} | Time Window: {hours_back}h</p></small>"}
    </div>

    <div class="summary">
        <div class="stats">
            <div class="stat">
                <strong>{len(multi_release_data.get("job_names", [])) if multi_release_data else len(issues_data)}</strong> {report_type}
            </div>
            {f'<div class="stat"><strong>{sum(1 for item in issues_data if mode == "prs" and item["failed_checks"])}</strong> Failures</div>' if mode == "prs" else f'<div class="stat"><strong>{sum(sum(job_data.get("total_failures", 0) for job_data in release_data.values()) for release_data in multi_release_data.get("matrix", {}).values()) if multi_release_data else (sum(job.get("total_failures", 0) for job in issues_data) if mode == "count" else len(issues_data))}</strong> {"Total Failures" if mode == "count" else "Failed Jobs"}</div>'}
            {f'<div class="stat"><strong>{len([job_name for job_name in multi_release_data.get("job_names", []) if any(multi_release_data.get("matrix", {}).get(release, {}).get(job_name, {}).get("total_failures", 0) > 0 for release in multi_release_data.get("releases", []))]) if multi_release_data else len([job for job in issues_data if job.get("total_failures", 0) > 0])}</strong> Jobs with Failures</div>' if mode == "count" else ""}
        </div>
    </div>
"""

    # Skip the "no data" check for multi-release mode since we handle it separately
    if not issues_data and not multi_release_data:
        if mode == "prs":
            html += """
    <div class="pr-card">
        <h2>✅ No Issues Found</h2>
        <p>No open PRs with failed or running tests found!</p>
    </div>
"""
        else:
            html += """
    <div class="pr-card">
        <h2>✅ No Failed Jobs Found</h2>
        <p>No failed periodic jobs found!</p>
    </div>
"""
    else:
        if mode == "prs":
            for pr in issues_data:
                pr_url = f"https://github.com/{org}/{repo}/pull/{pr['number']}"
                html += f"""
    <div class="pr-card">
        <div class="pr-title">
            <a href="{pr_url}" target="_blank" rel="noopener noreferrer">PR #{pr['number']}</a> - {pr['title']}
        </div>
        <div class="pr-meta">
            <strong>Author:</strong> {pr['author']} | <strong>Branch:</strong> {pr['branch']}
        </div>
"""

                if pr['failed_check_details']:
                    html += """
        <div class="checks-section">
            <div class="checks-title failed">❌ Failed Tests:</div>
"""
                    for check in pr['failed_check_details']:
                        test_name = check['name'].replace('ci/prow/', '')
                        if check['url']:
                            html += f'            <div class="check-item"><a href="{check["url"]}" target="_blank" rel="noopener noreferrer">{test_name}</a></div>\n'
                        else:
                            html += f'            <div class="check-item">{test_name}</div>\n'
                    html += "        </div>\n"

                if pr['running_check_details']:
                    html += """
        <div class="checks-section">
            <div class="checks-title running">🔄 Running Tests:</div>
"""
                    for check in pr['running_check_details']:
                        test_name = check['name'].replace('ci/prow/', '')
                        if check['url']:
                            html += f'            <div class="check-item"><a href="{check["url"]}" target="_blank" rel="noopener noreferrer">{test_name}</a></div>\n'
                        else:
                            html += f'            <div class="check-item">{test_name}</div>\n'
                    html += "        </div>\n"

                html += "    </div>\n"

        elif mode == "count":  # count mode with HTML table
            if multi_release_data:
                # Multi-release matrix view
                job_names = multi_release_data.get("job_names", [])
                releases = multi_release_data.get("releases", [])
                matrix = multi_release_data.get("matrix", {})

                if not job_names:
                    html += """
    <div class="pr-card">
        <h2>✅ No Jobs Found</h2>
        <p>No jobs found in the configuration!</p>
    </div>
"""
                else:
                    html += """
    <table class="count-table">
        <thead>
            <tr>
                <th>Job Name</th>
"""
                    # Add release version columns
                    for release in releases:
                        html += f'                <th>v{release}</th>\n'

                    html += """            </tr>
        </thead>
        <tbody>
"""

                    # Generate rows for each job
                    for job_name in job_names:
                        html += f"""            <tr>
                <td class="job-name">{job_name}</td>
"""

                        # Add failure count for each release
                        for release in releases:
                            job_data = matrix.get(release, {}).get(job_name, {})
                            failure_count = job_data.get('total_failures', 0)

                            # Determine failure count CSS class
                            if failure_count == 0:
                                count_class = "zero"
                            elif failure_count <= 2:
                                count_class = "low"
                            elif failure_count <= 5:
                                count_class = "medium"
                            else:
                                count_class = "high"

                            # Create clickable cell with links if failures exist
                            latest_failed = job_data.get('latest_failed')
                            if latest_failed and latest_failed.get('spyglass_url'):
                                html += f'                <td class="failure-count {count_class}"><a href="{latest_failed["spyglass_url"]}" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: none;" title="Build {latest_failed.get("build_id", "Unknown")} - {latest_failed.get("started", "Unknown")}">{failure_count}</a></td>\n'
                            else:
                                html += f'                <td class="failure-count {count_class}">{failure_count}</td>\n'

                        html += "            </tr>\n"

                    html += """        </tbody>
    </table>
"""
            # Single-release count mode
            elif not issues_data:
                html += """
    <div class="pr-card">
        <h2>✅ No Failures Found</h2>
        <p>No failures found in the specified time window!</p>
    </div>
"""
            else:
                # Sort by failure count (descending)
                sorted_data = sorted(issues_data, key=lambda x: x.get('total_failures', 0), reverse=True)

                html += """
    <table class="count-table">
        <thead>
            <tr>
                <th>Job Name</th>
                <th>Failures</th>
                <th>Latest Failure</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
"""

                for job_data in sorted_data:
                    job_name = job_data['job_name']
                    short_job_name = job_name.replace(f"periodic-ci-openshift-microshift-release-{release_version}-periodics-", "")
                    failure_count = job_data.get('total_failures', 0)

                    # Determine failure count CSS class
                    if failure_count == 0:
                        count_class = "zero"
                    elif failure_count <= 2:
                        count_class = "low"
                    elif failure_count <= 5:
                        count_class = "medium"
                    else:
                        count_class = "high"

                    latest_info = "No failures"
                    latest_build_url = ""
                    if job_data.get('latest_failed'):
                        latest_failed = job_data['latest_failed']
                        latest_started = latest_failed.get('started', 'Unknown')
                        latest_build = latest_failed.get('build_id', 'Unknown')
                        latest_info = f"Build {latest_build} ({latest_started})"

                        if latest_failed.get('spyglass_url'):
                            latest_build_url = latest_failed['spyglass_url']

                    html += f"""
            <tr>
                <td class="job-name">{short_job_name}</td>
                <td class="failure-count {count_class}">{failure_count}</td>
                <td class="latest-failure">{latest_info}</td>
                <td>
"""

                    if latest_build_url:
                        html += f'                    <a href="{latest_build_url}" target="_blank" rel="noopener noreferrer" style="color: #0969da; text-decoration: none;">🔍 View Latest</a>'

                    if job_data.get('latest_failed') and job_data['latest_failed'].get('artifacts_url'):
                        artifacts_url = job_data['latest_failed']['artifacts_url']
                        if latest_build_url:
                            html += " | "
                        html += f'                    <a href="{artifacts_url}" target="_blank" rel="noopener noreferrer" style="color: #0969da; text-decoration: none;">📁 Artifacts</a>'

                    html += """
                </td>
            </tr>
"""

                html += """
        </tbody>
    </table>
"""

        else:  # periodics mode
            for job in issues_data:
                # Extract short job name from full job name
                full_job_name = job['job_name']
                short_job_name = full_job_name.replace(f"periodic-ci-openshift-microshift-release-{release_version}-periodics-", "")

                html += f"""
    <div class="pr-card">
        <div class="pr-title">
            {short_job_name} (Build {job['build_id']})
        </div>
        <div class="pr-meta">
            <strong>Started:</strong> {job['started']} | <strong>Duration:</strong> {job['duration']} | <strong>Result:</strong> {job['result']}
        </div>
"""

                if job['spyglass_url'] or job['artifacts_url']:
                    html += """
        <div class="checks-section">
            <div class="checks-title">🔗 Links:</div>
"""
                    if job['spyglass_url']:
                        html += f'            <div class="check-item"><a href="{job["spyglass_url"]}" target="_blank" rel="noopener noreferrer">🔍 Spyglass</a></div>\n'
                    if job['artifacts_url']:
                        html += f'            <div class="check-item"><a href="{job["artifacts_url"]}" target="_blank" rel="noopener noreferrer">📁 Artifacts</a></div>\n'
                    html += "        </div>\n"

                if job['pr_numbers']:
                    html += f"""
        <div class="checks-section">
            <div class="checks-title">🔗 Related PRs:</div>
            <div class="check-item">{', '.join(map(str, job['pr_numbers']))}</div>
        </div>
"""

                html += "    </div>\n"

    html += f"""
    <div class="timestamp">
        Report generated on {timestamp}
    </div>
</body>
</html>"""

    return html


class PRReportHandler(BaseHTTPRequestHandler):
    """HTTP request handler for serving PR reports."""

    def __init__(self, *args, get_report_func=None, **kwargs):
        self.get_report_func = get_report_func
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        try:
            # Enable CORS for the Chrome extension
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

            # Generate fresh report
            if self.get_report_func:
                html_content = self.get_report_func()
                self.wfile.write(html_content.encode('utf-8'))
            else:
                self.wfile.write(b"<html><body><h1>Error: No report function available</h1></body></html>")

        except Exception as e:
            self.send_error(500, f"Internal Server Error: {str(e)}")

    def log_message(self, format, *args):
        """Override to reduce logging noise."""
        pass


def create_server_handler(get_report_func):
    """Create a request handler with the report function bound."""
    def handler(*args, **kwargs):
        return PRReportHandler(*args, get_report_func=get_report_func, **kwargs)
    return handler


def serve_reports(port, get_report_func):
    """Serve PR reports via HTTP server."""
    handler = create_server_handler(get_report_func)
    httpd = HTTPServer(('localhost', port), handler)

    print(f"🚀 PR Report server starting on http://localhost:{port}")
    print("📊 Reports will auto-refresh every 30 seconds")
    print("🔌 Chrome extension can now connect to this server")
    print("Press Ctrl+C to stop the server\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        httpd.shutdown()


def matches_subject_filter(title: str, subject_pattern: str) -> bool:
    """Check if PR title matches the subject regex pattern."""
    try:
        return bool(re.search(subject_pattern, title, re.IGNORECASE))
    except re.error:
        # If regex is invalid, fall back to simple case-insensitive substring search
        return subject_pattern.lower() in title.lower()


def get_pr_report_data(author_filter, subject_filter=None, org="openshift", repo="microshift"):
    """Get PR report data without printing to console."""
    # Build gh command arguments - fetch all open PRs first
    gh_args = ["pr", "list", "--state", "open"]

    # If we only have author filter (no subject), apply it directly to gh command
    if author_filter and not subject_filter:
        gh_args.extend(["--author", author_filter])

    gh_args.extend(["--json", "number,title,headRefName,statusCheckRollup,author"])

    # Fetch open PRs with status check information
    prs = run_gh_command(gh_args, org, repo)

    if not prs:
        return []

    prs_with_issues = []

    for pr in prs:
        # Apply filtering logic: if both author and subject filters are provided, use OR logic
        should_include = True

        if author_filter or subject_filter:
            should_include = False

            # Check author match
            if author_filter:
                pr_author = pr["author"]["login"] if pr.get("author") else "Unknown"
                if pr_author == author_filter:
                    should_include = True

            # Check subject match (OR logic)
            if subject_filter and not should_include:
                if matches_subject_filter(pr["title"], subject_filter):
                    should_include = True

        # Skip PR if it doesn't match our filters
        if not should_include:
            continue

        status_checks = pr.get("statusCheckRollup", [])
        if has_failed_or_running_tests(status_checks):
            failed_checks = get_failed_checks(status_checks)
            running_checks = get_running_checks(status_checks)

            # Create check details with URLs
            failed_check_details = []
            running_check_details = []

            for check in status_checks:
                context = check.get("context", "Unknown")
                target_url = check.get("targetUrl", "")
                state = check.get("state")

                if state == "FAILURE":
                    failed_check_details.append({"name": context, "url": target_url})
                elif state == "PENDING":
                    running_check_details.append({"name": context, "url": target_url})

            prs_with_issues.append({
                "number": pr["number"],
                "title": pr["title"],
                "branch": pr["headRefName"],
                "author": pr["author"]["login"] if pr.get("author") else "Unknown",
                "failed_checks": failed_checks,
                "running_checks": running_checks,
                "failed_check_details": failed_check_details,
                "running_check_details": running_check_details
            })

    return prs_with_issues


def main():
    """Main function to list PRs with failed tests."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="List open PRs with failed or running tests in the current GitHub repository"
    )
    parser.add_argument(
        "--author", "-a",
        default="eslutsky",
        help="Filter PRs by author (default: eslutsky). Use 'all' to show all authors."
    )
    parser.add_argument(
        "--no-hyperlinks",
        action="store_true",
        help="Disable terminal hyperlinks (show full URLs instead)"
    )
    parser.add_argument(
        "--html", "-H",
        metavar="FILE",
        help="Generate HTML report and save to specified file (e.g., report.html)"
    )
    parser.add_argument(
        "--serve", "-s",
        action="store_true",
        help="Start HTTP server to serve live reports for Chrome extension"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port for HTTP server (default: 8080)"
    )
    parser.add_argument(
        "--subject", "-S",
        help="Filter PRs by subject/title using regex pattern. When used with --author, uses OR logic (either author OR subject match)"
    )
    parser.add_argument(
        "--org", "-o",
        default="openshift",
        help="GitHub organization (default: openshift)"
    )
    parser.add_argument(
        "--repo", "-r",
        default="microshift",
        help="GitHub repository (default: microshift)"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["prs", "periodics", "refresh", "count"],
        default="prs",
        help="Mode: 'prs' for GitHub PRs (default), 'periodics' for Prow periodic jobs, 'refresh' to update cached data, or 'count' to count total failures in time window"
    )
    parser.add_argument(
        "--job-name", "-j",
        help="Specific Prow job name (optional for periodics mode - if not provided, all jobs from config will be used)"
    )
    parser.add_argument(
        "--release-version", "-rv",
        default="4.21",
        help="MicroShift release version for constructing periodic job names (default: 4.21)"
    )
    parser.add_argument(
        "--multi-release", "-mr",
        help="Comma-separated list of release versions for multi-release dashboard (e.g., '4.19,4.20,4.21'). When used, creates a matrix view with releases as columns."
    )
    parser.add_argument(
        "--hours-back", "-hb",
        type=int,
        default=12,
        help="Show periodic jobs from the last N hours (default: 12 hours)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching, always fetch fresh data from APIs"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all cached data before running"
    )
    args = parser.parse_args()

    # No validation needed since job-name is now optional for periodics mode

    # Handle cache clearing
    if args.clear_cache:
        cleared_count = clear_all_cache()
        print(f"Cleared {cleared_count} cache files")

    # Handle refresh mode
    if args.mode == "refresh":
        print("Refreshing cached data...")
        if args.job_name:
            # Refresh specific job
            full_job_name = construct_full_job_name(args.job_name, args.release_version)
            print(f"Refreshing cache for: {args.job_name}")
            clear_cache_for_job(full_job_name)
            get_latest_failed_job(full_job_name, args.hours_back, use_cache=True)
            print("✅ Cache refreshed for specific job")
        else:
            # Refresh all jobs
            job_names = fetch_prow_job_names()
            if job_names:
                print(f"Refreshing cache for {len(job_names)} jobs...")
                refreshed_count = 0
                for job_name in job_names:
                    full_job_name = construct_full_job_name(job_name, args.release_version)
                    print(f"  Refreshing {job_name}...")
                    clear_cache_for_job(full_job_name)
                    result = get_latest_failed_job(full_job_name, args.hours_back, use_cache=True)
                    if result:
                        refreshed_count += 1
                print(f"✅ Cache refreshed for {len(job_names)} jobs ({refreshed_count} had data)")
            else:
                print("❌ No job names found to refresh")
        return

    author_filter = args.author
    if author_filter and author_filter.lower() == "all":
        author_filter = None

    subject_filter = args.subject
    use_hyperlinks = not args.no_hyperlinks
    use_cache = not args.no_cache

    # Handle serve mode
    if args.serve:
        def get_live_report():
            if args.mode == "prs":
                issues_data = get_pr_report_data(author_filter, subject_filter, args.org, args.repo)
                return generate_html_report(issues_data, author_filter, subject_filter, args.org, args.repo, mode="prs")
            elif args.mode == "count":
                if args.multi_release:
                    # Parse multi-release versions
                    release_versions = [v.strip() for v in args.multi_release.split(',')]
                    multi_release_data = get_multi_release_counts(release_versions, args.job_name, args.hours_back, use_cache)
                    return generate_html_report([], None, None, args.org, args.repo, mode="count", job_name=args.job_name, release_version=args.release_version, hours_back=args.hours_back, multi_release_data=multi_release_data)
                else:
                    issues_data = get_multiple_periodic_jobs_counts(args.release_version, args.job_name, args.hours_back, use_cache)
                    return generate_html_report(issues_data, None, None, args.org, args.repo, mode="count", job_name=args.job_name, release_version=args.release_version, hours_back=args.hours_back)
            else:  # periodics mode
                issues_data = get_multiple_periodic_jobs_data(args.release_version, args.job_name, args.hours_back, use_cache)
                return generate_html_report(issues_data, None, None, args.org, args.repo, mode="periodics", job_name=args.job_name, release_version=args.release_version, hours_back=args.hours_back)

        serve_reports(args.port, get_live_report)
        return

    # Handle count mode for non-serve cases
    if args.mode == "count":
        if args.multi_release:
            # Parse multi-release versions
            release_versions = [v.strip() for v in args.multi_release.split(',')]
            releases_str = ", ".join(release_versions)

            if args.job_name:
                print(f"Multi-release counting for: {args.job_name} (releases {releases_str}, last {args.hours_back}h)...")
            else:
                print(f"Multi-release counting for all MicroShift jobs (releases {releases_str}, last {args.hours_back}h)...")

            # Get multi-release data
            multi_release_data = get_multi_release_counts(release_versions, args.job_name, args.hours_back, use_cache)
            job_names = multi_release_data.get("job_names", [])
            matrix = multi_release_data.get("matrix", {})

            if not job_names:
                print("✅ No jobs found in the configuration!")
            else:
                # Create terminal matrix display
                print(f"\n📊 Multi-Release Failure Matrix:")

                # Header
                header = f"{'Job Name':<30}"
                for release in release_versions:
                    header += f" | v{release:>6}"
                print(header)
                print("-" * len(header))

                # Rows
                for job_name in job_names:
                    row = f"{job_name:<30}"
                    for release in release_versions:
                        job_data = matrix.get(release, {}).get(job_name, {})
                        failure_count = job_data.get('total_failures', 0)
                        row += f" | {failure_count:>6}"
                    print(row)

            # Set issues_data for potential HTML generation later
            issues_data = []
        else:
            if args.job_name:
                print(f"Counting failures for: {args.job_name} (release {args.release_version}, last {args.hours_back}h)...")
            else:
                print(f"Counting failures for all MicroShift jobs (release {args.release_version}, last {args.hours_back}h)...")

            # Get count data
            count_data = get_multiple_periodic_jobs_counts(args.release_version, args.job_name, args.hours_back, use_cache)

            # Display count results
            total_failures = sum(job['total_failures'] for job in count_data)

            if total_failures == 0:
                if args.job_name:
                    print(f"✅ No failures found for {args.job_name} in the last {args.hours_back} hours!")
                else:
                    print(f"✅ No failures found for any MicroShift jobs in the last {args.hours_back} hours!")
            else:
                if args.job_name:
                    print(f"\n📊 Failure count for {args.job_name} in the last {args.hours_back} hours:")
                else:
                    print(f"\n📊 Failure counts for MicroShift jobs (release {args.release_version}) in the last {args.hours_back} hours:")

                # Sort by failure count (descending)
                count_data.sort(key=lambda x: x['total_failures'], reverse=True)

                print("\nJob Name | Failures | Latest Failure")
                print("-" * 70)

                for job_data in count_data:
                    short_job_name = job_data['job_name'].replace(f"periodic-ci-openshift-microshift-release-{args.release_version}-periodics-", "")
                    failure_count = job_data['total_failures']

                    latest_info = "No failures"
                    if job_data['latest_failed']:
                        latest_started = job_data['latest_failed']['started']
                        latest_build = job_data['latest_failed']['build_id']
                        latest_info = f"Build {latest_build} ({latest_started})"

                    print(f"{short_job_name:<30} | {failure_count:>8} | {latest_info}")

                jobs_with_failures = len([job for job in count_data if job['total_failures'] > 0])
                print(f"\nSummary: {total_failures} total failures across {jobs_with_failures} jobs with failures (out of {len(count_data)} total jobs)")

            # Set issues_data for potential HTML generation later
            issues_data = count_data

    # Print information based on mode
    elif args.mode == "prs":
        # Print filter information
        filter_parts = []
        if author_filter:
            filter_parts.append(f"author: {author_filter}")
        if subject_filter:
            filter_parts.append(f"subject matching: {subject_filter}")

        if filter_parts:
            filter_desc = " OR ".join(filter_parts) if len(filter_parts) > 1 else filter_parts[0]
            print(f"Fetching open PRs with failed or running tests for {filter_desc}...")
        else:
            print("Fetching open PRs with failed or running tests for all authors...")

        # Get PR data
        issues_data = get_pr_report_data(author_filter, subject_filter, args.org, args.repo)
    else:  # periodics mode
        if args.job_name:
            print(f"Fetching failed periodic jobs for: {args.job_name} (release {args.release_version}, last {args.hours_back}h)...")
        else:
            print(f"Fetching failed periodic jobs for all MicroShift jobs (release {args.release_version}, last {args.hours_back}h)...")
        # Get periodic job data
        issues_data = get_multiple_periodic_jobs_data(args.release_version, args.job_name, args.hours_back, use_cache)

    # Generate HTML report if requested
    if args.html:
        if args.mode == "prs":
            html_content = generate_html_report(issues_data, author_filter, subject_filter, args.org, args.repo, mode="prs")
        elif args.mode == "count":
            if args.multi_release:
                # Parse multi-release versions and get data
                release_versions = [v.strip() for v in args.multi_release.split(',')]
                multi_release_data = get_multi_release_counts(release_versions, args.job_name, args.hours_back, use_cache)
                html_content = generate_html_report([], None, None, args.org, args.repo, mode="count", job_name=args.job_name, release_version=args.release_version, hours_back=args.hours_back, multi_release_data=multi_release_data)
            else:
                html_content = generate_html_report(issues_data, None, None, args.org, args.repo, mode="count", job_name=args.job_name, release_version=args.release_version, hours_back=args.hours_back)
        else:
            html_content = generate_html_report(issues_data, None, None, args.org, args.repo, mode="periodics", job_name=args.job_name, release_version=args.release_version, hours_back=args.hours_back)

        try:
            with open(args.html, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"HTML report generated: {args.html}")
        except IOError as e:
            print(f"Error writing HTML report: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Terminal output (default behavior)
    # Skip terminal output for multi-release mode since we already displayed the matrix
    if args.mode == "count" and args.multi_release:
        return

    if not issues_data:
        if args.mode == "prs":
            filter_desc = _get_filter_description(author_filter, subject_filter)
            if filter_desc:
                print(f"✅ No open PRs with failed or running tests found{filter_desc}!")
            else:
                print("✅ No open PRs with failed or running tests found!")
        else:
            if args.job_name:
                print(f"✅ No failed periodic jobs found for {args.job_name} in the last {args.hours_back} hours!")
            else:
                print(f"✅ No failed periodic jobs found for any MicroShift jobs in the last {args.hours_back} hours!")
        return

    if args.mode == "prs":
        filter_desc = _get_filter_description(author_filter, subject_filter)
        if filter_desc:
            print(f"\n🔍 Found {len(issues_data)} open PR(s) with failed or running tests{filter_desc}:\n")
        else:
            print(f"\n🔍 Found {len(issues_data)} open PR(s) with failed or running tests:\n")

        for pr in issues_data:
            pr_url = f"https://github.com/{args.org}/{args.repo}/pull/{pr['number']}"
            pr_link = create_hyperlink(pr_url, f"PR #{pr['number']}", use_hyperlinks)
            print(f"**{pr_link}** - {pr['title']}")
            print(f"  Author: {pr['author']}")
            print(f"  Branch: {pr['branch']}")

            if pr['failed_check_details']:
                print(f"  ❌ Failed tests:")
                for check in pr['failed_check_details']:
                    if check['url']:
                        test_name = check['name'].replace('ci/prow/', '')
                        test_link = create_hyperlink(check['url'], test_name, use_hyperlinks)
                        print(f"    - {test_link}")
                    else:
                        print(f"    - {check['name']}")

            if pr['running_check_details']:
                print(f"  🔄 Running tests:")
                for check in pr['running_check_details']:
                    if check['url']:
                        test_name = check['name'].replace('ci/prow/', '')
                        test_link = create_hyperlink(check['url'], test_name, use_hyperlinks)
                        print(f"    - {test_link}")
                    else:
                        print(f"    - {check['name']}")

            print()

        failed_count = sum(1 for pr in issues_data if pr['failed_checks'])
        running_count = sum(1 for pr in issues_data if pr['running_checks'])

        print(f"Summary: {len(issues_data)} total PRs ({failed_count} with failures, {running_count} with running tests)")

    else:  # periodics mode
        if args.job_name:
            print(f"\n🔍 Found {len(issues_data)} failed periodic job(s) for {args.job_name} in the last {args.hours_back} hours:\n")
        else:
            print(f"\n🔍 Found {len(issues_data)} failed periodic job(s) from MicroShift jobs (release {args.release_version}) in the last {args.hours_back} hours:\n")

        for job in issues_data:
            # Extract short job name from full job name
            full_job_name = job['job_name']
            short_job_name = full_job_name.replace(f"periodic-ci-openshift-microshift-release-{args.release_version}-periodics-", "")

            print(f"**{short_job_name}** (Build {job['build_id']})")
            print(f"  Started: {job['started']}")
            print(f"  Duration: {job['duration']}")
            print(f"  Result: {job['result']}")

            if job['spyglass_url']:
                spyglass_link = create_hyperlink(job['spyglass_url'], "Spyglass", use_hyperlinks)
                print(f"  🔍 {spyglass_link}")

            if job['artifacts_url']:
                artifacts_link = create_hyperlink(job['artifacts_url'], "Artifacts", use_hyperlinks)
                print(f"  📁 {artifacts_link}")

            if job['pr_numbers']:
                print(f"  🔗 Related PRs: {', '.join(map(str, job['pr_numbers']))}")

            print()

        print(f"Summary: {len(issues_data)} failed periodic jobs")


if __name__ == "__main__":
    main()
