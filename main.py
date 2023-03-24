# main.py

# Refererence URL
# https://github.com/openai/openai-cookbook/blob/main/examples/How_to_stream_completions.ipynb

# Example of an OpenAI ChatCompletion request with stream=True
# https://platform.openai.com/docs/guides/chat': '

import sys
import time
import json
import openai

model = 'gpt-3.5-turbo'
api_key_file_name = "./openai_key_file"
openai.api_key_path = api_key_file_name
total_token_usage = { }

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BLUE = '\033[34m'
RESET = '\033[0m'

def write_colored_output(output, color, end='\n'):
    sys.stdout.write(color + output + RESET + end)

def account_token_usage(request_token_usage):
    global total_token_usage
    total_token_usage["completion_tokens"] += request_token_usage["completion_tokens"]
    total_token_usage["prompt_tokens"] += request_token_usage["prompt_tokens"]
    total_token_usage["total_tokens"] += request_token_usage["total_tokens"]

def load_config(config_file_name):
    # read config file
    try:
        json_raw = ''
        with open(config_file_name, 'r') as config_file:
            json_raw += config_file.read()
        config_raw = json.loads(json_raw)
    except IOError:
        print(f"Couldn't read {config_file_name}. Wheres your config?")
        sys.exit(1)
    except JSONDecodeError:
        print(f"Malformed json in {config_file_name}:")
        import traceback
        print(traceback.format_exc())

    # read api key
    try:
        api_key_file_name = config_raw["api_key_file"]
        with open(api_key_file_name, 'r') as api_key_file:
            key = api_key_file.readline()
    except IOError:
        print(f"Couldn't read {api_key_file_name}. Check your config!")
        sys.exit(1)

    # read token usage
    try:
        token_usage_file_name = config_raw["token_usage_file"]
        with open(token_usage_file_name, 'r') as token_usage_file:
            token_usage = json.loads(token_usage_file.readline())
    except IOError:
        print(f"Couldn't read {token_usage_file_name}. Check your config!")
        sys.exit(1)

    config["api_key"] = key
    return config, token_usage


config = {}
config_file_name = 'example_config.json'
config, token_usage = load_config(config_file_name )

print('Welcome to gpt-3.5 cli')
print('type `exit` to exit')

while True:
    write_colored_output("> ", YELLOW, end='')
    message = input()
    if message == 'exit':
        break

    start_time = time.time()
    response = openai.ChatCompletion.create(
        model=model,
        messages=[{'role': 'user', 'content': f'{message}'}],
        temperature=0,
        stream=True
    )

    collected_chunks = []
    collected_messages = []

    for chunk in response:
        chunk_time = time.time() - start_time  # calculate the time delay of the chunk
        collected_chunks.append(chunk)  # save the event response
        chunk_json = json.loads(f"{chunk['choices'][0]['delta']}")

#        print("keys:")
#        for key in chunk_json.keys():
#            print(key)

        if "role" in chunk_json:
            pass
        elif "content" in chunk_json:
            chunk_message = chunk_json["content"]
            collected_messages.append(chunk_message)  # save the message
            print(chunk_message, end='', flush=True)

    print()
print(f'\nConversation ended.\nTotal token usage:\n{token_usage}')
    




#    print(f"{chunk_message}")

