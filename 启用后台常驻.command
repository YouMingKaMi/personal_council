#!/bin/zsh
cd -- "${0:A:h}"
if [[ -x /opt/homebrew/bin/python3 ]]; then
  /opt/homebrew/bin/python3 background_service.py
else
  python3 background_service.py
fi
