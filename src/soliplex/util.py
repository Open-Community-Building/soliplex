import os
import typing


def scrub_private_keys(
    json_dict: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    """Return a copy of 'json_dict' with private keys removed

    'json_dict'
        the dict to be copied
    """
    scrubbed = {}
    for key, value in json_dict.items():
        if not key.startswith("_"):
            if isinstance(value, dict):
                value = scrub_private_keys(value)
            if isinstance(value, list):
                if value and isinstance(value[0], dict):
                    value = [
                        scrub_private_keys(item) for item in value
                    ]
            scrubbed[key] = value
    return scrubbed


def interpolate_env_vars(source: str) -> str:
    """Interplate environment variables into a string

    'source'
        the string containing potential format replacements to be
        filled using environment variables
    """
    if not source.startswith("env:"):
        return source

    stripped = source[len("env:"):]

    return stripped.format(**os.environ)
