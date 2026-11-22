# Ollama Sentinel

A polished desktop workspace for local Ollama models and remote AI API providers, with local Whisper voice input. Built with PySide6, Ollama's streaming API, provider-specific adapters and faster-whisper.

**Current scope:** local model discovery/download, local and remote chat, saved remote API connections, and on-device speech-to-text. Agentic workflows, tools, autonomous task execution and project agents are intentionally not part of this release.

## Features

- Local Ollama model discovery, pull progress, installed model library and model removal.
- Chat with local Ollama models or connected remote API models from one model selector.
- Multiple saved API connections: OpenAI, Anthropic (Claude), Google (Gemini) and OpenAI-compatible endpoints.
- API keys stored in the operating system credential manager.
- Free multilingual Whisper models downloaded to a configurable local folder.
- Voice Studio for recording speech, local transcription, language selection, editing, copying and inserting transcripts into Chat.
- Chat microphone push-to-talk: record, transcribe locally, insert the words into the message composer, then review and send to either a local or cloud model.
- Circular microphone download indicator showing model download progress. If the selected Whisper model is missing, Sentinel asks before downloading it.
- CPU int8 transcription by default for broad hardware compatibility. The first transcription loads the model into memory; subsequent dictation reuses it.
- Rounded dark desktop UI, sidebar navigation, provider settings and responsive settings page.
- Choose the model folder used by an Ollama server launched from the app.

## Local voice models

Sentinel uses multilingual Whisper models converted to CTranslate2 format by the faster-whisper project. They run locally after download; no speech-to-text API key or cloud transcription service is required.

| Model | Suggested use |
|---|---|
| tiny | Fastest and smallest; quick dictation |
| base | Balanced default for everyday voice input |
| small | Better recognition with more memory use |
| medium | Higher accuracy and higher resource use |
| large-v3 | High-accuracy multilingual transcription |
| large-v3-turbo | Fast large-v3 Turbo checkpoint |
| distil-large-v3 | Distilled large-model option |

The available model repositories are provided by [SYSTRAN faster-whisper](https://github.com/SYSTRAN/faster-whisper) and hosted on the [Hugging Face model hub](https://huggingface.co/Systran). These are open-source Whisper model conversions; review the upstream model and repository licenses before redistribution.

## Voice input workflow

1. Open Settings → Voice input and choose the model folder, default Whisper size and language.
2. Open Voice Studio to download a model manually, or press the microphone in Chat.
3. If the selected model is not installed, Sentinel asks before downloading it. During the download, a circular progress ring appears around the microphone button.
4. When the download completes, microphone recording starts. Press the microphone again to stop.
5. Sentinel transcribes the recording locally and inserts the recognized words into the Chat composer. Review or edit the text, then send it to the currently selected Local or API model.

Voice Studio also provides a transcript editor, Copy and Insert into Chat actions. Language can be set to automatic detection, Persian or English. The Whisper models listed above are multilingual; do not select an English-only checkpoint when transcribing Persian.

The default speech model is **base**. Models are stored separately from Ollama's own model directory, under the app's local-data folder by default. Choose a different Voice models folder in Settings at any time. Existing model folders are not moved automatically when changing this setting.

## Supported remote providers

| Provider | API protocol | Default base URL |
|---|---|---|
| OpenAI | Chat Completions | https://api.openai.com/v1 |
| Anthropic / Claude | Messages API | https://api.anthropic.com |
| Google / Gemini | Gemini generateContent | https://generativelanguage.googleapis.com/v1beta |
| OpenAI-compatible | Chat Completions | User-defined |

The OpenAI-compatible option can connect to services that expose compatible /models and /chat/completions endpoints, such as OpenRouter, Groq, Together, vLLM, LM Studio and many hosted inference gateways. Provider compatibility varies; a model ID can always be entered manually if a service does not expose model discovery.

## API keys and subscriptions

Create API credentials with the provider and add them under **Settings → AI API providers**. API keys are stored in the OS credential manager (Windows Credential Manager, macOS Keychain or a supported Linux Secret Service); only connection metadata and model IDs are stored in the application's JSON settings file.

A provider API key is not the same thing as a consumer ChatGPT/Codex or Claude Pro/Max subscription login. This application currently supports API-key authentication, not OAuth sign-in to consumer subscriptions. API usage is billed and rate-limited separately according to the provider account.

For cloud models, prompts and conversation history are sent to the selected provider. Voice recordings are transcribed locally by Whisper. If the resulting transcript is sent to a cloud model, that text is then sent to the selected provider. Review provider privacy and retention terms before sending sensitive information.

## Requirements

- Python 3.10 or newer
- [Ollama](https://ollama.com/download) for local LLMs
- A microphone for voice recording
- An API key for each cloud provider that requires authentication
- Windows, macOS or Linux desktop environment

## Run from source

1. Create a virtual environment: python -m venv .venv
2. Activate it:
   - Windows: .venv\Scripts\activate
   - macOS/Linux: source .venv/bin/activate
3. Install dependencies: pip install -r requirements.txt
4. Start: python main.py

The first Whisper model download requires internet access. Transcription itself works locally after the selected model has been downloaded.

## Model storage location

Ollama owns its model storage. Sentinel configures OLLAMA_MODELS only when it launches an Ollama server itself:

1. Open Settings → Model storage and choose a folder.
2. Save settings.
3. Stop any already-running Ollama desktop app or service.
4. Use **Launch Ollama with this folder**.

An already-running server is not silently reconfigured. The selected folder is applied to the app-managed local server only. Whisper models use their separate Voice models folder.

## Project structure

- core/ollama/ — local Ollama REST API and process manager
- core/providers.py — remote provider adapters and streaming protocols
- core/secrets.py — OS credential store integration
- core/settings.py — persistent application settings and provider profiles
- core/speech/whisper_manager.py — local Whisper model downloads and transcription
- ui/audio_recorder.py — local microphone capture through Qt Multimedia
- ui/mic_button.py — circular microphone button and model download progress ring
- ui/main_window.py — navigation shell and application coordination
- ui/workers.py — background API, model download and transcription workers
- ui/pages/chat_page.py — unified local/cloud chat and voice dictation
- ui/pages/voice_page.py — Voice Studio
- ui/pages/models_page.py — local LLM discovery and downloads
- ui/pages/settings_page.py — API providers, Ollama, Whisper and storage settings

## Roadmap

- Agentic runtime and task planning
- Tool permissions and controlled execution
- Project/workspace context management
- Agent activity, approvals and audit history

These items are future work and are not enabled in the current application.
