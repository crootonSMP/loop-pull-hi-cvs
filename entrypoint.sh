#!/bin/bash
set -e
touch /tmp/entrypoint.log
chmod 666 /tmp/entrypoint.log
echo "Starting entrypoint.sh" >> /tmp/entrypoint.log
echo "HIRE_USERNAME set: ${HIRE_USERNAME:+[SET]}" >> /tmp/entrypoint.log
echo "HIRE_PASSWORD set: ${HIRE_PASSWORD:+[SET]}" >> /tmp/entrypoint.log
echo "BRIGHTDATA_USERNAME set: ${BRIGHTDATA_USERNAME:+[SET]}" >> /tmp/entrypoint.log
echo "BRIGHTDATA_PASSWORD set: ${BRIGHTDATA_PASSWORD:+[SET]}" >> /tmp/entrypoint.log
echo "Checking Chrome version..." >> /tmp/entrypoint.log
/opt/chrome/chrome --version >> /tmp/entrypoint.log 2>> /tmp/entrypoint.log || echo "Chrome failed to run" >> /tmp/entrypoint.log
echo "Checking ChromeDriver version..." >> /tmp/entrypoint.log
/usr/local/bin/chromedriver --version >> /tmp/entrypoint.log 2>> /tmp/entrypoint.log || echo "ChromeDriver failed to run" >> /tmp/entrypoint.log
echo "Testing proxy connectivity..." >> /tmp/entrypoint.log
curl --fail --proxy http://${BRIGHTDATA_USERNAME}:${BRIGHTDATA_PASSWORD}@brd.superproxy.io:33335 https://example.com >> /tmp/entrypoint.log 2>> /tmp/entrypoint.log
if [ $? -ne 0 ]; then
  echo "Proxy test failed. Exiting." >> /tmp/entrypoint.log
  exit 1
fi
echo "Creating X11 directory..." >> /tmp/entrypoint.log
mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix
echo "Starting Xvfb..." >> /tmp/entrypoint.log
Xvfb :99 -screen 0 1280x720x16 -ac >> /tmp/entrypoint.log 2>> /tmp/entrypoint.log &
sleep 2
export DISPLAY=:99
echo "DISPLAY set to $DISPLAY" >> /tmp/entrypoint.log
if ! ps aux | grep -v grep | grep Xvfb > /dev/null; then
    echo "Xvfb failed to start" >> /tmp/entrypoint.log
    exit 1
fi
echo "Xvfb running" >> /tmp/entrypoint.log
echo "Running Python script..." >> /tmp/entrypoint.log
exec python daily_CV_and_candidate_importer.py
