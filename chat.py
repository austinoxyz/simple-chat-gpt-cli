#!/usr/bin/python3

import sys
import re
import openai

from os import getenv, listdir
from os.path import join

from subprocess import Popen, PIPE
from time import time
from math import floor
from json import loads, dump, JSONDecodeError
from numpy import zeros, uint32

from pathlib import Path  # for xdg

# ansi color sequences
ANSI_RED = '\033[31m'
ANSI_GREEN = '\033[32m'
ANSI_YELLOW = '\033[33m'
ANSI_BLUE = '\033[34m'

# write ansi colored terminal output
def write_colored_output(output, color, end='\n') -> None:
    sys.stdout.write(color + output + '\033[0m' + end)




APP_NAME = 'simple-chat'

def get_xdg_config_dir() -> str:
    config_dir = getenv('XDG_CONFIG_HOME', '')
    if config_dir == '' or config_dir[0] != '/':
        return str(Path.home().joinpath('.config', APP_NAME))
    return str(Path(config_dir).joinpath(APP_NAME))

def get_xdg_data_dir() -> str:
    data_dir = getenv('XDG_DATA_HOME', '')
    if data_dir == '' or data_dir[0] != '/':
        return str(Path.home().joinpath('.local/share', APP_NAME)) + '/'
    return str(Path(data_dir).joinpath(APP_NAME)) + '/'




# store terminal width for text justification
TERM_WIDTH = 80

REQUIRED_CONFIG_OPTIONS = ['api_key_file']
DEFAULT_CONFIG_OPTIONS = {
    'model': 'gpt-3.5-turbo',
    'prompts_dir': f"{get_xdg_data_dir()}prompts",
    'chats_dir': f"{get_xdg_data_dir()}chats",
    'token_usage_file': f"{get_xdg_data_dir()}token_usage.json",
    'colors': {
        "black":   "#bdae93",
        "red":     "#9d0006",
        "green":   "#79740e",
        "yellow":  "#b57614",
        "blue":    "#076678",
        "magenta": "#8f3f71",
        "cyan":    "#427b58",
        "white":   "#ffffff"
    }
}

def load_config(config_file_name):
    config = {}
    try:
        json_raw = ''
        with open(config_file_name, 'r') as config_file:
            json_raw += config_file.read()
        config = loads(json_raw)
    except IOError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't read config file.", end='', flush=True)
        sys.exit(1)
    except JSONDecodeError:
        print(f"Malformed json in {config_file_name}:")
        import traceback
        print(traceback.format_exc())

    for config_key in REQUIRED_CONFIG_OPTIONS:
        if config_key not in config:
            write_colored_output("CONFIG ERROR", ANSI_RED, end='')
            print(f": Must include ", end='', flush=True)
            write_colored_output(f"{config_key}", ANSI_GREEN, end='')
            print(" in config file.", flush=True)
            sys.exit(1)

    if 'model' not in config:
        config['model'] = DEFAULT_CONFIG_OPTIONS['model']

    if 'prompts_dir' not in config:
        config['prompts_dir'] = DEFAULT_CONFIG_OPTIONS['prompts_dir']
    else:
        if config['prompts_dir'][0] != '/':
            if config['prompts_dir'][-1:] == '/':
                config['prompts_dir'] = get_xdg_data_dir() + config['prompts_dir'][:-1]
            else:
                config['prompts_dir'] = get_xdg_data_dir() + config['prompts_dir']

    if 'chats_dir' not in config:
        config['chats_dir'] = DEFAULT_CONFIG_OPTIONS['chats_dir']
    else:
        if config['chats_dir'][0] != '/':
            if config['chats_dir'][-1:] == '/':
                config['chats_dir'] = get_xdg_data_dir() + config['chats_dir'][:-1]
            else:
                config['chats_dir'] = get_xdg_data_dir() + config['chats_dir']
    
    if 'token_usage_file' not in config:
        config['token_usage_file'] = get_xdg_data_dir() + 'token_usage.json'
    else:
        if config['token_usage'][0] != '/':
            config['token_usage_file'] = get_xdg_data_dir() + config['token_usage_file']

    if 'colors' not in config:
        config['colors'] = DEFAULT_CONFIG_OPTIONS['colors']

    return config



def hex_to_truecolor_ansi(color) -> str:
    r = int(color[1:3], base=16)
    g = int(color[3:5], base=16)
    b = int(color[5:7], base=16)
    return f"\x1b[38;2;{r};{g};{b}m"

def truecolor_ify(string_to_print, color) -> str:
    return hex_to_truecolor_ansi(color) + string_to_print + '\x1b[0m'

truecolor_pattern = re.compile(r'\x1b\[([\d;]*)([A-Za-z])')
def len_truecolor(string: str) -> int:
    return len(truecolor_pattern.sub('', string))

# write truecolor ansi colored terminal output
def write_truecolor_output(output, color, end='\n') -> None:
    sys.stdout.write(hex_to_truecolor_ansi(color) + output + '\x1b[0m' + end)

def center_truecolor(string: str, width=TERM_WIDTH):
    length = len_truecolor(string)
    if length >= width:
        return string
    padding = ' ' * floor((width - len_truecolor(string)) / 2)
    return padding + string + padding

def rjust_truecolor(string: str, width=TERM_WIDTH):
    length = len_truecolor(string)
    if length >= width:
        return string
    return (' ' * (width - len_truecolor(string))) + string

def split_string_into_len_n_substrings(input_string: str, n: int) -> list[str]:
    return [input_string[i:i+n] for i in range(0, len(input_string), n)]

def wrap_truecolor_text(text: str, width_box: (int, int), pos: (int)) -> list[str]:
    wrapped_text = []
    words = text.split(' ')
    if len(words) == 1:
        return words
    line = words[0]
    begin = pos
    start_x, end_x = width_box
    max_width = end_x - start_x
    for word in words[1:]:
        if len_truecolor(line) + len_truecolor(word) < max_width:
            line += ' ' + word
        else:
            if len(wrapped_text) == 0:
                begin = start_x
            wrapped_text.append(line)
            line = word
    begin; # to trick cython
    wrapped_text.append(line)
    wrapped_text = [line for line in wrapped_text if line != '']
    return wrapped_text


# use xclip to put the last chat completion in the clipboard
def set_clipboard_text(text) -> None:
    p = Popen(['xclip', '-selection', 'clipboard'], stdin=PIPE)
    p.stdin.write(text.encode('utf-8'))
    p.stdin.close()
    p.wait()












def levenshtein_dist(s1: str, s2: str) -> int:
    len1 = len(s1)
    len2 = len(s2)
    if len1 == 0:
        return len2
    elif len2 == 0:
        return len1
    prefix_matrix = zeros((len1 + 1, len2 + 1), dtype=uint32)
    for x in range(1, len1 + 1):
        prefix_matrix[x][0] = x
    for x in range(1, len2 + 1):
        prefix_matrix[0][x] = x
    for j in range(1, len2 + 1):
        for i in range(1, len1 + 1):
            sub_cost = 0 if s1[i - 1] == s2[j - 1] else 1
            prefix_matrix[i][j] = min(
                prefix_matrix[i - 1][j] + 1,
                prefix_matrix[i][j - 1] + 1,
                prefix_matrix[i - 1][j - 1] + sub_cost)
    return (prefix_matrix.flatten())[prefix_matrix.size - 1]



def load_prompt_names(prompts_dir: str) -> list[str]:
    res = []
    try:
        res = [filename[:-7] for filename in listdir(prompts_dir) if filename.endswith('.prompt')]
    except FileNotFoundError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't find directory ", end='', flush=True)
        write_colored_output(f"{prompts_dir}", ANSI_GREEN, end='\n')
        sys.exit(1)
    return res

def load_prompt(prompt_name: str, prompts_dir: str) -> str:
    prompt_file_name = prompt_name + '.prompt'
    prompt_path = join(prompts_dir, prompt_file_name)  # os.path.join
    prompt = ''  # to trick cython
    try:
        with open(prompt_path, 'r') as prompt_file:
            prompt = prompt_file.read()
    except IOError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't read ", end='', flush=True)
        write_colored_output(f"{prompt_path}", ANSI_GREEN, end='\n')
        sys.exit(1)
    print(f'\n   Loaded prompt at {prompt_path}')
    return prompt

def save_prompt(prompt: str, prompt_name: str, prompts_dir: str) -> None:
    prompt_file_name = prompt_name + '.prompt'
    prompt_path = join(prompts_dir, prompt_file_name) # os.path.join
    color_prompts_dir = truecolor_ify('$prompts_dir', CFG_COLOR)
    try:
        with open(prompt_path, 'w') as prompt_file:
            prompt_file.write(prompt)
    except IOError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't write to {color_prompts_dir}/{prompt_file_name}")
        return
    print(f'\n   Saved to {color_prompts_dir}/{prompt_file_name}')



def load_chat_names(chats_dir: str) -> list[str]:
    res = []
    try:
        res = [filename[:-5] for filename in listdir(chats_dir) if filename.endswith('.chat')]
    except FileNotFoundError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't find directory ", end='', flush=True)
        write_colored_output(f"{chats_dir}", ANSI_GREEN, end='\n')
        sys.exit(1)
    return res

def load_chat(chat_name: str, chats_dir: str) -> list[dict[str,str]]:
    chat_file_name = chat_name + '.chat'
    chat_path = join(chats_dir, chat_file_name)  # os.path.join
    chat = []  # to trick cython
    try:
        with open(chat_path, 'r') as chat_file:
            chat = loads(chat_file.readline())
    except IOError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't read ", end='', flush=True)
        write_colored_output(f"{chat_path}", ANSI_GREEN, end='\n')
        sys.exit(1)
    print(f'\n   Loaded chat at {chat_path}')
    return chat


def save_chat(messages: list[dict[str, str]], chat_name: str) -> None:
    chat_file_name = chat_name + '.chat'
    save_path = join(config['chats_dir'], chat_file_name)  # os.path.join
    color_chats_dir = truecolor_ify('$chats_dir', CFG_COLOR)
    try:
        with open(save_path, 'w') as outfile:
            dump(messages, outfile) # json.dump
    except IOError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't write to ", end='', flush=True)
        write_colored_output(f"{color_chats_dir}{chat_file_name}", ANSI_GREEN, end='\n')
    print(f"\n   Saved to {color_chats_dir}/{chat_file_name}")










def load_token_usage(token_usage_file_name):
    token_usage = {}  # to trick cython
    try:
        with open(token_usage_file_name, 'r') as token_usage_file:
            token_usage = loads(token_usage_file.readline())
    except IOError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't read ", end='', flush=True)
        write_colored_output(f"{token_usage_file_name}", ANSI_GREEN, end='\n')
        sys.exit(1)
    return token_usage

def account_token_usage(request_token_usage) -> None:
    pass






config_file_name = 'config.json'
config = load_config(get_xdg_config_dir() + '/config.json')

openai.api_key_path = config["api_key_file"]

token_usage = load_token_usage(config['token_usage_file'])
session_token_usage = { "completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0 }

prompt_names = load_prompt_names(config['prompts_dir'])
def list_saved_prompts() -> None:
    print(flush=True)
    for i, name in enumerate(prompt_names):
        print(f"   {i+1}. {name}")
    print(flush=True)

chat_names = load_chat_names(config['chats_dir'])
def list_saved_chats() -> None:
    print(flush=True)
    for i, name in enumerate(chat_names):
        print(f"   {i+1}. {name}")
    print(flush=True)

CMD_COLOR = config['colors']['blue']
CFG_COLOR = config['colors']['green']




commands = { 'exit':         "exit simple-chat-gpt-cli", 
             'help':         "display the message you are currently reading.",
             'clip':         "store the contents of the last chat completion in the clipboard.", 
             'prompt new':   "create a new prompt and begin using it.", 
             'prompt list': f"list the saved prompts located in your {truecolor_ify('prompts_dir', CFG_COLOR)}", 
             'prompt load': f"load a saved prompt from your {truecolor_ify('prompts_dir', CFG_COLOR)}",
             'save':         "save the current chat history.",
             'chat new':     "begin a new chat",
             'chat list':    f"list the saved chats located in your {truecolor_ify('chats_dir', CFG_COLOR)}", 
             'chat load':    f"load a saved chat from your {truecolor_ify('chats_dir', CFG_COLOR)}" }

MOST_WORDS_IN_COMMAND = max([len(cmd_name.split(' ')) for cmd_name in commands.keys()])

LEV_DIST_CUTOFF = 6  # arbitrarily chosen

LONGEST_PROMPT_NAME = 0 if len(prompt_names) == 0 else max([len(name) for name in prompt_names])
LONGEST_COMMAND_NAME = max(commands.keys(), key=lambda k: len(k))
SIMILAR_COMMAND_LENGTH_CUTOFF = len(LONGEST_COMMAND_NAME) + LONGEST_PROMPT_NAME


def find_similar_command_name(user_input: str) -> str:
    if len(user_input) >= SIMILAR_COMMAND_LENGTH_CUTOFF:
        return ''
    distances = []
    for command_name in commands:
        dist = levenshtein_dist(user_input, command_name)
        if dist < LEV_DIST_CUTOFF:
            distances.append((command_name, dist))
    if len(distances) == 0:
        return ''
    minimum = min(distances, key=lambda c:c[1])
    if minimum[1] == 0:
        return ''
    return minimum[0]



def print_startup_message() -> None:
    print(flush=True)
    print('Welcome to simple-chat-gpt-cli'.center(TERM_WIDTH))
    print(center_truecolor(f"\ttype {truecolor_ify('exit', CMD_COLOR)} to exit, or \
{truecolor_ify('help', CMD_COLOR)} for a list of commands"))
    print(flush=True)


def print_help_message() -> None:
    command_name_total_space = int(TERM_WIDTH * 0.35)
    for command_name in commands:
        colored_command = truecolor_ify(command_name, CMD_COLOR)
        usage_split = wrap_truecolor_text(commands[command_name], 
                                (command_name_total_space + 2, TERM_WIDTH), 
                                command_name_total_space + 2)
        print(rjust_truecolor(colored_command, width=(command_name_total_space)), end='')
        print(f"  {usage_split[0]}")
        if len(usage_split) == 0:
            return
        for s in usage_split[1:]:
            print(f"{' ' * (command_name_total_space + 2)}{s}")
    print(flush=True)



def print_cli_prompt() -> None:
    print(f"{truecolor_ify('   >>> ', config['colors']['yellow'])}", end='')

def ask_save_prompt() -> None:
    print('\n   Save this prompt for future use? y/n')
    if confirm():
        print('\n   Prompt name: ')
        print_cli_prompt()
        prompt_name = input()
        if prompt_name in prompt_names:
            print(f"\n   There is already a prompt with that name saved in \
{truecolor_ify('$prompts_dir', CFG_COLOR)}.\n   Do you want to overwrite it?")
            if not confirm():
                print('\n   Prompt left unsaved.')
                return
        save_prompt(prompt, prompt_name, config['prompts_dir'])
        prompt_names.append(prompt_name)

def ask_save_chat() -> None:
    print('\n   What would you like to name this chat?')
    print_cli_prompt()
    chat_name = input()
    if len(chat_names) != 0 and chat_name in chat_names:
        print("\n   There is already a chat saved with that name. Overwrite it?")
        print_cli_prompt()
        are_you_sure = input()
        if are_you_sure not in ['y', 'yes']:
            print("\n   Not saving chat.")
            return
    save_chat(messages, chat_name)
    chat_names.append(chat_name)

def ask_selection() -> int:
    selected_n = 0
    while True:
        print_cli_prompt()
        selected_n = input()
        if selected_n.isdigit():
            break
        print("\n   Must enter number.")
    assert(selected_n != 0)
    return selected_n

def confirm() -> bool:
    print_cli_prompt()
    are_you_sure = input()
    return are_you_sure in ['y', 'yes']


def apply_prompt(messages: list[dict[str, str]], prompt: str) -> list[dict[str, str]]:
    for i, message in enumerate(messages):
        if message['role'] == 'system':
            messages[i]['content'] = prompt
            return messages
    return [ {'role': 'system', 'content': prompt}, *messages ]

        

# main
last_response = ''
messages = []

print_startup_message()
while True:
    # FIXME: Pasting in messages with newlines breaks this
    print_cli_prompt()
    message = input()
    if message == '':
        continue 

    closest_command = find_similar_command_name(message)
    if closest_command != '':
        print(center_truecolor(f"Did you mean {truecolor_ify(closest_command, CMD_COLOR)}?", TERM_WIDTH))
        continue

    split_message = message.split(' ')
    if len(split_message) <= MOST_WORDS_IN_COMMAND:
        # TODO implement `clip code [n]`
        if split_message[0] == 'exit':
            account_token_usage(session_token_usage)
            print(flush=True)
            sys.exit(0)
        elif split_message[0] == 'help':
            print_help_message()
            continue
        elif split_message[0] == 'clip':
            if last_response == '':
                print(center_truecolor(f"\n   Must provide an initial message before you can \
{truecolor_ify('clip', CMD_COLOR)}", TERM_WIDTH))
                continue
            set_clipboard_text(last_response)
            continue
        elif split_message[0] == 'prompt':
            if split_message[1] == 'new':
                chat_type = 'current'
                if last_response != '':
                    print('Start new chat? y/n')
                    if confirm():
                        chat_type = 'new'
                        messages = []
                print('Enter your prompt:'.center(TERM_WIDTH)); print(flush=True)
                print_cli_prompt()
                prompt = input()
                ask_save_prompt()
                messages = apply_prompt(messages, prompt)
                print(f"\n   Prompt applied to {chat_type} chat.")
                continue
            elif split_message[1] == 'list':
                if len(prompt_names) == 0:
                    print(f"\n   No prompts located in {truecolor_ify(config['prompts_dir'], CFG_COLOR)}")
                    continue
                list_saved_prompts()
                continue
            elif split_message[1] == 'load':
                if len(prompt_names) == 0:
                    print(f"\n   No prompts located in {truecolor_ify(config['prompts_dir'], CFG_COLOR)}")
                    continue
                if last_response != '':
                    print('\n   Start new chat? y/n')
                    if confirm():
                        messages = []
                        continue
                list_saved_prompts()
                selected_prompt_n = ask_selection()
                selected_prompt_name = prompt_names[int(selected_prompt_n) - 1]
                prompt = load_prompt(selected_prompt_name, config['prompts_dir'])
                messages = apply_prompt(messages, prompt)
                continue
        elif split_message[0] == 'save':
            ask_save_chat()
            continue
        elif split_message[0] == 'chat':
            if split_message[1] == 'list':
                if len(prompt_names) == 0:
                    print(f"\n   No chats located in {truecolor_ify(config['chats_dir'], CFG_COLOR)}")
                    continue
                list_saved_chats()
                continue
            elif split_message[1] == 'load':
                if len(chat_names) == 0:
                    print(f"\n   No chats located in {truecolor_ify(config['prompts_dir'], CFG_COLOR)}")
                    continue
                if last_response != '':
                    print('\n   Leave current chat? y/n')
                    if not confirm():
                        print('\n   Not starting new chat.')
                        continue
                list_saved_chats()
                selected_chat_n = ask_selection()
                selected_chat_name = chat_names[int(selected_chat_n) - 1]
                messages = load_chat(selected_chat_name, config['chats_dir'])
                continue
            elif split_message[1] == 'new':
                print('\n   Leave current chat? y/n')
                if confirm():
                    prompt = ''
                    print('\n   Include prompt? y/n')
                    if confirm():
                        print('\n   Use existing prompt? y/n')
                        if confirm():
                            list_saved_prompts()
                            selected_prompt_n = ask_selection()
                            selected_prompt_name = prompt_names[int(selected_prompt_n) - 1]
                            prompt = load_prompt(selected_prompt_name, config['prompts_dir'])
                        else:
                            print('Enter your prompt:'.center(TERM_WIDTH)); print(flush=True)
                            print_cli_prompt()
                            prompt = input()
                    messages = [{'role':'system', 'content': prompt}]
                print('\n   Begin new chat')
                continue
            

    messages.append({"role": "user", "content": message})

    start_time = time()
    response = openai.ChatCompletion.create(
        model=config['model'],
        messages=messages,
        temperature=0,
        stream=True)

    # FIXME see below FIXME
    start_cursor = int(TERM_WIDTH * 0.2)
    end_cursor = TERM_WIDTH - int(TERM_WIDTH * 0.25)

    collected_chunks = []
    collected_messages = []
    chunk_tokens = 0

    print(f"{' ' * start_cursor}")
    for chunk in response:

        chunk_time = time() - start_time  
        collected_chunks.append(chunk)  
        chunk_delta = loads(f"{chunk['choices'][0]['delta']}")

        chunk_tokens = 0
        cursor = start_cursor
        if "role" in chunk_delta:
            continue
        elif "content" in chunk_delta:
            chunk_message = chunk_delta["content"]
            collected_messages.append(chunk_message)  

            # FIXME padding on either side of chat completion response not working
            if ' ' in chunk_message and cursor > end_cursor:
                print(chunk_message, flush=True)
                if cursor != start_cursor:
                    print("\n", flush=True)
                print(f"{' ' * start_cursor}", flush=True)
                cursor = start_cursor
            cursor += len(chunk_message)

            chunk_tokens += 1
            print(chunk_message, end='', flush=True)
        last_response = ''.join(collected_messages)

    messages.append({"role": "assistant", "content": last_response})
    session_token_usage["completion_tokens"] += chunk_tokens
    print('\n\n', end='')

