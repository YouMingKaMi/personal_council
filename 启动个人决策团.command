#!/bin/zsh
cd -- "${0:A:h}"
if [[ -x /opt/homebrew/bin/python3 ]]; then
  /opt/homebrew/bin/python3 launcher.py
else
  python3 launcher.py
fi
