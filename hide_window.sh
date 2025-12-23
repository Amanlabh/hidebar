#!/bin/bash
# Background script to hide Hidebar window from screen sharing

WINDOW_TITLE="Hidebar"

while true; do
    # Use AppleScript to set window to be excluded from screen capture
    osascript -e "
    tell application \"System Events\"
        set appList to every application process whose name contains \"Python\" or name contains \"python3\"
        repeat with appProc in appList
            try
                set windowList to every window of appProc whose name contains \"$WINDOW_TITLE\"
                repeat with aWindow in windowList
                    try
                        set value of attribute \"AXExcludedFromScreenCapture\" of aWindow to true
                    end try
                end repeat
            end try
        end repeat
    end tell
    " 2>/dev/null
    
    sleep 1
done

