#!/usr/bin/python3

import sys
import re
import openai

import readline

from os import getenv, listdir, get_terminal_size
from os.path import join, exists

from subprocess import Popen, PIPE
from time import time
from math import floor
from json import loads, dump, JSONDecodeError
from numpy import zeros, uint32

from pathlib import Path  # for xdg

APP_NAME = 'simple-chat'

# for error messages on startup before config has been read
ANSI_RED = '\033[31m'
ANSI_GREEN = '\033[32m'
ANSI_PURPLE = '\033[35m'

# write standard ansi colored terminal output
def write_colored_output(output, color, end='\n') -> None:
    sys.stdout.write(color + output + '\033[0m' + end)

# implicit $HOME before these locations
DEFAULT_XDG_LOCATIONS = {
    'XDG_CONFIG_HOME': '.config',
    'XDG_DATA_HOME':   '.local/share' }

def get_xdg_dir(xdg_env_var: str) -> str:
    xdg_dir = getenv(xdg_env_var, '')
    if xdg_dir == '' or xdg_dir[0] != '/':
        default_loc = DEFAULT_XDG_LOCATIONS[xdg_env_var]
        return str(Path.home().joinpath(default_loc, APP_NAME)) + '/'
    return str(Path(xdg_dir).joinpath(APP_NAME)) + '/'

DEFAULT_CONFIG_OPTIONS = {
    'model': 'gpt-3.5-turbo',
    'prompts_dir': f"{get_xdg_dir('XDG_DATA_HOME')}prompts",
    'chats_dir': f"{get_xdg_dir('XDG_DATA_HOME')}chats",
    'token_usage_file': f"{get_xdg_dir('XDG_DATA_HOME')}token_usage.json",
    'term_width': 80,
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

DEFAULT_CONFIG_LOCATION = get_xdg_dir('XDG_CONFIG_HOME') + 'config.json'
config_location = DEFAULT_CONFIG_LOCATION

chat_path_on_start = ''
prompt_path_on_start = ''
api_key_path = ''

SHORT_OPTIONS = ['-f', '-c', '-p', '-k']
LONG_OPTIONS  = ['--config', '--chat', '--prompt', '--key'] 

def parse_cmd_line_options() -> None:
    def option_value_valid(opt_idx: int) -> bool:
        if opt_idx + 1 >= len(sys.argv) or sys.argv[opt_idx + 1][0] == '-':
            print(f"\n    Must provide a value for option {sys.argv[opt_idx]}")
            return False
        elif not exists(sys.argv[opt_idx + 1]):
            print(f"\n   The path provided to {sys.argv[opt_idx]} doesn't exist")
            return False
        return True

    global config_location
    global chat_path_on_start
    global prompt_path_on_start
    global api_key_path

    for i in range(1, len(sys.argv), 2):
        if sys.argv[i] not in SHORT_OPTIONS and sys.argv[i] not in LONG_OPTIONS:
            write_colored_output("COMMAND ERROR", ANSI_RED, end='')
            print(f"\n   Invalid option `{sys.argv[i]}`")
            sys.exit(1)

        if not option_value_valid(i):
            sys.exit(1)

        if sys.argv[i] == '-f' or sys.argv[i] == '--config':
            config_location = sys.argv[i + 1]
        elif sys.argv[i] == '-c' or sys.argv[i] == '--chat':
            chat_path_on_start = sys.argv[i + 1]
        elif sys.argv[i] == '-p' or sys.argv[i] == '--prompt':
            prompt_path_on_start = sys.argv[i + 1]
        elif sys.argv[i] == '-k' or sys.argv[i] == '--key':
            api_key_path = sys.argv[i + 1]

parse_cmd_line_options()

def load_config(config_file_name: str) -> dict[str, any]:
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
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Malformed json in {config_file_name}:\n")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

    api_key_env_var = getenv('OPENAI_API_KEY', '')
    if api_key_env_var:
        config['api_key'] = api_key_env_var
    elif 'api_key_file' not in config and api_key_path == '':
        write_colored_output("API_KEY ERROR", ANSI_RED, end='')
        print(f": Must include either an ", end='', flush=True)
        write_colored_output(f"api_key_file", ANSI_GREEN, end='')
        print(" in config file,\n               have the ", end='', flush=True)
        write_colored_output(f"OPENAI_API_KEY", ANSI_GREEN, end='')
        print(f" environment variable set,\n               \
or have specified the key path with the ", end='', flush=True)
        write_colored_output(f"--key", ANSI_PURPLE, end='')
        print(" or ", end='', flush=True)
        write_colored_output(f"-k", ANSI_PURPLE, end='')
        print(" command line options.", flush=True)
        sys.exit(1)

    if 'model' not in config:
        config['model'] = DEFAULT_CONFIG_OPTIONS['model']

    if 'prompts_dir' not in config:
        config['prompts_dir'] = DEFAULT_CONFIG_OPTIONS['prompts_dir']
    else:
        if config['prompts_dir'][0] != '/':
            if config['prompts_dir'][-1:] == '/':
                config['prompts_dir'] = get_xdg_dir('XDG_DATA_HOME') + config['prompts_dir'][:-1]
            else:
                config['prompts_dir'] = get_xdg_dir('XDG_DATA_HOME') + config['prompts_dir']

    if 'chats_dir' not in config:
        config['chats_dir'] = DEFAULT_CONFIG_OPTIONS['chats_dir']
    else:
        if config['chats_dir'][0] != '/':
            if config['chats_dir'][-1:] == '/':
                config['chats_dir'] = get_xdg_dir('XDG_DATA_HOME') + config['chats_dir'][:-1]
            else:
                config['chats_dir'] = get_xdg_dir('XDG_DATA_HOME') + config['chats_dir']
    
    if 'token_usage_file' not in config:
        config['token_usage_file'] = DEFAULT_CONFIG_OPTIONS['token_usage_file']
    else:
        if config['token_usage'][0] != '/':
            config['token_usage_file'] = get_xdg_dir('XDG_DATA_HOME') + config['token_usage_file']

    if 'term_width' not in config:
        config['term_width'] = DEFAULT_CONFIG_OPTIONS['term_width']
    else:
        true_term_width = get_terminal_size().columns # os.get_terminal_size
        if config['term_width'] == 0 or config['term_width'] > true_term_width:
            config['term_width'] = true_term_width

    if 'colors' not in config:
        config['colors'] = DEFAULT_CONFIG_OPTIONS['colors']

    return config

CONFIG = load_config(config_location)
if api_key_path:
    openai.api_key_path = api_key_path
elif 'api_key' in CONFIG:
    openai.api_key = CONFIG['api_key']
else:
    openai.api_key_path = CONFIG['api_key_file']

def convert_hex_to_truecolor_ansi(color: str) -> str:
    r = int(color[1:3], base=16)
    g = int(color[3:5], base=16)
    b = int(color[5:7], base=16)
    return f"\x1b[38;2;{r};{g};{b}m"

def truecolor_ify(msg_to_print: str, color: str) -> str:
    return convert_hex_to_truecolor_ansi(color) + msg_to_print + '\x1b[0m'

TRUECOLOR_PATTERN = re.compile(r'\x1b\[([\d;]*)([A-Za-z])')
def len_truecolor(truecolor_string: str) -> int:
    return len(TRUECOLOR_PATTERN.sub('', truecolor_string))

def center_truecolor(truecolor_string: str, width=CONFIG['term_width']):
    length = len_truecolor(truecolor_string)
    if length >= width:
        return truecolor_string
    padding = ' ' * floor((width - length) / 2)
    return padding + truecolor_string + padding

def rjust_truecolor(truecolor_string: str, width=CONFIG['term_width']):
    length = len_truecolor(truecolor_string)
    if length >= width:
        return truecolor_string
    return (' ' * (width - length)) + truecolor_string

def split_string_into_len_n_substrings(input_string: str, n: int) -> list[str]:
    return [input_string[i:i+n] for i in range(0, len(input_string), n)]

def wrap_truecolor_text(text: str, width_box: (int, int), pos: int) -> list[str]:
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
    wrapped_text.append(line)
    wrapped_text = [line for line in wrapped_text if line]
    return wrapped_text

# use xclip to put the last chat completion in the clipboard
def set_clipboard_text(text: str) -> None:
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
    try:
        res = [filename[:-7] for filename in listdir(prompts_dir) if filename.endswith('.prompt')]
    except FileNotFoundError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't find directory ", end='', flush=True)
        write_colored_output(f"{prompts_dir}", ANSI_GREEN, end='\n')
        sys.exit(1)
    return res

def load_prompt(prompt_path: str) -> str:
    try:
        with open(prompt_path, 'r') as prompt_file:
            prompt = prompt_file.read()
    except IOError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't read ", end='', flush=True)
        write_colored_output(f"{prompt_path}", ANSI_GREEN, end='\n')
        sys.exit(1)
    print(f'\n   Loaded prompt at {truecolor_ify(prompt_path, CFG_COLOR)}')
    return prompt

def load_prompt_from_name(prompt_name: str, prompts_dir: str) -> str:
    prompt_file_name = prompt_name + '.prompt'
    prompt_path = join(prompts_dir, prompt_file_name)  # os.path.join
    return load_prompt(prompt_path)

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
    try:
        res = [filename[:-5] for filename in listdir(chats_dir) if filename.endswith('.chat')]
    except FileNotFoundError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't find directory ", end='', flush=True)
        write_colored_output(f"{chats_dir}", ANSI_GREEN, end='\n')
        sys.exit(1)
    return res

def load_chat(chat_path: str) -> str:
    try:
        with open(chat_path, 'r') as chat_file:
            chat = loads(chat_file.readline())
    except IOError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't read ", end='', flush=True)
        write_colored_output(f"{chat_path}", ANSI_GREEN, end='\n')
        sys.exit(1)
    print(f'\n   Loaded chat at {truecolor_ify(chat_path, CFG_COLOR)}')
    return chat

def load_chat_from_name(chat_name: str, chats_dir: str) -> list[dict[str,str]]:
    chat_file_name = chat_name + '.chat'
    chat_path = join(chats_dir, chat_file_name)  # os.path.join
    return load_chat(chat_path)

def save_chat(messages: list[dict[str, str]], chat_name: str) -> None:
    chat_file_name = chat_name + '.chat'
    save_path = join(CONFIG['chats_dir'], chat_file_name)  # os.path.join
    color_chats_dir = truecolor_ify('$chats_dir', CFG_COLOR)
    try:
        with open(save_path, 'w') as outfile:
            dump(messages, outfile) # json.dump
    except IOError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't write to ", end='', flush=True)
        write_colored_output(f"{color_chats_dir}{chat_file_name}", ANSI_GREEN, end='\n')
    print(f"\n   Saved to {color_chats_dir}/{chat_file_name}")

def load_token_usage(token_usage_file_name: str) -> dict[str, int]:
    try:
        with open(token_usage_file_name, 'r') as token_usage_file:
            token_usage = loads(token_usage_file.readline())
    except IOError:
        write_colored_output("CONFIG ERROR", ANSI_RED, end='')
        print(f": Couldn't read ", end='', flush=True)
        write_colored_output(f"{token_usage_file_name}", ANSI_GREEN, end='\n')
        sys.exit(1)
    return token_usage

def account_token_usage(request_token_usage: dict[str, int]) -> None:
    pass


token_usage = load_token_usage(CONFIG['token_usage_file'])
session_token_usage = { "completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0 }

prompt_names = load_prompt_names(CONFIG['prompts_dir'])
def list_saved_prompts() -> None:
    print(flush=True)
    for i, name in enumerate(prompt_names):
        print(f"   {i+1}. {name}")
    print(flush=True)

chat_names = load_chat_names(CONFIG['chats_dir'])
def list_saved_chats() -> None:
    print(flush=True)
    for i, name in enumerate(chat_names):
        print(f"   {i+1}. {name}")
    print(flush=True)

CMD_COLOR = CONFIG['colors']['blue']
CFG_COLOR = CONFIG['colors']['green']

commands = { 'exit':         "exit simple-chat-gpt-cli", 
             'help':         "display the message you are currently reading.",
             'clip':         "store the contents of the last chat completion in the clipboard.", 
             'prompt new':   "create a new prompt and begin using it.", 
             'prompt list': f"list the saved prompts located in your {truecolor_ify('prompts_dir', CFG_COLOR)}", 
             'prompt load': f"load a saved prompt from your {truecolor_ify('prompts_dir', CFG_COLOR)}",
             'save':         "save the current chat history.",
             'chat new':     "begin a new chat",
             'chat list':   f"list the saved chats located in your {truecolor_ify('chats_dir', CFG_COLOR)}", 
             'chat load':   f"load a saved chat from your {truecolor_ify('chats_dir', CFG_COLOR)}" }

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
    print('Welcome to simple-chat-gpt-cli'.center(CONFIG['term_width']))
    print(center_truecolor(f"\ttype {truecolor_ify('exit', CMD_COLOR)} to exit, or \
{truecolor_ify('help', CMD_COLOR)} for a list of commands"))
    print(flush=True)


def print_help_message() -> None:
    command_name_total_space = int(CONFIG['term_width'] * 0.35)
    for command_name in commands:
        colored_command = truecolor_ify(command_name, CMD_COLOR)
        usage_split = wrap_truecolor_text(commands[command_name], 
                                (command_name_total_space + 2, CONFIG['term_width']), 
                                command_name_total_space + 2)
        print(rjust_truecolor(colored_command, width=(command_name_total_space)), end='')
        print(f"  {usage_split[0]}")
        if len(usage_split) == 0:
            return
        for s in usage_split[1:]:
            print(f"{' ' * (command_name_total_space + 2)}{s}")
    print(flush=True)



CLI_PROMPT = f"{truecolor_ify('   >>> ', CONFIG['colors']['yellow'])}"
def print_cli_prompt() -> None:
    print(CLI_PROMPT, end='')

START_CURSOR = 7  # aligns with the user's cli prompt
END_CURSOR = CONFIG['term_width'] - 7
def print_response_lpad() -> None:
    print(f"{' ' * START_CURSOR}", flush=True, end='')

def ask_save_prompt(prompt: str) -> None:
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
        save_prompt(prompt, prompt_name, CONFIG['prompts_dir'])
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

def ask_selection(n_selections: int) -> int:
    selected_n = 0
    while True:
        print_cli_prompt()
        selected_n = input()
        if not selected_n.isdigit():
            print("\n   Must enter number.")
            continue
        if int(selected_n) not in range(1, n_selections + 1):
            print("\n   Selection not in appropriate range.")
            continue
        else:
            break
    assert(selected_n != 0)
    return int(selected_n)

def confirm() -> bool:
    print_cli_prompt()
    are_you_sure = input()
    return are_you_sure in ['y', 'yes']

def enter_prompt(messages: list[dict[str, str]]) -> None:
    print('Enter your prompt:'.center(CONFIG['term_width'])); print(flush=True)
    print_cli_prompt()
    prompt = input()
    ask_save_prompt(prompt)
    apply_prompt_to_messages(messages, prompt)

def apply_prompt_to_messages(messages: list[dict[str, str]], prompt: str) -> None:
    for i, message in enumerate(messages):
        if message['role'] == 'system':
            messages[i]['content'] = prompt
            return
    messages = [ {'role': 'system', 'content': prompt}, *messages ]



# BEGIN APP FUNCTIONALITY

print_startup_message()
        
messages = [{'role': 'system', 'content': ''}]

if chat_path_on_start:
    messages = load_chat(chat_path_on_start)

if prompt_path_on_start:
    prompt = load_prompt(prompt_path_on_start)
    apply_prompt_to_messages(messages, prompt)

last_response = ''
while True:
    print_cli_prompt()
    # FIXME: Pasting in messages with newlines breaks this
    message = input()
    if message == '':
        print(flush=True)
        continue 

    closest_command = find_similar_command_name(message)
    if closest_command:
        print(center_truecolor(f"Did you mean {truecolor_ify(closest_command, CMD_COLOR)}?", CONFIG['term_width']))
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
{truecolor_ify('clip', CMD_COLOR)}", CONFIG['term_width']))
                continue
            set_clipboard_text(last_response)
            continue
        elif split_message[0] == 'prompt':
            if split_message[1] == 'new':
                chat_type = 'current'
                if last_response:
                    print('\n   Start new chat? y/n')
                    if confirm():
                        chat_type = 'new'
                        messages = []
                enter_prompt(messages)
                print(f"\n   Prompt applied to {chat_type} chat.")
                continue
            elif split_message[1] == 'list':
                if len(prompt_names) == 0:
                    print(f"\n   No prompts located in {truecolor_ify(CONFIG['prompts_dir'], CFG_COLOR)}")
                    continue
                list_saved_prompts()
                continue
            elif split_message[1] == 'load':
                if len(prompt_names) == 0:
                    print(f"\n   No prompts located in {truecolor_ify(CONFIG['prompts_dir'], CFG_COLOR)}")
                    continue
                if last_response:
                    print('\n   Start new chat? y/n')
                    if confirm():
                        messages = []
                        continue
                list_saved_prompts()
                selected_prompt_n = ask_selection(len(prompt_names))
                selected_prompt_name = prompt_names[int(selected_prompt_n) - 1]
                prompt = load_prompt_from_name(selected_prompt_name, CONFIG['prompts_dir'])
                apply_prompt_to_messages(messages, prompt)
                continue
        elif split_message[0] == 'save':
            ask_save_chat()
            continue
        elif split_message[0] == 'chat':
            if split_message[1] == 'list':
                if len(chat_names) == 0:
                    print(f"\n   No chats located in {truecolor_ify(CONFIG['chats_dir'], CFG_COLOR)}")
                    continue
                list_saved_chats()
                continue
            elif split_message[1] == 'load':
                if len(chat_names) == 0:
                    print(f"\n   No chats located in {truecolor_ify(CONFIG['prompts_dir'], CFG_COLOR)}")
                    continue
                if last_response:
                    print('\n   Leave current chat? y/n')
                    if not confirm():
                        print('\n   Not starting new chat.')
                        continue
                list_saved_chats()
                selected_chat_n = ask_selection(len(chat_names))
                selected_chat_name = chat_names[int(selected_chat_n) - 1]
                messages = load_chat_from_name(selected_chat_name, CONFIG['chats_dir'])
                continue
            elif split_message[1] == 'new':
                print('\n   Leave current chat? y/n')
                if confirm():
                    prompt = ''
                    print('\n   Include prompt? y/n')
                    if confirm():
                        if len(prompt_names) > 0:
                            print('\n   Use existing prompt? y/n')
                            if confirm():
                                list_saved_prompts()
                                selected_prompt_n = ask_selection(len(chat_names))
                                selected_prompt_name = prompt_names[int(selected_prompt_n) - 1]
                                prompt = load_prompt_from_name(selected_prompt_name, CONFIG['prompts_dir'])
                            else:
                                enter_prompt(messages)
                        else:
                            enter_prompt(messages)
                        messages = [{'role':'system', 'content': prompt}]
                print('\n   Begin new chat')
                continue
            

    messages.append({"role": "user", "content": message})

    try:
        response = openai.ChatCompletion.create(
            model=CONFIG['model'],
            messages=messages,
            temperature=0,
            stream=True)
    except Exception as ex:
        print(f"\n   Something went wrong: {truecolor_ify(str(ex), CONFIG['colors']['red'])}\n")
        sys.exit(1)

    cursor = START_CURSOR

    collected_chunks = []
    collected_messages = []
    chunk_tokens = 0

    print(flush=True)
    print_response_lpad()
    for chunk in response:
        collected_chunks.append(chunk)  
        chunk_delta = loads(f"{chunk['choices'][0]['delta']}")

        chunk_tokens = 0
        if "role" in chunk_delta:
            continue
        elif "content" in chunk_delta:
            chunk_message = chunk_delta["content"]
            collected_messages.append(chunk_message)  

            # this feels hacky, but after viewing many tokens from generated responses,
            # I have yet to see a space not be at the beginning of the token.
            if ' ' in chunk_message and cursor > END_CURSOR:
                print(flush=True)
                print_response_lpad()
                chunk_message = chunk_message[1:] # remove the leading space for alignment
                cursor = START_CURSOR
            cursor += len(chunk_message)

            chunk_tokens += 1
            print(chunk_message, end='', flush=True)

            if '\n' in chunk_message:
                cursor = START_CURSOR
                print_response_lpad()

    last_response = ''.join(collected_messages)
    messages.append({"role": "assistant", "content": last_response})
    session_token_usage["completion_tokens"] += chunk_tokens
    print('\n\n', end='')

