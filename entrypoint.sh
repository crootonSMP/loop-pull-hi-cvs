#!/bin/bash
# Start the virtual display server in the background
Xvfb :99 -screen 0 1280x720x16 &

# Set the DISPLAY environment variable for all subsequent commands
export DISPLAY=:99

# Execute the Python script that was passed as an argument to this script
exec python daily_CV_and_candidate_importer.py
