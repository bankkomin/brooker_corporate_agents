#!/usr/bin/env bash
# Replay errored + previously-unsupported files with rate limiting.
# Usage: bash scripts/replay-ingest.sh
#
# Sources:
#   /tmp/ingest-bulk/errors.log    — 577 files that hit Gemini rate-limit / chunker exception
#   /tmp/ingest-bulk/skipped.log   — 288 files; we now have readers for .doc .pptx .xls .msg
#
# Strategy:
#   - 1 second sleep between each request (= 60 req/min, well under Gemini limits)
#   - extension blacklist (skip .js .css .gif .png .jpg .db .ico .json .xml etc.)
#   - logs ok/err/skip counters to /tmp/replay/
set -u

ERR_LOG=/tmp/ingest-bulk/errors.log
SKIP_LOG=/tmp/ingest-bulk/skipped.log
OUT_DIR=/tmp/replay
mkdir -p "$OUT_DIR"
LOG="$OUT_DIR/replay.log"
NEW_ERR="$OUT_DIR/errors.log"
NEW_SKIP="$OUT_DIR/skipped.log"
: > "$LOG"; : > "$NEW_ERR"; : > "$NEW_SKIP"

TOTAL_OK=0
TOTAL_ERR=0
TOTAL_SKIP=0
SLEEP_BETWEEN=1   # seconds

declare -A BLACKLIST=(
    [".js"]=1 [".css"]=1 [".gif"]=1 [".png"]=1 [".jpg"]=1 [".jpeg"]=1
    [".db"]=1 [".ico"]=1 [".json"]=1 [".xml"]=1 [".woff"]=1 [".woff2"]=1
    [".ttf"]=1 [".eot"]=1 [".svg"]=1 [".tmp"]=1 [".bak"]=1
)

detect_type() {
    case "${1,,}" in
        *.pdf)  echo pdf ;;
        *.docx) echo docx ;;
        *.xlsx) echo xlsx ;;
        *.pptx) echo pptx ;;
        *.doc)  echo doc ;;
        *.xls)  echo xls ;;
        *.msg)  echo msg ;;
        *.md)   echo md ;;
        *.txt)  echo txt ;;
        *)      echo "" ;;
    esac
}

# Map a file path to (dept, collection). Mirror of the original run.sh routing:
#   brooker_database/{dept}/...  -> dept = {dept}, collection = {dept}_docs
#   2nd_Brain/*                  -> dept = shared,  collection = shared_policies
classify() {
    local f="$1"
    if [[ "$f" == *"/brooker_database/"* ]]; then
        local dept
        dept=$(echo "$f" | sed -E 's|.*/brooker_database/([^/]+)/.*|\1|')
        echo "$dept:${dept}_docs:brooker_database"
    elif [[ "$f" == *"/2nd_Brain/"* ]]; then
        echo "shared:shared_policies:2nd_brain"
    else
        echo ":::"   # unknown
    fi
}

ingest_one() {
    local file="$1"
    local ext=".${file##*.}"
    ext="${ext,,}"
    if [ -n "${BLACKLIST[$ext]:-}" ]; then
        echo "$file" >> "$NEW_SKIP"; TOTAL_SKIP=$((TOTAL_SKIP+1)); return
    fi
    local dt; dt=$(detect_type "$file")
    if [ -z "$dt" ]; then
        echo "$file" >> "$NEW_SKIP"; TOTAL_SKIP=$((TOTAL_SKIP+1)); return
    fi

    local triple; triple=$(classify "$file")
    local dept coll src
    dept="$(cut -d: -f1 <<< "$triple")"
    coll="$(cut -d: -f2 <<< "$triple")"
    src="$(cut -d: -f3 <<< "$triple")"
    if [ -z "$dept" ]; then
        echo "$file" >> "$NEW_SKIP"; TOTAL_SKIP=$((TOTAL_SKIP+1)); return
    fi

    local resp
    resp=$(curl -s -m 180 -X POST http://localhost:3004/ingest/document \
        -F "file=@$file;type=application/octet-stream" \
        -F "dept=${dept^^}" -F "doc_type=$dt" -F "collection=$coll" \
        -F "source=$src" 2>&1)

    if echo "$resp" | grep -q '"status":"ingested"'; then
        TOTAL_OK=$((TOTAL_OK+1))
    elif echo "$resp" | grep -q '"status":"skipped"'; then
        echo "SKIP $file :: $resp" >> "$NEW_SKIP"; TOTAL_SKIP=$((TOTAL_SKIP+1))
    else
        echo "ERR  $file :: $(echo "$resp" | head -c 200)" >> "$NEW_ERR"; TOTAL_ERR=$((TOTAL_ERR+1))
    fi
    sleep "$SLEEP_BETWEEN"
}

extract_path() {
    # error/skip log line shape: "ERR  /path/to/file :: ..." or "SKIP /path/to/file :: ..."
    # also handles bare "/path/to/file" (unsupported-type entries written by the
    # original script when detect_type returned empty).
    awk '
        /^ERR / || /^SKIP / { sub(/^(ERR|SKIP) +/, ""); sub(/ ::.*$/, ""); print; next }
        /^\// { print }
    ' "$1"
}

START=$(date +%s)
echo "[$(date +%T)] starting replay" | tee -a "$LOG"

# Combine + dedupe sources.
PATHS=$(mktemp)
extract_path "$ERR_LOG"  >  "$PATHS"
extract_path "$SKIP_LOG" >> "$PATHS"
TOTAL=$(sort -u "$PATHS" | wc -l)
echo "  unique candidate files: $TOTAL" | tee -a "$LOG"

i=0
while IFS= read -r file; do
    [ -z "$file" ] && continue
    [ ! -f "$file" ] && continue
    i=$((i+1))
    ingest_one "$file"
    if (( i % 25 == 0 )); then
        echo "  [$(date +%T)] $i/$TOTAL ok=$TOTAL_OK err=$TOTAL_ERR skip=$TOTAL_SKIP" | tee -a "$LOG"
    fi
done < <(sort -u "$PATHS")

END=$(date +%s)
echo "[$(date +%T)] DONE ok=$TOTAL_OK err=$TOTAL_ERR skip=$TOTAL_SKIP wall=$((END-START))s" | tee -a "$LOG"
rm -f "$PATHS"
