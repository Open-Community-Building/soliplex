# Docker Setup for Soliplex Flutter Web

This directory contains Docker configuration for building and running the Soliplex Flutter web application.

## Files

- `Dockerfile` - Multi-stage build that compiles Flutter web and serves it with nginx
- `docker-compose.yml` - Orchestration for production and development environments
- `.dockerignore` - Excludes unnecessary files from the Docker build context

## Usage

### Production Build

Build and run the production web server:

```bash
cd docker
docker-compose up --build
```

The web application will be available at `http://localhost:8080`

### Development with Hot Reload

Run the development server with hot reload:

```bash
cd docker
docker-compose --profile dev up dev
```

The development server will be available at `http://localhost:8081`

## Building the Docker Image Directly

To build the Docker image without docker-compose:

```bash
docker build -f docker/Dockerfile -t soliplex-web .
docker run -p 8080:80 soliplex-web
```
