# Server Setup

The Soliplex server is a FastAPI-based backend that forwards requests
to OpenAI and provides RAG functionality.

## Prerequisites

- Python 3.13+
- Access to LLM:
   - OpenAI - an API key is required to use OpenAI
   - Ollama  ([https://ollama.com/] https://ollama.com/)
- Logfire (optional) - A token from logfire ( [https://logfire-us.pydantic.dev/login](https://logfire-us.pydantic.dev/login) ) allows for visibility into the application. (see [ https://logfire.pydantic.dev/docs/integrations/web-frameworks/fastapi/](https://logfire.pydantic.dev/docs/integrations/web-frameworks/fastapi/) for more information)

## Installation

1. Clone the repository:
   ```bash
   git clone git@github.com:soliplex/soliplex.git
   cd soliplex/
   ```

2. Set up a Python3 virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install --upgrade setuptools pip
   ```

3. Install `soliplex` and its dependencies:
   ```bash
   pip install -e .
   ```
4. Set up environment variables:

   An environment file can be used to configure secrets.  For logfire, create a .env file with
   ```
   LOGFIRE_TOKEN=<your_token_here>
   ```
## Running the example

The example configuration provides an overview of how a soliplex application is assembled.  It includes a number of rooms that 

1. Configure resources:
   The example needs access to a model server using either openapi or ollama as well as access to example MCP services. The example uses [https://smithery.ai/](https://smithery.ai/) but others can be configured.
   ```
   SMITHERY_AI_API_KEY=<your key>
   SMITHERY_AI_PROFILE=<your profile>
   OLLAMA_BASE_URL=http://localhost:11434
   OPENAI_API_KEY=<your key>
   ```
   a. OIDC configuration:
   TODO
2. Configure Ollama:
   The example configuration uses the qwen3 model.  To install:
   ```bash
   ollama pull qwen3:latest
   ```

3. Check for missing secrets / environment variables:
   This command will check the server for any missing variables or invalid configuration files.
   ```bash
   soliplex-cli check-config example/installation.yaml
   ```




## Running the Server

Start the FastAPI server with auto-reload:

```bash
soliplex-cli serve example/installation.yaml -r both
```

The server will be available at `http://localhost:8000` by default.

For testing purposes, the server can be run with authentication disabled. To run without authentication:
```bash
soliplex-cli serve example/no_auth.yaml -r both
```

To confirm your room configuration:
```bash
curl -X 'GET' \
  'http://127.0.0.1:8000/api/v1/rooms' \
  -H 'accept: application/json'
```

## API Endpoints

If the `soliplex-cli` server is running, you can browse the
[live OpenAPI documentation](http://localhost:8000/docs).
