# Simple Chat GPT CLI
> A simple CLI tool to use Chat GPT Chat Completions in the terminal

### Setup
> To get started, add the file location of your API key to `config.json`, then run
> ```
> chmod +x setup.sh && ./setup.sh
> ```
> and finally you can
> ```
> python3 chat.py
> ```

### Capabilities
> 1. Save and switch between prompts.
> 2. Save and switch between chats.
> 3. Store the contents of the last response in the clipboard using `xclip`.

### Configuration
> Only the `openai_key_file` config option is required.
> See `example_config.json` for available configuration options.

**TODO**
> 1. Handle standard readline commands.
> 2. Account the token usage.
> 3. Add functionality to stop response from generating
> 4. Package `chat.py` into a static binary that can be added to the user's `PATH`

**FIXME**
> 1. Cannot paste multi-line input.
