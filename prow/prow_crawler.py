#!/usr/bin/env python3
"""
Prow CI Job Crawler - Extracts failed jobs from OpenShift Prow CI
"""

import argparse
import json
import os
import re
import requests
import subprocess
import sys
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup


class ProwJobCrawler:
    """Crawler for Prow CI job history to extract failed jobs"""
    
    BASE_URL = "https://prow.ci.openshift.org/job-history/gs/test-platform-results/logs/"
    PROW_BASE_URL = "https://prow.ci.openshift.org"
    
    def __init__(self, job_name: str):
        self.job_name = job_name
        self.job_url = urljoin(self.BASE_URL, job_name)
    
    def load_builds_from_file(self, json_file_path: str) -> List[Dict[str, Any]]:
        """Load builds data from a JSON file"""
        try:
            with open(json_file_path, 'r') as f:
                builds_data = json.load(f)
            print(f"Loaded {len(builds_data)} builds from {json_file_path}")
            return builds_data
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading JSON file {json_file_path}: {e}")
            sys.exit(1)
        
    def fetch_job_history(self) -> str:
        """Fetch the job history HTML page"""
        try:
            print(f"Fetching job history from: {self.job_url}")
            response = requests.get(self.job_url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching job history: {e}")
            sys.exit(1)
    
    def extract_builds_json(self, html_content: str) -> List[Dict[str, Any]]:
        """Extract and parse the allBuilds JSON from HTML"""
        try:
            # Find the line containing allBuilds variable
            all_builds_pattern = r'var allBuilds = (.+);'
            match = re.search(all_builds_pattern, html_content)
            
            if not match:
                print("Error: Could not find allBuilds variable in HTML")
                sys.exit(1)
            
            # Extract the JSON string
            json_str = match.group(1)
            
            # Parse JSON
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
    
    def extract_pr_numbers(self, failed_jobs: List[Dict[str, Any]]) -> List[int]:
        """Extract PR numbers from failed jobs"""
        pr_numbers = []
        
        for job in failed_jobs:
            refs = job.get('Refs', {})
            if refs:
                pulls = refs.get('pulls', [])
                
                for pull in pulls:
                    pr_number = pull.get('number')
                    if pr_number:
                        pr_numbers.append(pr_number)
        
        return pr_numbers
    
    def fetch_spyglass_page(self, spyglass_link: str) -> Optional[str]:
        """Fetch the SpyglassLink page content"""
        try:
            full_url = urljoin(self.PROW_BASE_URL, spyglass_link)
            print(f"Fetching SpyglassLink: {full_url}")
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
            
            # Find the <a> tag with text "Artifacts"
            artifacts_link = soup.find('a', string='Artifacts')
            if artifacts_link and artifacts_link.get('href'):
                return artifacts_link['href']
            
            # Alternative: look for links containing "gcsweb-ci" or "Artifacts"
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
                print(f"No SpyglassLink found for build {build_id}")
                continue
            
            # Fetch the SpyglassLink page
            html_content = self.fetch_spyglass_page(spyglass_link)
            if not html_content:
                continue
            
            # Extract artifacts URL
            artifacts_url = self.extract_artifacts_url(html_content)
            if artifacts_url:
                artifacts_urls[build_id] = artifacts_url
                print(f"Found artifacts URL for build {build_id}: {artifacts_url}")
            else:
                print(f"No artifacts URL found for build {build_id}")
        
        return artifacts_urls
    
    def convert_artifacts_url_to_gcs_path(self, artifacts_url: str) -> Optional[str]:
        """Convert gcsweb artifacts URL to GCS path for gsutil"""
        try:
            # Pattern: https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/...
            # Convert to: gs://test-platform-results/logs/...
            if 'gcsweb-ci' in artifacts_url and '/gcs/' in artifacts_url:
                # Extract the part after /gcs/
                gcs_path_part = artifacts_url.split('/gcs/', 1)[1]
                # Remove trailing slash if present
                gcs_path_part = gcs_path_part.rstrip('/')
                return f"gs://{gcs_path_part}"
            return None
        except Exception as e:
            print(f"Error converting artifacts URL to GCS path: {e}")
            return None
    
    def create_local_directory(self, build_id: str, base_dir: str = "artifacts") -> str:
        """Create local directory for job artifacts"""
        local_dir = os.path.join(base_dir, f"job_{build_id}")
        try:
            os.makedirs(local_dir, exist_ok=True)
            return local_dir
        except OSError as e:
            print(f"Error creating directory {local_dir}: {e}")
            return None
    
    def generate_gsutil_command(self, gcs_path: str, local_dir: str) -> str:
        """Generate gsutil command to download artifacts"""
        return f"gsutil -m cp -r {gcs_path} {local_dir}/"
    
    def download_artifacts(self, build_id: str, gcs_path: str, base_dir: str = "artifacts", dry_run: bool = False) -> bool:
        """Download artifacts for a specific build"""
        try:
            # Create local directory
            local_dir = self.create_local_directory(build_id, base_dir)
            if not local_dir:
                return False
            
            # Generate gsutil command
            gsutil_cmd = self.generate_gsutil_command(gcs_path, local_dir)
            
            print(f"Downloading artifacts for build {build_id}")
            print(f"Command: {gsutil_cmd}")
            
            if dry_run:
                print("  [DRY RUN] Command would be executed")
                return True
            
            # Execute gsutil command
            result = subprocess.run(
                gsutil_cmd.split(),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                print(f"  ✓ Successfully downloaded to {local_dir}")
                return True
            else:
                print(f"  ✗ Error downloading artifacts: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout downloading artifacts for build {build_id}")
            return False
        except Exception as e:
            print(f"  ✗ Error downloading artifacts for build {build_id}: {e}")
            return False
    
    def download_all_failed_job_artifacts(self, failed_jobs: List[Dict[str, Any]], artifacts_urls: Dict[str, str], 
                                        base_dir: str = "artifacts", dry_run: bool = False) -> Dict[str, bool]:
        """Download artifacts for all failed jobs"""
        download_results = {}
        
        print(f"\n=== Downloading Artifacts ===")
        print(f"Base directory: {os.path.abspath(base_dir)}")
        
        for job in failed_jobs:
            build_id = job.get('ID', 'Unknown')
            
            if build_id not in artifacts_urls:
                print(f"No artifacts URL found for build {build_id}")
                download_results[build_id] = False
                continue
            
            artifacts_url = artifacts_urls[build_id]
            gcs_path = self.convert_artifacts_url_to_gcs_path(artifacts_url)
            
            if not gcs_path:
                print(f"Could not convert artifacts URL to GCS path for build {build_id}")
                download_results[build_id] = False
                continue
            
            # Download artifacts
            success = self.download_artifacts(build_id, gcs_path, base_dir, dry_run)
            download_results[build_id] = success
        
        # Print summary
        successful_downloads = sum(1 for success in download_results.values() if success)
        total_downloads = len(download_results)
        
        print(f"\n=== Download Summary ===")
        print(f"Successful downloads: {successful_downloads}/{total_downloads}")
        
        return download_results
    
    def print_job_summary(self, builds: List[Dict[str, Any]], failed_jobs: List[Dict[str, Any]]):
        """Print summary of job results"""
        total_jobs = len(builds)
        failed_count = len(failed_jobs)
        success_count = len([b for b in builds if b.get('Result') == 'SUCCESS'])
        
        print(f"\n=== Job Summary for {self.job_name} ===")
        print(f"Total jobs: {total_jobs}")
        print(f"Failed jobs: {failed_count}")
        print(f"Successful jobs: {success_count}")
        print(f"Other statuses: {total_jobs - failed_count - success_count}")
    
    def print_failed_jobs_details(self, failed_jobs: List[Dict[str, Any]], artifacts_urls: Dict[str, str] = None):
        """Print detailed information about failed jobs"""
        if not failed_jobs:
            print("\nNo failed jobs found.")
            return
        
        print(f"\n=== Failed Jobs Details ===")
        for i, job in enumerate(failed_jobs, 1):
            build_id = job.get('ID', 'Unknown')
            started = job.get('Started', 'Unknown')
            duration = job.get('Duration', 'Unknown')
            spyglass_link = job.get('SpyglassLink', 'Unknown')
            
            print(f"\n{i}. Build ID: {build_id}")
            print(f"   Started: {started}")
            print(f"   Duration: {duration}")
            print(f"   SpyglassLink: {urljoin(self.PROW_BASE_URL, spyglass_link) if spyglass_link != 'Unknown' else 'Unknown'}")
            
            # Print PR information if available
            refs = job.get('Refs', {})
            if refs:
                pulls = refs.get('pulls', [])
                if pulls:
                    print(f"   PRs: {[pull.get('number') for pull in pulls]}")
            
            # Print artifacts URL (extracted from SpyglassLink if available)
            if artifacts_urls and build_id in artifacts_urls:
                print(f"   Artifacts URL: {artifacts_urls[build_id]}")
            else:
                # Fallback to constructed URL
                artifacts_url = f"https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/{self.job_name}/{build_id}/"
                print(f"   Artifacts URL (constructed): {artifacts_url}")
    
    def run(self, extract_artifacts: bool = True, json_file: str = None, 
            download_artifacts: bool = False, artifacts_dir: str = "artifacts", 
            dry_run: bool = False) -> Dict[str, Any]:
        """Main crawler execution"""
        if json_file:
            # Load builds data from JSON file
            builds = self.load_builds_from_file(json_file)
        else:
            # Fetch job history
            html_content = self.fetch_job_history()
            
            # Extract builds data
            builds = self.extract_builds_json(html_content)
        
        # Get failed jobs
        failed_jobs = self.get_failed_jobs(builds)
        
        # Print summary
        self.print_job_summary(builds, failed_jobs)
        
        # Extract artifacts URLs for failed jobs if requested
        artifacts_urls = {}
        if (extract_artifacts or download_artifacts) and failed_jobs:
            print(f"\n=== Extracting Artifacts URLs ===")
            artifacts_urls = self.get_artifacts_urls_for_failed_jobs(failed_jobs)
        
        # Download artifacts if requested
        download_results = {}
        if download_artifacts and artifacts_urls:
            download_results = self.download_all_failed_job_artifacts(
                failed_jobs, artifacts_urls, artifacts_dir, dry_run
            )
        
        # Print failed job details
        self.print_failed_jobs_details(failed_jobs, artifacts_urls)
        
        # Extract PR numbers
        pr_numbers = self.extract_pr_numbers(failed_jobs)
        
        if pr_numbers:
            print(f"\n=== Failed PR Numbers ===")
            for pr in pr_numbers:
                print(pr)
        
        # Print artifacts URLs summary
        if artifacts_urls:
            print(f"\n=== Artifacts URLs ===")
            for build_id, url in artifacts_urls.items():
                print(f"Build {build_id}: {url}")
        
        # Print GCS paths for manual use
        if artifacts_urls and not download_artifacts:
            print(f"\n=== GCS Paths (for manual gsutil) ===")
            for build_id, url in artifacts_urls.items():
                gcs_path = self.convert_artifacts_url_to_gcs_path(url)
                if gcs_path:
                    print(f"Build {build_id}: {gcs_path}")
        
        return {
            'job_name': self.job_name,
            'total_jobs': len(builds),
            'failed_jobs_count': len(failed_jobs),
            'failed_pr_numbers': pr_numbers,
            'artifacts_urls': artifacts_urls,
            'failed_jobs': failed_jobs,
            'download_results': download_results
        }


def main():
    parser = argparse.ArgumentParser(
        description="Crawl Prow CI job history to find failed jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch from web and extract artifacts URLs
  python prow_crawler.py periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
  
  # Use existing JSON file
  python prow_crawler.py --json-file prow.json periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
  
  # Download artifacts for all failed jobs
  python prow_crawler.py --json-file prow.json --download-artifacts periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
  
  # Dry run (show gsutil commands without executing)
  python prow_crawler.py --json-file prow.json --download-artifacts --dry-run periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
  
  # Download to custom directory
  python prow_crawler.py --json-file prow.json --download-artifacts --artifacts-dir my_artifacts periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
  
  # Skip artifacts extraction (faster)
  python prow_crawler.py --no-artifacts periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
  
  # Output only artifacts URLs
  python prow_crawler.py --artifacts-only periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
  
  # JSON output format
  python prow_crawler.py --json periodic-ci-openshift-microshift-release-4.19-periodics-e2e-aws-tests-bootc-nightly
        """
    )
    
    parser.add_argument(
        'job_name',
        help='The Prow CI job name to crawl'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format'
    )
    
    parser.add_argument(
        '--pr-only',
        action='store_true',
        help='Output only PR numbers (one per line)'
    )
    
    parser.add_argument(
        '--no-artifacts',
        action='store_true',
        help='Skip extracting artifacts URLs from SpyglassLinks (faster)'
    )
    
    parser.add_argument(
        '--artifacts-only',
        action='store_true',
        help='Output only artifacts URLs'
    )
    
    parser.add_argument(
        '--json-file',
        type=str,
        help='Load builds data from a JSON file instead of fetching from web'
    )
    
    parser.add_argument(
        '--download-artifacts',
        action='store_true',
        help='Download artifacts using gsutil for each failed job'
    )
    
    parser.add_argument(
        '--artifacts-dir',
        type=str,
        default='artifacts',
        help='Base directory for downloaded artifacts (default: artifacts)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show gsutil commands that would be executed without running them'
    )
    
    args = parser.parse_args()
    
    # Create and run crawler
    crawler = ProwJobCrawler(args.job_name)
    
    try:
        extract_artifacts = not args.no_artifacts
        result = crawler.run(
            extract_artifacts=extract_artifacts, 
            json_file=args.json_file,
            download_artifacts=args.download_artifacts,
            artifacts_dir=args.artifacts_dir,
            dry_run=args.dry_run
        )
        
        # Handle different output formats
        if args.json:
            print(json.dumps(result, indent=2))
        elif args.pr_only:
            for pr in result['failed_pr_numbers']:
                print(pr)
        elif args.artifacts_only:
            for build_id, url in result['artifacts_urls'].items():
                print(url)
                
    except KeyboardInterrupt:
        print("\nCrawling interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 