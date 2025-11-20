# WenPM Bucket

A curated collection of CLI tools for [WenPM](https://github.com/superyngo/WenPM).

## 📦 Usage

Add this bucket to WenPM:

```bash
wenpm bucket add superyngo https://raw.githubusercontent.com/superyngo/wenpm-bucket/main/manifest.json
```

## 🔍 Search and Install Packages

```bash
# Search for packages
wenpm search ripgrep

# Install packages
wenpm add ripgrep fd bat
```

## 📊 Statistics

- **Total Packages**: 9
- **Platform Coverage**: Windows, Linux, macOS (x86_64, ARM64)
- **Auto-Update**: Daily via GitHub Actions

## 📝 Package List

### Search & Find
- **ripgrep** - Fast grep alternative
- **fd** - Simple find alternative

### File Viewers
- **bat** - Cat with syntax highlighting
- **hexyl** - Command-line hex viewer

### Development Tools
- **hyperfine** - Command-line benchmarking

### Git Tools
- **gitui** - Terminal UI for git

### Navigation
- **zoxide** - Smarter cd command

### System Monitoring
- **bottom** - Cross-platform system monitor

### Shell Enhancement
- **starship** - Cross-shell prompt

## 🔧 Maintenance

This bucket is automatically updated daily. The manifest is generated from `sources.txt` using a lightweight Python script.

## 🤝 Contributing

To suggest a new package:

1. Open an issue with the GitHub repository URL
2. Ensure the package has binary releases
3. Verify it supports major platforms (Windows, Linux, macOS)

## 📄 License

This repository configuration is released under MIT License.

Individual packages have their own licenses - check each package's repository.

## 🔗 Links

- **WenPM**: https://github.com/superyngo/WenPM
- **Issues**: https://github.com/superyngo/wenpm-bucket/issues
