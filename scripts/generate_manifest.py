#!/usr/bin/env python3
"""
Wenget Bucket Manifest Generator

Lightweight script to generate manifest.json from sources.txt
Fetches package information from GitHub API without installing Wenget
"""

import os
import sys
import json
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Dict, List, Optional, Any

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration
GITHUB_API_BASE = "https://api.github.com"
RATE_LIMIT_DELAY = 1  # seconds between requests
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


class GitHubAPI:
    """Simple GitHub API client"""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.rate_limit_remaining = None
        self.rate_limit_reset = None

    def _make_request(self, url: str) -> Dict[str, Any]:
        """Make HTTP request to GitHub API"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Wenget-Bucket-Generator/1.0",
        }

        if self.token:
            headers["Authorization"] = f"token {self.token}"

        req = Request(url, headers=headers)

        for attempt in range(MAX_RETRIES):
            try:
                with urlopen(req, timeout=30) as response:
                    # Update rate limit info
                    self.rate_limit_remaining = response.headers.get(
                        "X-RateLimit-Remaining"
                    )
                    self.rate_limit_reset = response.headers.get("X-RateLimit-Reset")

                    data = json.loads(response.read().decode("utf-8"))
                    return data

            except HTTPError as e:
                if e.code == 403:
                    # Check if it's actually rate limit or permission issue
                    error_body = e.read().decode('utf-8') if hasattr(e, 'read') else ''
                    if 'rate limit' in error_body.lower() or self.rate_limit_remaining == '0':
                        print(f"⚠️  Rate limit exceeded. Remaining: {self.rate_limit_remaining}")
                        print(f"   Waiting {RETRY_DELAY}s before retry...")
                    else:
                        print(f"⚠️  Permission denied (403): {url}")
                        print(f"   This might be a private resource or authentication issue")

                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                    else:
                        raise
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
        "windows-x86_64": [
            r"windows.*x86_64|x86_64.*windows|win64|windows.*amd64|x64.*windows",
            r"pc-windows-msvc",
        ],
        "windows-i686": [
            r"windows.*i686|i686.*windows|win32",
            r"pc-windows-msvc.*i686",
        ],
        "linux-x86_64": [
            r"linux.*x86_64|x86_64.*linux|linux.*amd64",
            r"x86_64.*unknown-linux-gnu",
            r"x86_64.*unknown-linux-musl",
        ],
        "linux-aarch64": [
            r"linux.*aarch64|aarch64.*linux|linux.*arm64",
            r"aarch64.*unknown-linux-musl",
            r"aarch64.*unknown-linux-gnu",
        ],
        "linux-armv7": [
            r"linux.*armv7|armv7.*linux|linux.*arm7",
            r"armv7.*unknown-linux-musleabihf",
            r"armv7.*unknown-linux-gnueabihf",
        ],
        "linux-armv6": [
            r"linux.*armv6|armv6.*linux|linux.*arm6",
            r"arm.*unknown-linux-musleabihf",
            r"arm.*unknown-linux-gnueabihf",
        ],
        "linux-i686": [
            r"linux.*i686|i686.*linux",
            r"i686.*unknown-linux-gnu",
            r"i686.*unknown-linux-musl",
        ],
        "freebsd-x86_64": [
            r"freebsd.*x86_64|x86_64.*freebsd|freebsd.*amd64",
            r"x86_64.*unknown-freebsd",
        ],
        "darwin-x86_64": [
            r"darwin.*x86_64|x86_64.*darwin|macos.*x86_64|osx.*x86_64",
            r"apple-darwin.*x86_64",
            r"(?:mac|osx)-x86(?:[_.-]|\.tar|\.zip)",  # mac-x86, osx-x86 (assume x86_64)
        ],
        "darwin-aarch64": [
            r"darwin.*aarch64|aarch64.*darwin|darwin.*arm64|macos.*arm64|osx.*arm64",
            r"apple-darwin.*aarch64",
        ],
        "macos-x86_64": [
            r"macos.*x86_64|osx.*x86_64",
        ],
        "macos-aarch64": [
            r"macos.*aarch64|macos.*arm64|osx.*arm64",
        ],
    }

    # Fallback patterns for ambiguous filenames (assume most common architecture)
    # These patterns only match OS without specific architecture info
    FALLBACK_PATTERNS = {
        "windows-x86_64": [
            r"(?:^|[_-])win(?:dows)?(?:[_.-]|\.tar|\.zip|\.msi|\.exe)",  # win.tar.gz, -win.zip, win.msi
        ],
        "linux-x86_64": [
            r"(?:^|[_-])linux(?:[_.-]|\.tar|\.zip)",  # linux.tar.gz, -linux.zip
        ],
        "darwin-aarch64": [
            r"(?:^|[_-])(?:mac|macos|osx|darwin)(?:[_.-]|\.tar|\.zip)",  # mac.tar.gz, -macos.zip (assume Apple Silicon)
        ],
    }

    # Archive extensions (including standalone executables)
    ARCHIVE_EXTENSIONS = [".tar.gz", ".tgz", ".zip", ".tar.xz", ".tar.bz2", ".exe", ".msi"]

    @classmethod
    def get_linux_variant_priority(cls, filename: str) -> int:
        """
        Get priority for Linux variants (higher number = higher priority)
        Priority: musl (3) > gnu (2) > no keyword (1)
        """
        filename_lower = filename.lower()
        if "musl" in filename_lower:
            return 3
        elif "gnu" in filename_lower:
            return 2
        else:
            return 1

    @classmethod
    def detect_platform(cls, filename: str) -> Optional[str]:
        """Detect platform from filename with fallback support"""
        filename_lower = filename.lower()

        # Check if it's an archive
        if not any(filename_lower.endswith(ext) for ext in cls.ARCHIVE_EXTENSIONS):
            return None

        # Priority 1: Try exact platform patterns (with architecture info)
        for platform, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower):
                    return platform

        # Priority 2: Try fallback patterns (assume common architecture)
        for platform, patterns in cls.FALLBACK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower):
                    print(f"   ⚠️  Fallback assumption: {filename} -> {platform}")
                    return platform

        return None


class ManifestGenerator:
    """Generate manifest.json from sources.txt"""

    def __init__(self, github_token: Optional[str] = None):
        self.api = GitHubAPI(github_token)
        self.packages = []
        self.scripts = []

    def parse_github_url(self, url: str) -> Optional[tuple]:
        """Parse GitHub URL to extract owner and repo"""
        patterns = [
            r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
            r"github\.com/([^/]+)/([^/]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), match.group(2)

        return None

    def parse_gist_url(self, url: str) -> Optional[str]:
        """Parse Gist URL to extract gist ID"""
        patterns = [
            r"gist\.github\.com/[^/]+/([a-f0-9]+)",
            r"gist\.githubusercontent\.com/[^/]+/([a-f0-9]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def detect_script_type(self, filename: str) -> Optional[str]:
        """Detect script type from filename extension"""
        ext_map = {
            ".ps1": "powershell",
            ".sh": "bash",
            ".bat": "batch",
            ".cmd": "batch",
            ".py": "python",
        }

        for ext, script_type in ext_map.items():
            if filename.lower().endswith(ext):
                return script_type

        return None

    def fetch_gist_scripts(self, url: str) -> List[Dict[str, Any]]:
        """Fetch script information from GitHub Gist"""
        gist_id = self.parse_gist_url(url)
        if not gist_id:
            print(f"⚠️  Invalid Gist URL: {url}")
            return []

        try:
            # Get gist info (use anonymous access for public gists)
            gist_url = f"{GITHUB_API_BASE}/gists/{gist_id}"

            # Create a temporary API client without token for gist access
            # GITHUB_TOKEN from Actions doesn't have permission to access gists
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Wenget-Bucket-Generator/1.0",
            }
            req = Request(gist_url, headers=headers)

            with urlopen(req, timeout=30) as response:
                gist_data = json.loads(response.read().decode("utf-8"))

            scripts = []
            files = gist_data.get("files", {})

            for filename, file_info in files.items():
                script_type = self.detect_script_type(filename)
                if not script_type:
                    print(f"   ⚠️  Skipping non-script file: {filename}")
                    continue

                # Remove extension from script name
                name = filename
                for ext in [".ps1", ".sh", ".bat", ".cmd", ".py"]:
                    if name.endswith(ext):
                        name = name[:-len(ext)]
                        break

                script = {
                    "name": name,
                    "description": gist_data.get("description") or f"{filename} from gist",
                    "url": file_info["raw_url"],
                    "script_type": script_type,
                    "repo": gist_data["html_url"],
                }

                scripts.append(script)

            return scripts

        except Exception as e:
            print(f"❌ Error fetching gist {gist_id}: {e}")
            return []

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
            # Track platform info with priority for Linux variants
            platforms = {}
            platform_priorities = {}  # Track priority of selected assets

            for asset in release.get("assets", []):
                platform = PlatformDetector.detect_platform(asset["name"])
                if platform:
                    asset_info = {
                        "url": asset["browser_download_url"],
                        "size": asset["size"],
                    }

                    # For Linux platforms, check priority
                    if platform.startswith("linux-"):
                        current_priority = PlatformDetector.get_linux_variant_priority(asset["name"])
                        existing_priority = platform_priorities.get(platform, 0)

                        # Only update if current asset has higher priority
                        if current_priority > existing_priority:
                            platforms[platform] = asset_info
                            platform_priorities[platform] = current_priority
                    else:
                        # For non-Linux platforms, just use the asset
                        platforms[platform] = asset_info

            if not platforms:
                print(f"⚠️  No binary assets found for {owner}/{repo}")
                return None

            # Build package info
            package = {
                "name": repo_info["name"],
                "description": repo_info["description"] or "",
                "repo": repo_info["html_url"],
                "homepage": repo_info["homepage"],
                "license": repo_info["license"]["spdx_id"]
                if repo_info.get("license")
                else None,
                "platforms": platforms,
            }

            return package

        except Exception as e:
            print(f"❌ Error fetching {owner}/{repo}: {e}")
            return None

    def load_sources(self, sources_file: str) -> List[str]:
        """Load GitHub URLs from sources file"""
        urls = []

        if not sources_file or not os.path.exists(sources_file):
            return urls

        with open(sources_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    urls.append(line)

        return urls

    def generate(self, sources_file: str, sources_scripts_file: str, output_file: str):
        """Generate manifest.json from sources files"""
        print("🚀 Wenget Bucket Manifest Generator")
        print("=" * 50)

        # Load script sources FIRST (to avoid rate limit issues)
        print(f"\n📖 Loading script sources from {sources_scripts_file}...")
        gist_urls = self.load_sources(sources_scripts_file)
        print(f"✓ Found {len(gist_urls)} gists")

        # Fetch script info FIRST
        if gist_urls:
            print(f"\n📜 Fetching script information...")
            for i, url in enumerate(gist_urls, 1):
                print(f"\n[{i}/{len(gist_urls)}] {url}")

                scripts = self.fetch_gist_scripts(url)
                if scripts:
                    self.scripts.extend(scripts)
                    for script in scripts:
                        print(f"   ✓ {script['name']} ({script['script_type']})")

                # Rate limiting
                if i < len(gist_urls):
                    time.sleep(RATE_LIMIT_DELAY)

                # Show rate limit status periodically
                if i % 10 == 0:
                    self.api.check_rate_limit()

        # Load package sources AFTER scripts
        print(f"\n📖 Loading package sources from {sources_file}...")
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
        manifest_obj = {
            "packages": self.packages,
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Add scripts if any
        if self.scripts:
            manifest_obj["scripts"] = self.scripts

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(manifest_obj, f, indent=2, ensure_ascii=False)

        # Summary
        print("\n" + "=" * 50)
        print("✅ Generation complete!")
        print(f"   Total packages: {len(self.packages)}/{len(urls)}")
        print(f"   Total scripts: {len(self.scripts)}")
        print(f"   Output file: {output_file}")

        # Platform statistics
        platform_stats = {}
        for pkg in self.packages:
            for platform in pkg["platforms"].keys():
                platform_stats[platform] = platform_stats.get(platform, 0) + 1

        if platform_stats:
            print("\n📊 Platform coverage:")
            for platform, count in sorted(platform_stats.items()):
                print(f"   {platform}: {count} packages")

        # Script type statistics
        if self.scripts:
            script_type_stats = {}
            for script in self.scripts:
                script_type = script["script_type"]
                script_type_stats[script_type] = script_type_stats.get(script_type, 0) + 1

            print("\n📜 Script types:")
            for script_type, count in sorted(script_type_stats.items()):
                print(f"   {script_type}: {count} scripts")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Wenget bucket manifest from sources"
    )
    parser.add_argument(
        "sources",
        nargs="?",
        default="sources_repos.txt",
        help="Source file containing GitHub repository URLs (default: sources_repos.txt)",
    )
    parser.add_argument(
        "-s",
        "--scripts",
        default="sources_scripts.txt",
        help="Source file containing Gist URLs for scripts (default: sources_scripts.txt)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="manifest.json",
        help="Output manifest file (default: manifest.json)",
    )
    parser.add_argument(
        "-t",
        "--token",
        help="GitHub personal access token (or use GITHUB_TOKEN env var)",
    )

    args = parser.parse_args()

    # Check if sources file exists
    if not os.path.exists(args.sources):
        print(f"❌ Error: Source file '{args.sources}' not found")
        sys.exit(1)

    # Generate manifest
    try:
        generator = ManifestGenerator(args.token)
        generator.generate(args.sources, args.scripts, args.output)
    except KeyboardInterrupt:
        print("\n\n⚠️  Generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
