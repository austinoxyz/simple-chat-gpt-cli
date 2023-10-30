#!/usr/bin/bash
set -xe

mkdir $HOME/.local/share/simple-chat
mkdir $HOME/.local/share/simple-chat/chats
mkdir $HOME/.local/share/simple-chat/prompts
mkdir $HOME/.config/simple-chat

printf "{\n\n}" > $HOME/.config/simple-chat/config.json
