#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# search_tool.sh — Search for available tool packages across package managers
#
# Usage: search_tool.sh <keyword> [--type <apt|pip|npm|github>]
#
# Only IT Support should invoke this script.
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_ROOT="${AGENTOFFICE_ROOT:-"$(dirname "$SCRIPT_DIR")"}"

VALID_TYPES=("apt" "pip" "npm" "github")
MAX_RESULTS=10

usage() {
    cat <<'EOF'
Usage: search_tool.sh <keyword> [--type <apt|pip|npm|github>]

Search for available tool packages across package managers.

Arguments:
  keyword             Search keyword (e.g. "json", "lint", "format")

Options:
  --type <type>       Limit search to a specific package manager:
                        apt    — Debian/Ubuntu system packages
                        pip    — Python packages (PyPI)
                        npm    — Node.js packages (npm registry)
                        github — GitHub repositories (requires gh CLI)
                      If omitted, searches all available managers.
  --help              Show this help message

Output format:
  [type] package-name — description

At most 10 results are shown per package manager.

Examples:
  search_tool.sh json
  search_tool.sh linter --type pip
  search_tool.sh formatter --type npm
EOF
}

# --help check
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# --- Argument parsing --------------------------------------------------------

if [[ $# -lt 1 ]]; then
    echo "Error: Missing search keyword." >&2
    echo "Run 'search_tool.sh --help' for usage." >&2
    exit 1
fi

KEYWORD="$1"
shift

SEARCH_TYPE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)
            if [[ $# -lt 2 ]]; then
                echo "Error: --type requires a value." >&2
                exit 1
            fi
            SEARCH_TYPE="$2"
            # Validate type
            type_valid=false
            for t in "${VALID_TYPES[@]}"; do
                if [[ "$SEARCH_TYPE" == "$t" ]]; then
                    type_valid=true
                    break
                fi
            done
            if [[ "$type_valid" == false ]]; then
                echo "Error: Invalid search type '$SEARCH_TYPE'." >&2
                echo "Valid types: ${VALID_TYPES[*]}" >&2
                exit 1
            fi
            shift 2
            ;;
        *)
            echo "Error: Unknown option '$1'." >&2
            echo "Run 'search_tool.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- Search functions --------------------------------------------------------

TOTAL_RESULTS=0

search_apt() {
    if ! command -v apt-cache &>/dev/null; then
        echo "  (apt-cache not available, skipping apt search)" >&2
        return
    fi

    echo "--- [apt] Searching for '${KEYWORD}' ---"

    local count=0
    while IFS= read -r line; do
        if [[ $count -ge $MAX_RESULTS ]]; then
            break
        fi
        # apt-cache search outputs: package-name - description
        local pkg_name pkg_desc
        pkg_name="$(echo "$line" | cut -d' ' -f1)"
        pkg_desc="$(echo "$line" | cut -d' ' -f3-)"
        echo "[apt] ${pkg_name} — ${pkg_desc}"
        count=$((count + 1))
        TOTAL_RESULTS=$((TOTAL_RESULTS + 1))
    done < <(apt-cache search "$KEYWORD" 2>/dev/null || true)

    if [[ $count -eq 0 ]]; then
        echo "  (no apt results for '${KEYWORD}')"
    fi
    echo ""
}

search_pip() {
    if ! command -v pip &>/dev/null; then
        echo "  (pip not available, skipping pip search)" >&2
        return
    fi

    echo "--- [pip] Searching for '${KEYWORD}' ---"

    # pip search has been disabled on PyPI since 2021.
    # Fallback: use pip index versions or a simple PyPI JSON API query via curl.
    local count=0

    if command -v curl &>/dev/null; then
        # Use PyPI simple search via the JSON API
        local response
        response="$(curl -fsSL "https://pypi.org/pypi/${KEYWORD}/json" 2>/dev/null || true)"
        if [[ -n "$response" ]]; then
            local summary
            summary="$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['info']['summary'])" 2>/dev/null || echo "Python package")"
            echo "[pip] ${KEYWORD} — ${summary}"
            count=1
            TOTAL_RESULTS=$((TOTAL_RESULTS + 1))
        fi

        # Also try a search via the simple index (list packages matching keyword)
        # We use a lightweight approach: query the simple API and grep
        if [[ $count -eq 0 ]]; then
            local simple_list
            simple_list="$(curl -fsSL "https://pypi.org/simple/" 2>/dev/null | grep -oi "[^>]*${KEYWORD}[^<]*" | head -n "$MAX_RESULTS" || true)"
            if [[ -n "$simple_list" ]]; then
                while IFS= read -r pkg; do
                    if [[ $count -ge $MAX_RESULTS ]]; then
                        break
                    fi
                    echo "[pip] ${pkg} — (PyPI package)"
                    count=$((count + 1))
                    TOTAL_RESULTS=$((TOTAL_RESULTS + 1))
                done <<< "$simple_list"
            fi
        fi
    else
        echo "  (curl not available; cannot query PyPI)" >&2
    fi

    if [[ $count -eq 0 ]]; then
        echo "  (no pip results for '${KEYWORD}')"
    fi
    echo ""
}

search_npm() {
    if ! command -v npm &>/dev/null; then
        echo "  (npm not available, skipping npm search)" >&2
        return
    fi

    echo "--- [npm] Searching for '${KEYWORD}' ---"

    local count=0
    # npm search --json gives structured output; plain text is simpler to parse
    while IFS= read -r line; do
        if [[ $count -ge $MAX_RESULTS ]]; then
            break
        fi
        # Skip header / separator lines
        if [[ -z "$line" || "$line" =~ ^NAME || "$line" =~ ^│ ]]; then
            continue
        fi
        # npm search output columns: NAME | DESCRIPTION | AUTHOR | DATE | VERSION | KEYWORDS
        # Parse the first two meaningful columns
        local pkg_name pkg_desc
        pkg_name="$(echo "$line" | awk '{print $1}')"
        # Description is from column 2 onward up to the | or end
        pkg_desc="$(echo "$line" | awk '{$1=""; print $0}' | sed 's/^ *//' | cut -d'|' -f1 | sed 's/ *$//')"
        if [[ -n "$pkg_name" && "$pkg_name" != "|" ]]; then
            echo "[npm] ${pkg_name} — ${pkg_desc}"
            count=$((count + 1))
            TOTAL_RESULTS=$((TOTAL_RESULTS + 1))
        fi
    done < <(npm search "$KEYWORD" --long 2>/dev/null | head -n $((MAX_RESULTS + 2)) || true)

    if [[ $count -eq 0 ]]; then
        echo "  (no npm results for '${KEYWORD}')"
    fi
    echo ""
}

search_github() {
    if ! command -v gh &>/dev/null; then
        echo "  (gh CLI not available, skipping GitHub search)" >&2
        return
    fi

    # Check if gh is authenticated
    if ! gh auth status &>/dev/null 2>&1; then
        echo "  (gh CLI not authenticated, skipping GitHub search)" >&2
        return
    fi

    echo "--- [github] Searching for '${KEYWORD}' ---"

    local count=0
    while IFS=$'\t' read -r fullname description; do
        if [[ $count -ge $MAX_RESULTS ]]; then
            break
        fi
        if [[ -n "$fullname" ]]; then
            echo "[github] ${fullname} — ${description:-(no description)}"
            count=$((count + 1))
            TOTAL_RESULTS=$((TOTAL_RESULTS + 1))
        fi
    done < <(gh search repos "$KEYWORD" --limit "$MAX_RESULTS" --json fullName,description \
        --jq '.[] | [.fullName, .description] | @tsv' 2>/dev/null || true)

    if [[ $count -eq 0 ]]; then
        echo "  (no GitHub results for '${KEYWORD}')"
    fi
    echo ""
}

# --- Execute searches --------------------------------------------------------

echo "Searching for '${KEYWORD}' ..."
echo ""

if [[ -n "$SEARCH_TYPE" ]]; then
    # Search only the specified type
    case "$SEARCH_TYPE" in
        apt)    search_apt    ;;
        pip)    search_pip    ;;
        npm)    search_npm    ;;
        github) search_github ;;
    esac
else
    # Search all available package managers
    search_apt
    search_pip
    search_npm
    search_github
fi

# --- Summary -----------------------------------------------------------------

echo "Search complete. ${TOTAL_RESULTS} result(s) found."
