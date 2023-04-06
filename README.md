# Simple Chat GPT CLI
> A simple CLI tool to use ChatGPT Chat Completions in the terminal

![Picture showing sample use of the cli tool.](res/simple-chat.png)

### Setup
To get started, you must first let `chatgpt.py` know where to find your `OPENAI_API_KEY`. 

You can either add the file location of your API key to `config.json` with the key `api_key_file`
or have the `OPENAI_API_KEY` environment variable set. 

Then, run
```
chmod +x setup.sh && ./setup.sh
``````
and finally you can
```
python3 chatgpt.py
``````

Alternatively, to use this without having to `cd` into the directory containing `chatgpt.py`,
you can run
```
chmod +x build-static-binary.sh && ./build-static-binary.sh
``````
This will put a static binary named `chatgpt` into the your `$HOME/.local/bin`, allowing
you to simply `chatgpt` and begin chatting.
NOTE: This requires `nuitka` to be installed via `pip`

### Capabilities
1. Save and switch between prompts.
2. Save and switch between chats.
3. Store the contents of the last response in the clipboard using `xclip`.

### Configuration
See `example_config.json` for available configuration options.
Both relative and absolute paths will be accepted.

### Command Line Options
1. `--key` or `-k`: The path to the `OPENAI_API_KEY` file that you would like to use.
2. `--chat` or `-c`: The file containing the message history of the chat to load on startup.
3. `--prompt` or `-p`: The file containing the prompt to load on startup.
4. `--config` or `-f`: The file configuration file to use.

