#!/usr/bin/env python3
"""
WenPM Bucket Manifest Validator

Validates manifest.json format and content
"""

import json
import sys
from typing import Dict, List, Any


class ManifestValidator:
    """Validate manifest.json structure and content"""

    REQUIRED_PACKAGE_FIELDS = ['name', 'description', 'repo', 'platforms']
    REQUIRED_PLATFORM_FIELDS = ['url', 'size']

    def __init__(self, manifest_file: str):
        self.manifest_file = manifest_file
        self.errors = []
        self.warnings = []
        self.packages = []

    def validate(self) -> bool:
        """Validate manifest file"""
        print("🔍 WenPM Bucket Manifest Validator")
        print("=" * 50)

        # Load manifest
        if not self._load_manifest():
            return False

        # Validate structure
        self._validate_structure()

        # Validate each package
        for i, package in enumerate(self.packages):
            self._validate_package(package, i)

        # Check for duplicates
        self._check_duplicates()

        # Print results
        self._print_results()

        return len(self.errors) == 0

    def _load_manifest(self) -> bool:
        """Load and parse manifest file"""
        try:
            with open(self.manifest_file, 'r', encoding='utf-8') as f:
                self.packages = json.load(f)
            print(f"✓ Loaded {self.manifest_file}")
            return True
        except FileNotFoundError:
            self.errors.append(f"File not found: {self.manifest_file}")
            return False
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error loading file: {e}")
            return False

    def _validate_structure(self):
        """Validate overall manifest structure"""
        if not isinstance(self.packages, list):
            self.errors.append("Manifest must be an array of packages")
            return

        if len(self.packages) == 0:
            self.warnings.append("Manifest is empty")

    def _validate_package(self, package: Dict[str, Any], index: int):
        """Validate individual package"""
        pkg_id = package.get('name', f'package[{index}]')

        # Check required fields
        for field in self.REQUIRED_PACKAGE_FIELDS:
            if field not in package:
                self.errors.append(f"{pkg_id}: Missing required field '{field}'")

        # Validate name
        if 'name' in package:
            if not isinstance(package['name'], str) or not package['name']:
                self.errors.append(f"{pkg_id}: Invalid name")

        # Validate description
        if 'description' in package:
            if not isinstance(package['description'], str):
                self.errors.append(f"{pkg_id}: Invalid description")

        # Validate repo URL
        if 'repo' in package:
            repo = package['repo']
            if not isinstance(repo, str):
                self.errors.append(f"{pkg_id}: Invalid repo URL")
            elif not repo.startswith('https://github.com/'):
                self.warnings.append(f"{pkg_id}: Repo URL not from GitHub")

        # Validate homepage (optional)
        if 'homepage' in package and package['homepage']:
            if not isinstance(package['homepage'], str):
                self.errors.append(f"{pkg_id}: Invalid homepage")

        # Validate license (optional)
        if 'license' in package and package['license']:
            if not isinstance(package['license'], str):
                self.warnings.append(f"{pkg_id}: Invalid license format")

        # Validate platforms
        if 'platforms' in package:
            self._validate_platforms(package['platforms'], pkg_id)
        else:
            self.errors.append(f"{pkg_id}: Missing platforms")

    def _validate_platforms(self, platforms: Dict[str, Any], pkg_id: str):
        """Validate platforms object"""
        if not isinstance(platforms, dict):
            self.errors.append(f"{pkg_id}: Platforms must be an object")
            return

        if len(platforms) == 0:
            self.errors.append(f"{pkg_id}: No platforms defined")
            return

        # Validate each platform
        for platform_id, platform_data in platforms.items():
            self._validate_platform(platform_data, pkg_id, platform_id)

    def _validate_platform(self, platform: Dict[str, Any], pkg_id: str, platform_id: str):
        """Validate individual platform"""
        if not isinstance(platform, dict):
            self.errors.append(f"{pkg_id}/{platform_id}: Platform data must be an object")
            return

        # Check required fields
        for field in self.REQUIRED_PLATFORM_FIELDS:
            if field not in platform:
                self.errors.append(f"{pkg_id}/{platform_id}: Missing '{field}'")

        # Validate URL
        if 'url' in platform:
            url = platform['url']
            if not isinstance(url, str):
                self.errors.append(f"{pkg_id}/{platform_id}: Invalid URL")
            elif not url.startswith('https://'):
                self.warnings.append(f"{pkg_id}/{platform_id}: URL not using HTTPS")

        # Validate size
        if 'size' in platform:
            size = platform['size']
            if not isinstance(size, int) or size <= 0:
                self.errors.append(f"{pkg_id}/{platform_id}: Invalid size")

        # Validate checksum (optional)
        if 'checksum' in platform:
            checksum = platform['checksum']
            if not isinstance(checksum, str):
                self.warnings.append(f"{pkg_id}/{platform_id}: Invalid checksum format")

    def _check_duplicates(self):
        """Check for duplicate package names"""
        names = [pkg.get('name') for pkg in self.packages if 'name' in pkg]
        duplicates = set([name for name in names if names.count(name) > 1])

        for dup in duplicates:
            self.errors.append(f"Duplicate package name: {dup}")

    def _print_results(self):
        """Print validation results"""
        print("\n" + "=" * 50)

        if self.errors:
            print(f"\n❌ {len(self.errors)} Error(s):")
            for error in self.errors:
                print(f"   • {error}")

        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} Warning(s):")
            for warning in self.warnings:
                print(f"   • {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ Manifest is valid!")
            print(f"   • {len(self.packages)} package(s)")

            # Count total platforms
            total_platforms = sum(len(pkg.get('platforms', {})) for pkg in self.packages)
            print(f"   • {total_platforms} platform binaries")

        print()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Validate WenPM bucket manifest'
    )
    parser.add_argument(
        'manifest',
        nargs='?',
        default='manifest.json',
        help='Manifest file to validate (default: manifest.json)'
    )

    args = parser.parse_args()

    validator = ManifestValidator(args.manifest)
    success = validator.validate()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
