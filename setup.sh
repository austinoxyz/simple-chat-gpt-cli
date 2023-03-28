#!/usr/bin/bash
mkdir $HOME/.local/share/simple-chat
mkdir $HOME/.local/share/simple-chat/chats
mkdir $HOME/.local/share/simple-chat/prompts
mkdir $HOME/.config/simple-chat

cat example_config.json >> $HOME/.config/simple-chat/config.json
