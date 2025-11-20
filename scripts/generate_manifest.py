#!/usr/bin/env python3
"""
WenPM Bucket Manifest Generator

Lightweight script to generate manifest.json from sources.txt
Fetches package information from GitHub API without installing WenPM
"""

import os
import sys
import json
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Dict, List, Optional, Any

# Configuration
GITHUB_API_BASE = "https://api.github.com"
RATE_LIMIT_DELAY = 1  # seconds between requests
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


class GitHubAPI:
    """Simple GitHub API client"""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get('GITHUB_TOKEN')
        self.rate_limit_remaining = None
        self.rate_limit_reset = None

    def _make_request(self, url: str) -> Dict[str, Any]:
        """Make HTTP request to GitHub API"""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'WenPM-Bucket-Generator/1.0'
        }

        if self.token:
            headers['Authorization'] = f'token {self.token}'

        req = Request(url, headers=headers)

        for attempt in range(MAX_RETRIES):
            try:
                with urlopen(req, timeout=30) as response:
                    # Update rate limit info
                    self.rate_limit_remaining = response.headers.get('X-RateLimit-Remaining')
                    self.rate_limit_reset = response.headers.get('X-RateLimit-Reset')

                    data = json.loads(response.read().decode('utf-8'))
                    return data

            except HTTPError as e:
                if e.code == 403:  # Rate limit
                    print(f"⚠️  Rate limit hit. Waiting {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                elif e.code == 404:
                    raise ValueError(f"Repository not found: {url}")
                else:
                    print(f"❌ HTTP Error {e.code}: {e.reason}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                    else:
                        raise

            except URLError as e:
                print(f"❌ Network error: {e.reason}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    raise

        raise Exception(f"Failed after {MAX_RETRIES} attempts")

    def get_repo_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information"""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        return self._make_request(url)

    def get_latest_release(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get latest release information"""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/releases/latest"
        return self._make_request(url)

    def check_rate_limit(self):
        """Print rate limit status"""
        if self.rate_limit_remaining:
            print(f"ℹ️  Rate limit: {self.rate_limit_remaining} remaining")


class PlatformDetector:
    """Detect platform from release asset filename"""

    # Platform patterns (os-arch)
    PATTERNS = {
        'windows-x86_64': [
            r'windows.*x86_64|x86_64.*windows|win64|windows.*amd64|x64.*windows',
            r'pc-windows-msvc',
        ],
        'windows-i686': [
            r'windows.*i686|i686.*windows|win32',
            r'pc-windows-msvc.*i686',
        ],
        'linux-x86_64': [
            r'linux.*x86_64|x86_64.*linux|linux.*amd64',
            r'unknown-linux-gnu',
            r'unknown-linux-musl',
        ],
        'linux-aarch64': [
            r'linux.*aarch64|aarch64.*linux|linux.*arm64',
        ],
        'linux-armv7': [
            r'linux.*armv7|armv7.*linux|linux.*arm7',
        ],
        'darwin-x86_64': [
            r'darwin.*x86_64|x86_64.*darwin|macos.*x86_64|osx.*x86_64',
            r'apple-darwin.*x86_64',
        ],
        'darwin-aarch64': [
            r'darwin.*aarch64|aarch64.*darwin|darwin.*arm64|macos.*arm64|osx.*arm64',
            r'apple-darwin.*aarch64',
        ],
        'macos-x86_64': [
            r'macos.*x86_64|osx.*x86_64',
        ],
        'macos-aarch64': [
            r'macos.*aarch64|macos.*arm64|osx.*arm64',
        ],
    }

    # Archive extensions
    ARCHIVE_EXTENSIONS = ['.tar.gz', '.tgz', '.zip', '.tar.xz', '.tar.bz2']

    @classmethod
    def detect_platform(cls, filename: str) -> Optional[str]:
        """Detect platform from filename"""
        filename_lower = filename.lower()

        # Check if it's an archive
        if not any(filename_lower.endswith(ext) for ext in cls.ARCHIVE_EXTENSIONS):
            return None

        # Try each platform pattern
        for platform, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower):
                    return platform

        return None


class ManifestGenerator:
    """Generate manifest.json from sources.txt"""

    def __init__(self, github_token: Optional[str] = None):
        self.api = GitHubAPI(github_token)
        self.packages = []

    def parse_github_url(self, url: str) -> Optional[tuple]:
        """Parse GitHub URL to extract owner and repo"""
        patterns = [
            r'github\.com/([^/]+)/([^/]+?)(?:\.git)?$',
            r'github\.com/([^/]+)/([^/]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), match.group(2)

        return None

    def fetch_package_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch package information from GitHub"""
        parsed = self.parse_github_url(url)
        if not parsed:
            print(f"⚠️  Invalid GitHub URL: {url}")
            return None

        owner, repo = parsed

        try:
            # Get repository info
            repo_info = self.api.get_repo_info(owner, repo)

            # Get latest release
            try:
                release = self.api.get_latest_release(owner, repo)
            except Exception as e:
                print(f"⚠️  No releases found for {owner}/{repo}: {e}")
                return None

            # Extract platform binaries from assets
            platforms = {}
            for asset in release.get('assets', []):
                platform = PlatformDetector.detect_platform(asset['name'])
                if platform:
                    platforms[platform] = {
                        'url': asset['browser_download_url'],
                        'size': asset['size']
                    }

            if not platforms:
                print(f"⚠️  No binary assets found for {owner}/{repo}")
                return None

            # Build package info
            package = {
                'name': repo_info['name'],
                'description': repo_info['description'] or '',
                'repo': repo_info['html_url'],
                'homepage': repo_info['homepage'],
                'license': repo_info['license']['spdx_id'] if repo_info.get('license') else None,
                'platforms': platforms
            }

            return package

        except Exception as e:
            print(f"❌ Error fetching {owner}/{repo}: {e}")
            return None

    def load_sources(self, sources_file: str) -> List[str]:
        """Load GitHub URLs from sources.txt"""
        urls = []

        with open(sources_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    urls.append(line)

        return urls

    def generate(self, sources_file: str, output_file: str):
        """Generate manifest.json from sources.txt"""
        print("🚀 WenPM Bucket Manifest Generator")
        print("=" * 50)

        # Load sources
        print(f"\n📖 Loading sources from {sources_file}...")
        urls = self.load_sources(sources_file)
        print(f"✓ Found {len(urls)} repositories")

        # Fetch package info
        print(f"\n📦 Fetching package information...")
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] {url}")

            package = self.fetch_package_info(url)
            if package:
                self.packages.append(package)
                print(f"   ✓ {package['name']} - {len(package['platforms'])} platforms")

            # Rate limiting
            if i < len(urls):
                time.sleep(RATE_LIMIT_DELAY)

            # Show rate limit status periodically
            if i % 10 == 0:
                self.api.check_rate_limit()

        # Save manifest
        print(f"\n💾 Saving manifest to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.packages, f, indent=2, ensure_ascii=False)

        # Summary
        print("\n" + "=" * 50)
        print("✅ Generation complete!")
        print(f"   Total packages: {len(self.packages)}/{len(urls)}")
        print(f"   Output file: {output_file}")

        # Platform statistics
        platform_stats = {}
        for pkg in self.packages:
            for platform in pkg['platforms'].keys():
                platform_stats[platform] = platform_stats.get(platform, 0) + 1

        if platform_stats:
            print("\n📊 Platform coverage:")
            for platform, count in sorted(platform_stats.items()):
                print(f"   {platform}: {count} packages")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate WenPM bucket manifest from sources'
    )
    parser.add_argument(
        'sources',
        nargs='?',
        default='sources.txt',
        help='Source file containing GitHub URLs (default: sources.txt)'
    )
    parser.add_argument(
        '-o', '--output',
        default='manifest.json',
        help='Output manifest file (default: manifest.json)'
    )
    parser.add_argument(
        '-t', '--token',
        help='GitHub personal access token (or use GITHUB_TOKEN env var)'
    )

    args = parser.parse_args()

    # Check if sources file exists
    if not os.path.exists(args.sources):
        print(f"❌ Error: Source file '{args.sources}' not found")
        sys.exit(1)

    # Generate manifest
    try:
        generator = ManifestGenerator(args.token)
        generator.generate(args.sources, args.output)
    except KeyboardInterrupt:
        print("\n\n⚠️  Generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
