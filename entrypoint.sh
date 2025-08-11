#!/bin/bash
set -e
echo "Starting entrypoint.sh"
echo "HIRE_USERNAME set: ${HIRE_USERNAME:+[SET]}"
echo "HIRE_PASSWORD set: ${HIRE_PASSWORD:+[SET]}"
echo "BRIGHTDATA_USERNAME set: ${BRIGHTDATA_USERNAME:+[SET]}"
echo "BRIGHTDATA_PASSWORD set: ${BRIGHTDATA_PASSWORD:+[SET]}"
echo "Checking Chrome version..."
/opt/chrome/chrome --version || echo "Chrome failed to run"
echo "Checking ChromeDriver version..."
/usr/local/bin/chromedriver --version || echo "ChromeDriver failed to run"
echo "Testing proxy connectivity..."
curl --proxy http://${BRIGHTDATA_USERNAME}:${BRIGHTDATA_PASSWORD}@brd.superproxy.io:22225 https://example.com || echo "Proxy test failed"
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1280x720x16 &
sleep 2
export DISPLAY=:99
echo "DISPLAY set to $DISPLAY"
ps aux | grep Xvfb || echo "Xvfb not running"
echo "Running Python script..."
exec python daily_CV_and_candidate_importer.py
