#!/bin/zsh
cd -- "${0:A:h}"
python3 recovery.py
read '?按回车关闭窗口…'
