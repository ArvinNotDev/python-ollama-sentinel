# Ollama Sentinel

A polished desktop workspace for local Ollama models and remote AI API providers. Built with PySide6, Ollama's streaming API and provider-specific adapters.

**Current scope:** local model discovery/download, streaming local chat, saved remote API connections and streaming remote chat. Agentic workflows, tools, autonomous task execution and project agents are intentionally not part of this release.

## Features

- Local Ollama model discovery, pull progress, installed model library and model removal.
- Chat with local Ollama models or connected remote API models from one model selector.
- Multiple saved API connections: OpenAI, Anthropic (Claude), Google (Gemini) and OpenAI-compatible endpoints.
- Fetch provider model lists or enter model IDs manually.
- Test provider connectivity before using a connection.
- Stream responses from OpenAI-compatible Chat Completions, Anthropic Messages and Gemini generate-content APIs.
- API keys stored in the operating system credential manager through Python Keyring. Secrets are not written to settings.json.
- Rounded dark desktop UI, sidebar navigation, provider settings and responsive settings page.
- Choose the model folder used by an Ollama server launched from the app.

## Supported providers

| Provider | API protocol | Default base URL |
|---|---|---|
| OpenAI | Chat Completions | https://api.openai.com/v1 |
| Anthropic / Claude | Messages API | https://api.anthropic.com |
| Google / Gemini | Gemini generateContent | https://generativelanguage.googleapis.com/v1beta |
| OpenAI-compatible | Chat Completions | User-defined |

The OpenAI-compatible option can connect to services that expose the compatible /models and /chat/completions endpoints, such as OpenRouter, Groq, Together, vLLM, LM Studio and many hosted inference gateways. Provider compatibility varies; a model ID can always be entered manually if a service does not expose model discovery.

## API keys and subscriptions

Create API credentials with the provider and add them under **Settings → AI API providers**. API keys are stored in the OS credential manager (Windows Credential Manager, macOS Keychain or a supported Linux Secret Service); only the connection metadata and model IDs are stored in the application's JSON settings file.

A provider API key is not the same thing as a consumer ChatGPT/Codex or Claude Pro/Max subscription login. API usage is billed and rate-limited separately according to the provider account. This application currently supports API-key authentication, not OAuth sign-in to consumer subscriptions.

For cloud models, prompts and conversation history are sent to the selected provider. Review the provider's privacy and retention terms before sending sensitive information. Local Ollama models continue to run through the configured Ollama server.

## Requirements

- Python 3.10 or newer
- Ollama installed for local models
- An API key for each cloud provider that requires authentication
- Windows, macOS or Linux desktop environment

## Run from source

1. Create a virtual environment: python -m venv .venv
2. Activate it:
   - Windows: .venv\Scripts\activate
   - macOS/Linux: source .venv/bin/activate
3. Install dependencies: pip install -r requirements.txt
4. Start: python main.py

## Add an API provider

1. Open **Settings → AI API providers**.
2. Select OpenAI, Anthropic · Claude, Google · Gemini or OpenAI-compatible.
3. Give the connection a name, check the base URL and paste the API key (not needed for compatible endpoints that do not require authentication).
4. Save the connection, then use **Fetch models** to retrieve the available model IDs. You can also add model IDs manually, one per line.
5. Return to Chat and select the model from the dropdown. Connected providers are shown alongside local Ollama models.

Each saved connection can have its own base URL and model list. Add multiple profiles for separate accounts, gateways or local compatible servers.

## Model storage location

Ollama owns its model storage. Sentinel configures OLLAMA_MODELS only when it launches an Ollama server itself:

1. Open Settings → Model storage and choose a folder.
2. Save settings.
3. Stop any already-running Ollama desktop app or service.
4. Use **Launch Ollama with this folder**.

An already-running server is not silently reconfigured. The selected folder is applied to the app-managed local server only; cloud provider models are not downloaded or stored locally by Sentinel.

## Project structure

- core/ollama/ — local Ollama REST API and process manager
- core/providers.py — remote provider adapters and streaming protocols
- core/secrets.py — OS credential store integration
- core/settings.py — persistent application settings and provider profiles
- ui/main_window.py — navigation shell and application coordination
- ui/workers.py — background API, pull and chat workers
- ui/pages/chat_page.py — unified local/cloud model chat
- ui/pages/models_page.py — local model discovery and downloads
- ui/pages/settings_page.py — provider, connection and storage settings

## Roadmap

- Agentic runtime and task planning
- Tool permissions and controlled execution
- Project/workspace context management
- Agent activity, approvals and audit history

These items are future work and are not enabled in the current application.
