#!/bin/bash
echo "folder_change_detected 0" > /var/lib/node_exporter/textfile_collector/folder_watch.prom
echo "folder_last_check_timestamp $(date +%s)" >> /var/lib/node_exporter/textfile_collector/folder_watch.prom
echo "Alert acknowledged and cleared."
