#!/bin/sh
set -xe
# requires that nuitka is installed via pip
python3 -m nuitka --follow-imports --remove-output chatgpt.py
mv ./chatgpt.bin ~/.local/bin/chatgpt
