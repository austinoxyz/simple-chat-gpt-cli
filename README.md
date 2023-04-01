# Simple Chat GPT CLI
> A simple CLI tool to use Chat GPT Chat Completions in the terminal

### Setup
> To get started, you must first let `chat.py` where to find your `OPENAI_API_KEY`. 
> You can either add the file location of your API key to `config.json`,
> or have the `OPENAI_API_KEY` environment variable set. Then, run
> ```
> chmod +x setup.sh && ./setup.sh
> ```
> and finally you can
> ```
> python3 chat.py
> ``````

### Capabilities
> 1. Save and switch between prompts.
> 2. Save and switch between chats.
> 3. Store the contents of the last response in the clipboard using `xclip`.

### Configuration
> Only the `openai_key_file` config option is required.
> See `example_config.json` for available configuration options.
> Both relative and absolute paths will be accepted.

