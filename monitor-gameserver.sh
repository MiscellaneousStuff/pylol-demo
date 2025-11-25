#!/bin/bash
while true; do
    echo "Time: $(date '+%H:%M:%S')"
    ps aux | grep -E "GameServerConsole" | grep -v grep | \
    awk '{printf "PID: %s, CPU: %s%%, MEM: %s%%, CMD: %s\n", $2, $3, $4, $11}'
    echo "----------------"
    sleep 1
    clear  # Optional
done