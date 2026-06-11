#!/bin/bash
# pull-voice.sh <site> — pull voice capture data from a dashboard instance
# Works for: velocityseo1, ahn (read-only on both)
# Usage: ./pull-voice.sh velocityseo1
#        ./pull-voice.sh ahn

set -uo pipefail

SITE="${1:-}"
if [[ -z "$SITE" ]]; then
  echo "Usage: pull-voice.sh <site>"
  echo "  Sites: velocityseo1, ahn"
  exit 1
fi

SSH_KEY="$HOME/.ssh/wpengine_valn"
LOCAL_DIR="$HOME/voice-intake/$SITE"
LAST_PULL="$LOCAL_DIR/.last-pull"

case "$SITE" in
  velocityseo1)
    SSH_HOST="velocityseo1@velocityseo1.ssh.wpengine.net"
    REMOTE_BASE="/nas/content/live/velocityseo1/voice/data"
    ;;
  ahn)
    SSH_HOST="afghanhomenetw@afghanhomenetw.ssh.wpengine.net"
    REMOTE_BASE="/nas/content/live/afghanhomenetw/dashboard/data"
    ;;
  *)
    echo "Unknown site: $SITE"
    echo "Supported: velocityseo1, ahn"
    exit 1
    ;;
esac

SSH_CMD="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new $SSH_HOST"

mkdir -p "$LOCAL_DIR/capture" "$LOCAL_DIR/audio"

echo "=== pull-voice: $SITE ==="
echo "Remote: $SSH_HOST:$REMOTE_BASE"
echo "Local:  $LOCAL_DIR"
echo ""

# Record what we had before
BEFORE_CAPTURES=$(ls "$LOCAL_DIR/capture/" 2>/dev/null | wc -l | tr -d ' ')
BEFORE_AUDIO=$(ls "$LOCAL_DIR/audio/" 2>/dev/null | wc -l | tr -d ' ')

# Pull capture files
echo "Pulling capture/*.json..."
$SSH_CMD "ls $REMOTE_BASE/capture/*.json 2>/dev/null" 2>/dev/null | while read -r remote_file; do
  fname=$(basename "$remote_file")
  $SSH_CMD "cat $remote_file" > "$LOCAL_DIR/capture/$fname" 2>/dev/null
  echo "  $fname"
done

# Pull audio files
echo "Pulling audio/*..."
$SSH_CMD "ls $REMOTE_BASE/audio/* 2>/dev/null" 2>/dev/null | while read -r remote_file; do
  fname=$(basename "$remote_file")
  if [[ ! -f "$LOCAL_DIR/audio/$fname" ]]; then
    $SSH_CMD "cat $remote_file" > "$LOCAL_DIR/audio/$fname" 2>/dev/null
    echo "  $fname (new)"
  fi
done

# Pull capture log
echo "Pulling capture-log.txt..."
$SSH_CMD "cat $REMOTE_BASE/capture-log.txt 2>/dev/null" > "$LOCAL_DIR/capture-log.txt" 2>/dev/null || true

# Diff since last pull
AFTER_CAPTURES=$(ls "$LOCAL_DIR/capture/" 2>/dev/null | wc -l | tr -d ' ')
AFTER_AUDIO=$(ls "$LOCAL_DIR/audio/" 2>/dev/null | wc -l | tr -d ' ')
NEW_CAPTURES=$((AFTER_CAPTURES - BEFORE_CAPTURES))
NEW_AUDIO=$((AFTER_AUDIO - BEFORE_AUDIO))

echo ""
echo "=== Summary ==="
echo "Captures: $AFTER_CAPTURES total ($NEW_CAPTURES new)"
echo "Audio:    $AFTER_AUDIO total ($NEW_AUDIO new)"

if [[ -f "$LOCAL_DIR/capture-log.txt" ]]; then
  LOG_LINES=$(wc -l < "$LOCAL_DIR/capture-log.txt" | tr -d ' ')
  if [[ -f "$LAST_PULL" ]]; then
    LAST_LINES=$(cat "$LAST_PULL")
    NEW_LOG=$((LOG_LINES - LAST_LINES))
    if [[ $NEW_LOG -gt 0 ]]; then
      echo "Log:      $NEW_LOG new entries since last pull:"
      tail -n "$NEW_LOG" "$LOCAL_DIR/capture-log.txt" | while IFS= read -r line; do
        echo "  $line"
      done
    else
      echo "Log:      no new entries"
    fi
  else
    echo "Log:      $LOG_LINES entries (first pull)"
  fi
  echo "$LOG_LINES" > "$LAST_PULL"
else
  echo "Log:      not found"
fi

echo ""
echo "Done. Files at: $LOCAL_DIR/"
