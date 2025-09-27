# Installation Directory

An "installation" is a set of filesystem-based configuration files, organized
as a directory tree.

## Installation Filesystem Layout

At the root of an installation directory is a file, `installation.yaml`, which
is used to configure environment variables and secrets used by the
installation.  There may be alternative configrations available, e.g. to
configure how the installation runs inside a container.

An installation directory typically containts subdirectories, each holding
configurations for a given type of entity.

Example layout:

```
/
  installation.yaml
  completions/
    chat-bot/
      completion_config.yaml
      prompt.txt
    ...
  oidc/
    cacert.pem
    config.yaml
  quizzes/
    quiz_name.json
    ...
  rooms/
    quiztest/
      prompt.txt
      room_config.yaml
    ...
```

### OIDC Provier Configuration Filesystem Layout

This directory contains configuration files defining the OIDC identity
providers configured for use in this installation.

See `example/oidc/README.md` for documentation on the contents and
schema of these files.


### Quiz Configuration Filesystem Layout

This directory contains question sets as individual JSON files, derived
from the evaluation dataset entries.

See `example/quizzes/README.md` for documentation on the contents and
schema of these files.

### Completions Endpoint Configuration Filesystem Layout

Within a "completions" directory, each endpoint is represented by a
subdirectory, whose name is the endpoint ID.

Within that subdirectory should be one or two files:

- `completion_config.yaml` holds metadata about the endpoint (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the endpoint.

See `example/completions/README.md` for documentation on the contents and
schema of these files.

### Room Configuration Filesystem Layout

Within a "rooms" directory, each room is represented by a subdirectory,
whose name is the room ID.

Within that subdirectory should be one or two files:

- `room_config.yaml` holds metadata about the room (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the room.

- A logo image file (optional)

See `example/rooms/README.md` for documentation on the contents and
schema of these files.
