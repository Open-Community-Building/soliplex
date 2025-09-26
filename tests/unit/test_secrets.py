import contextlib
from unittest import mock

import pytest

from soliplex import config
from soliplex import secrets

SECRET_NAME = "TEST_SECRET"
ENV_VAR_NAME = "TEST_ENV_VAR"
SECRET_VALUE = "DEADBEEF"
ERROR_MISS = object()

NoRaise = contextlib.nullcontext()
EnvVarNotFound = pytest.raises(secrets.SecretEnvVarNotFound)
FilePathNotFound = pytest.raises(secrets.SecretFilePathNotFound)
SubprocessError = pytest.raises(secrets.SecretSubprocessError)
ExcGroup = pytest.raises(ExceptionGroup)


@pytest.mark.parametrize(
    "secret_name, env_var_name, env_patch, expectation, expected",
    [
        (SECRET_NAME, None, {}, EnvVarNotFound, ERROR_MISS),
        (SECRET_NAME, ENV_VAR_NAME, {}, EnvVarNotFound, ERROR_MISS),
        (
            SECRET_NAME,
            None,
            {SECRET_NAME: SECRET_VALUE},
            NoRaise,
            SECRET_VALUE,
        ),
        (
            SECRET_NAME,
            ENV_VAR_NAME,
            {SECRET_NAME: SECRET_VALUE},
            EnvVarNotFound,
            ERROR_MISS,
        ),
        (
            SECRET_NAME,
            ENV_VAR_NAME,
            {ENV_VAR_NAME: SECRET_VALUE},
            NoRaise,
            SECRET_VALUE,
        ),
    ],
)
def test_get_env_var_secret(
    secret_name,
    env_var_name,
    env_patch,
    expectation,
    expected,
):
    if env_var_name is None:
        source = config.EnvVarSecretSource(SECRET_NAME)
    else:
        source = config.EnvVarSecretSource(SECRET_NAME, ENV_VAR_NAME)

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        with expectation:
            found = secrets.get_env_var_secret(source)

        if expected is not ERROR_MISS:
            assert found == expected


@pytest.mark.parametrize(
    "file_path, expectation, expected",
    [
        ("/path/to/nowhere", FilePathNotFound, ERROR_MISS),
        ("./nonesuch", FilePathNotFound, ERROR_MISS),
        ("./secret_file", NoRaise, SECRET_VALUE),
    ],
)
def test_get_file_path_secret(temp_dir, file_path, expectation, expected):
    if file_path.startswith("."):
        write_file_path = temp_dir / file_path
        if expected is not ERROR_MISS:
            write_file_path.write_text(expected)

    source = config.FilePathSecretSource(
        SECRET_NAME,
        file_path,
        _config_path=temp_dir / "installation.yaml",
    )

    with expectation:
        found = secrets.get_file_path_secret(source)

    if expected is not ERROR_MISS:
        assert found == expected


@pytest.mark.parametrize(
    "command, args, expectation, expected",
    [
        ("/nowhere/not_executable", (), SubprocessError, ERROR_MISS),
        ("/bin/true", (), SubprocessError, ERROR_MISS),
        ("echo", [SECRET_VALUE], NoRaise, SECRET_VALUE),
    ],
)
def test_get_subprocess_secret(command, args, expectation, expected):
    source = config.SubprocessSecretSource(SECRET_NAME, command, args)

    with expectation:
        found = secrets.get_subprocess_secret(source)

    if expected is not ERROR_MISS:
        assert found == expected


@mock.patch("os.urandom")
def test_random_chars_secret_source(o_ur):
    source = config.RandomCharsSecretSource(SECRET_NAME, 32)

    found = secrets.get_random_chars_secret(source)

    assert found is o_ur.return_value.hex.return_value

    o_ur.assert_called_once_with(32)


ENV_VAR_MISS = config.EnvVarSecretSource(SECRET_NAME, "NONESUCH")
ENV_VAR_HIT = config.EnvVarSecretSource(SECRET_NAME, ENV_VAR_NAME)
RANDOM_CHARS = config.RandomCharsSecretSource(SECRET_NAME)


@pytest.mark.parametrize(
    "sources, expectation, expected",
    [
        ([ENV_VAR_MISS], ExcGroup, ERROR_MISS),
        ([ENV_VAR_MISS, ENV_VAR_HIT], NoRaise, SECRET_VALUE),
    ],
)
@mock.patch("os.urandom")
def test_secret_ctor_w_sources(o_ur, sources, expectation, expected):
    secret_config = config.SecretConfig(SECRET_NAME, sources)

    env_patch = {ENV_VAR_NAME: SECRET_VALUE}

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        with expectation:
            found = secrets.get_secret(secret_config)

    if expected is not ERROR_MISS:
        assert found == expected
