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

4. Check for missing secrets / environment varisables:
   ```bash
   soliplex-cli --installation-path example check_config
   ```bash

5. Configure any missing secrets, e.g. using a `.env` file.


## Running the Server

Start the FastAPI server with auto-reload:

```bash
soliplex-cli --installation-path example serve
```

The server will be available at `http://localhost:8000` by default.

## API Endpoints

The server provides various endpoints for:
- Chat completions
- RAG queries
- Document management
- Authentication
