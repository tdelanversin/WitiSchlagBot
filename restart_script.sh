#!/bin/bash

# Define the path to the Python script
SCRIPT_PATH="/home/pi/repos/WitiSchlagBot/src/WitiBot.py"

# Go to the git directory
cd "$(git rev-parse --show-toplevel)"

# Pull the latest changes
git pull origin

# Check if there were any changes
if [ "$(git diff --name-only origin/main)" ]; then
    echo "Changes detected. Restarting the Python script..."
    
    # Stop the currently running Python script if it's already running
    pkill -f "$SCRIPT_PATH"
    
    # Start the Python script
    python3 "$SCRIPT_PATH" &
    
    echo "Python script restarted."
else
    echo "No changes detected. Python script will not be restarted."
fi
