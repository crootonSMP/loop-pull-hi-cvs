#!/bin/bash
set -e
echo "Starting entrypoint.sh" | tee -a /tmp/entrypoint.log
echo "HIRE_USERNAME set: ${HIRE_USERNAME:+[SET]}" | tee -a /tmp/entrypoint.log
echo "HIRE_PASSWORD set: ${HIRE_PASSWORD:+[SET]}" | tee -a /tmp/entrypoint.log
echo "BRIGHTDATA_USERNAME set: ${BRIGHTDATA_USERNAME:+[SET]}" | tee -a /tmp/entrypoint.log
echo "BRIGHTDATA_PASSWORD set: ${BRIGHTDATA_PASSWORD:+[SET]}" | tee -a /tmp/entrypoint.log
echo "Checking Chrome version..." | tee -a /tmp/entrypoint.log
/opt/chrome/chrome --version >> /tmp/entrypoint.log 2>&1 || echo "Chrome failed to run" | tee -a /tmp/entrypoint.log
echo "Checking ChromeDriver version..." | tee -a /tmp/entrypoint.log
/usr/local/bin/chromedriver --version >> /tmp/entrypoint.log 2>&1 || echo "ChromeDriver failed to run" | tee -a /tmp/entrypoint.log
echo "Testing proxy connectivity..." | tee -a /tmp/entrypoint.log
curl --proxy http://${BRIGHTDATA_USERNAME}:${BRIGHTDATA_PASSWORD}@brd.superproxy.io:22225 https://example.com >> /tmp/entrypoint.log 2>&1 || echo "Proxy test failed" | tee -a /tmp/entrypoint.log
echo "Starting Xvfb..." | tee -a /tmp/entrypoint.log
Xvfb :99 -screen 0 1280x720x16 -ac >> /tmp/entrypoint.log 2>&1 &
sleep 2
export DISPLAY=:99
echo "DISPLAY set to $DISPLAY" | tee -a /tmp/entrypoint.log
if ! ps aux | grep -v grep | grep Xvfb > /dev/null; then
    echo "Xvfb failed to start" | tee -a /tmp/entrypoint.log
    exit 1
fi
echo "Xvfb running" | tee -a /tmp/entrypoint.log
echo "Running Python script..." | tee -a /tmp/entrypoint.log
exec python daily_CV_and_candidate_importer.py
