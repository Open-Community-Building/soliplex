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

4. Check for missing secrets / environment variables:
   ```bash
   soliplex-cli check_config example/
   ```

5. Configure any missing secrets, e.g. by sourcing a `.env` file, or
   by exporting them directly. (Note the related issue about whether
   `soliplex` should support using a `.env` file to define secrets:
   https://github.com/enfold/soliplex/issues/89 .)

6.  Configure any missing environment varibles, e.g. by editing
    the installation YAML file, adding them to a `.env` file in the
    installation path, or exporting them directly.


## Running the Server

Start the FastAPI server with auto-reload:

```bash
soliplex-cli serve example -r both
```

The server will be available at `http://localhost:8000` by default.

## API Endpoints

If the `soliplex-cli` server is running, you can browse the
[live OpenAPI documentation](http://localhost:8000/docs).
