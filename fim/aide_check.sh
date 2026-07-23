#!/bin/bash
OUTPUT_FILE=/var/lib/node_exporter/textfile_collector/aide.prom
TMP_FILE=$(mktemp)

if aide --config=/etc/aide/aide.conf --check > /tmp/aide_report.txt 2>&1; then
  echo "aide_changes_detected 0" > "$TMP_FILE"
else
  echo "aide_changes_detected 1" > "$TMP_FILE"
fi
echo "aide_last_check_timestamp $(date +%s)" >> "$TMP_FILE"
mv "$TMP_FILE" "$OUTPUT_FILE"
