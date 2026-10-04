#!/bin/zsh
cd "${0:A:h}"
GF_PYTHON=""
for candidate in /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [[ -x "$candidate" ]] && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
    GF_PYTHON="$candidate"
    break
  fi
done
if [[ -z "$GF_PYTHON" ]]; then
  open 'https://www.python.org/downloads/macos/'
  echo 'Install Python 3.12 or newer from python.org, then run Setup Mac again.'
else
  "$GF_PYTHON" setup.py
fi
read '?Press Return to close.'
