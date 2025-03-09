Added three free models:

Ollama - local server for running models (requires installation on your server):

Llama 2 - universal model with a good balance of performance Mistral - a newer and more efficient model

Hugging Face - API with free limitations:

Uses the Mistral-7B-Instruct model

Google Gemini (former PaLM):

Has a free usage tier

Additional improvements:

Per-user model selection:

Added /model command to select a preferred model The choice is saved in the database

Advanced bot commands:

/start - initial greeting /clear - clear chat history /help - help on commands

Improved interface:

Buttons for selecting a model

To use the code you need to:

Install Ollama on your server for local models (https://ollama.ai/) Get a free Hugging Face API key (https://huggingface.co/settings/tokens) Get a free Google Gemini API key (https://ai.google.dev/) Add these keys to your .env file: CopyHUGGINGFACE_API_KEY=your_key GOOGLE_AI_API_KEY=your_key OLLAMA_HOST=http://localhost:11434 # or your Ollama server URL

All other bot logic (payments, request limits, chat history) is preserved as in the original code. RetryClaude does not have the ability to run the code it generates yet. Claude does not have internet access. Links provided may not be accurate or up to date.
