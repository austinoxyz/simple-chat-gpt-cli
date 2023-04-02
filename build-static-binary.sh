#!/bin/sh

# requires that nuitka is installed via pip
python3 -m nuitka --follow-imports chatgpt.py

mv ./chatgpt.bin ~/.local/bin/chatgpt
rm -r ./chatgpt.build
