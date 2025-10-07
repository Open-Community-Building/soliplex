# Server Setup

The Soliplex server is a FastAPI-based backend that forwards requests
to OpenAI and provides RAG functionality.

## Prerequisites

- Python 3.13+
- Access to OpenAI API (API key required) or Ollama.

## Installation

1. Clone the repository:
   ```bash
   git clone git@github.com:soliplex/soliplex.git
   cd soliplex/
   ```

2. Set up your environment variables:
   ```bash
   cat > .env
   OPENAI_API_KEY=sk-....
   # Press Ctrl+C to exit
   ```

3. Install dependencies:
   ```bash
   pip install -e .
   ```

## Running the Server

Start the FastAPI server with auto-reload:

```bash
uvicorn factory:soliplex.main:create_app --reload
```

The server will be available at `http://localhost:8000` by default.

## API Endpoints

The server provides various endpoints for:
- Chat completions
- RAG queries
- Document management
- Authentication
