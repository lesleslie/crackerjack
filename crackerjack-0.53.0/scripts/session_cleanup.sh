#!/usr/bin/env bash
# Session Cleanup Script - Run after checkpoint
# Addresses cache buildup and temporary files

set -euo pipefail

echo "🧹 Starting session cleanup..."

# High Priority: Python cache
echo "📦 Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name ".coverage*" -delete 2>/dev/null || true
rm -rf htmlcov/ 2>/dev/null || true

# Medium Priority: macOS artifacts
echo "🍎 Cleaning macOS artifacts..."
find . -name ".DS_Store" -delete 2>/dev/null || true

# Git optimization
echo "🔧 Optimizing Git repository..."
git gc --auto 2>/dev/null || true

# UV cache cleanup (optional)
echo "📭 Cleaning UV package cache..."
uv cache clean 2>/dev/null || true

echo "✅ Session cleanup complete!"
echo ""
echo "Disk space saved:"
du -sh .venv 2>/dev/null || echo "  (venv: not checked)"
du -sh .git 2>/dev/null || echo "  (git: not checked)"
