#!/usr/bin/env bash
# Flatten this repository into a single monolithic text file for LLM analysis.
# Usage:
#   ./flatten.sh [OUTPUT_FILE]
# Default OUTPUT_FILE is project_monolith.txt in repo root.
# Notes:
# - Only text files are included (based on `file --mime`), binaries are skipped.
# - Common junk/virtual/cache directories are excluded.
# - Each file is wrapped with a clear delimiter that includes its relative path.

set -euo pipefail

# Determine repo root (directory of this script)
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

OUTPUT_FILE="${1:-project_monolith.txt}"

# Stat helper supporting macOS and Linux
file_size() {
  local f="$1"
  if command -v gstat >/dev/null 2>&1; then
    gstat -c %s "$f"
  elif stat -f %z "$f" >/dev/null 2>&1; then
    stat -f %z "$f"  # macOS
  else
    stat -c %s "$f"  # Linux
  fi
}

# Decide if a file is text (skip binaries)
is_text_file() {
  local f="$1"
  local mt
  mt=$(file -b --mime-type "$f" 2>/dev/null || echo "application/octet-stream")
  [[ "$mt" == text/* || "$mt" == application/json || "$mt" == application/xml || "$mt" == application/x-sh ]] \
    && return 0 || return 1
}

# Exclude patterns
should_exclude() {
  local f="$1"
  case "$f" in
    ./$(basename "$OUTPUT_FILE") ) return 0;;
    ./.git/*|.git) return 0;;
    ./.svn/*|.svn) return 0;;
    ./.hg/*|.hg) return 0;;
    ./.idea/*|.idea) return 0;;
    ./.vscode/*|.vscode) return 0;;
    ./node_modules/*|node_modules) return 0;;
    ./.venv/*|.venv) return 0;;
    ./venv/*|venv) return 0;;
    ./*__pycache__/*|*__pycache__*) return 0;;
    ./.pytest_cache/*|.pytest_cache) return 0;;
    ./.mypy_cache/*|.mypy_cache) return 0;;
    ./.coverage|.coverage) return 0;;
    ./*.pyc|*.pyc) return 0;;
    ./dist/*|dist) return 0;;
    ./build/*|build) return 0;;
    ./*.db|*.db) return 0;;
    ./*.sqlite|*.sqlite) return 0;;
    ./*.sqlite3|*.sqlite3) return 0;;
    ./.DS_Store|.DS_Store) return 0;;
    *) return 1;;
  esac
}

# Initialize output
: > "$OUTPUT_FILE"

# Header
{
  echo "# Monolithic project bundle"
  echo "# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "# Repo root: $REPO_ROOT"
  echo
} >> "$OUTPUT_FILE"

# Collect and sort files

append_file() {
  local f="$1"
  local rel="${f#./}"
  local size
  size=$(file_size "$f" 2>/dev/null || echo 0)

  # Delimiter header
  {
    echo "-----8<----- FILE: $rel ($size bytes) -----"
    # Provide an indicative code fence for some common types
    case "$rel" in
      *.py) echo '```python';;
      *.yaml|*.yml) echo '```yaml';;
      *.json) echo '```json';;
      *.sh) echo '```bash';;
      *.md) echo '```markdown';;
      *) echo '```';;
    esac
    cat "$f"
    echo
    echo '```'
    echo "-----8<----- END FILE: $rel -----"
    echo
  } >> "$OUTPUT_FILE"
}

# Iterate sorted file list in a portable way (no mapfile)
find . -type f \
  ! -name ".git" -a ! -path "*/.git/*" \
  -print | LC_ALL=C sort | while IFS= read -r f; do
  # Skip the output file itself and excluded paths
  if should_exclude "$f"; then
    continue
  fi
  # Include only text-like files
  if is_text_file "$f"; then
    append_file "$f"
  fi
done

# Summary footer
{
  echo "# End of bundle"
} >> "$OUTPUT_FILE"

echo "Created monolith: $OUTPUT_FILE"
