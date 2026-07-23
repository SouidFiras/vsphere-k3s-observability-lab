#!/bin/bash
WATCH_DIR="/home/monitoring/DOSSIER_TEST_FIM"
METRIC_FILE="/var/lib/node_exporter/textfile_collector/folder_watch.prom"

# Don't overwrite an existing "1" state - preserve until manually acknowledged
inotifywait -m -r -e modify,attrib,create,delete,move "$WATCH_DIR" |
while read path action file; do
    echo "folder_change_detected 1" > "$METRIC_FILE"
    echo "folder_last_change_timestamp $(date +%s)" >> "$METRIC_FILE"
    echo "# last change: $action on ${path}${file}" >> "$METRIC_FILE"
    logger "FIM: detected $action on ${path}${file}"
done
