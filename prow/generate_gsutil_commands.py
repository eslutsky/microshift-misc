#!/usr/bin/env python3
"""
Simple script to generate gsutil commands for downloading failed job artifacts
"""

import argparse
import json
import sys
from pathlib import Path

def convert_artifacts_url_to_gcs_path(artifacts_url: str) -> str:
    """Convert gcsweb artifacts URL to GCS path for gsutil"""
    if 'gcsweb-ci' in artifacts_url and '/gcs/' in artifacts_url:
        gcs_path_part = artifacts_url.split('/gcs/', 1)[1]
        gcs_path_part = gcs_path_part.rstrip('/')
        return f"gs://{gcs_path_part}"
    return None

def generate_gsutil_commands(json_file: str, job_name: str):
    """Generate gsutil commands from prow.json file"""
    try:
        with open(json_file, 'r') as f:
            builds = json.load(f)
    except Exception as e:
        print(f"Error loading {json_file}: {e}")
        sys.exit(1)
    
    # Find failed jobs
    failed_jobs = [build for build in builds if build.get('Result') == 'FAILURE']
    
    if not failed_jobs:
        print("No failed jobs found")
        return
    
    print("#!/bin/bash")
    print("# Generated gsutil commands for downloading failed job artifacts")
    print(f"# Job: {job_name}")
    print(f"# Total failed jobs: {len(failed_jobs)}")
    print()
    
    for job in failed_jobs:
        build_id = job.get('ID', 'Unknown')
        started = job.get('Started', 'Unknown')
        
        # Construct GCS path
        gcs_path = f"gs://test-platform-results/logs/{job_name}/{build_id}"
        local_dir = f"artifacts/job_{build_id}"
        
        print(f"# Build {build_id} - Started: {started}")
        print(f"mkdir -p {local_dir}")
        print(f"gsutil -m cp -r {gcs_path} {local_dir}/")
        print()

def main():
    parser = argparse.ArgumentParser(
        description="Generate gsutil commands for downloading failed job artifacts"
    )
    
    parser.add_argument(
        'json_file',
        help='Path to prow.json file'
    )
    
    parser.add_argument(
        'job_name',
        help='The Prow CI job name'
    )
    
    args = parser.parse_args()
    
    generate_gsutil_commands(args.json_file, args.job_name)

if __name__ == "__main__":
    main() 