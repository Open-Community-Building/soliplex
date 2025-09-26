import contextlib
import dataclasses
import functools
import inspect
import json
import pathlib
from unittest import mock
from urllib import parse as url_parse

import pytest
import yaml

from soliplex import config

AUTHSYSTEM_ID = "testing"
AUTHSYSTEM_TITLE = "Testing OIDC"
AUTHSYSTEM_SERVER_URL = "https://example.com/auth/realms/sso"
AUTHSYSTEM_TOKEN_VALIDATION_PEM = """\
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAlXYDp/ux5839pPyhRAjq
RZTeyv6fKZqgvJS2cvrNzjfttYni7/++nU2uywAiKRnxfVIf6TWKaC4/oy0VkLpW
mkC4oyj0ArST9OYWI9mqxqdweEHrzXf8CjU7Q88LVY/9JUmHAiKjOH17m5hLY+q9
cmIs33SMq9g7GMgPfABNsgh57Xei1sVPSzzSzTd80AguMF7B9hrNg6eTr69CN+3s
3535wDD7tBgPzhz1qJ+lhaBSWrht9mjYpX5S0/7IQOV9M7YVBsFYztpD4Ht9TQc0
jbVPyMXk2bi6vmfpfjCtio7RjDqi38wTf38RuD7mhPYyDOzGFcfSr4yNnORRKyYH
9QIDAQAB
-----END PUBLIC KEY-----
"""
AUTHSYSTEM_CLIENT_ID = "testing-oidc"

ABSOLUTE_OIDC_CLIENT_PEM_PATH = "/path/to/cacert.pem"
RELATIVE_OIDC_CLIENT_PEM_PATH = "./cacert.pem"
BARE_AUTHSYSTEM_CONFIG_KW = {
    "id": AUTHSYSTEM_ID,
    "title": AUTHSYSTEM_TITLE,
    "server_url": AUTHSYSTEM_SERVER_URL,
    "token_validation_pem": AUTHSYSTEM_TOKEN_VALIDATION_PEM,
    "client_id": AUTHSYSTEM_CLIENT_ID,
}
BARE_AUTHSYSTEM_CONFIG_YAML = f"""
auth_systems:
  - id: "{AUTHSYSTEM_ID}"
    title: "{AUTHSYSTEM_TITLE}"
    server_url: "{AUTHSYSTEM_SERVER_URL}"
    token_validation_pem: |
        -----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAlXYDp/ux5839pPyhRAjq
        RZTeyv6fKZqgvJS2cvrNzjfttYni7/++nU2uywAiKRnxfVIf6TWKaC4/oy0VkLpW
        mkC4oyj0ArST9OYWI9mqxqdweEHrzXf8CjU7Q88LVY/9JUmHAiKjOH17m5hLY+q9
        cmIs33SMq9g7GMgPfABNsgh57Xei1sVPSzzSzTd80AguMF7B9hrNg6eTr69CN+3s
        3535wDD7tBgPzhz1qJ+lhaBSWrht9mjYpX5S0/7IQOV9M7YVBsFYztpD4Ht9TQc0
        jbVPyMXk2bi6vmfpfjCtio7RjDqi38wTf38RuD7mhPYyDOzGFcfSr4yNnORRKyYH
        9QIDAQAB
        -----END PUBLIC KEY-----
    client_id: "{AUTHSYSTEM_CLIENT_ID}"
"""

AUTHSYSTEM_SCOPE = "test one two three"
W_SCOPE_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_SCOPE_AUTHSYSTEM_CONFIG_KW["scope"] = AUTHSYSTEM_SCOPE
W_SCOPE_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    scope: "{AUTHSYSTEM_SCOPE}"
"""

W_PEM_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_PEM_AUTHSYSTEM_CONFIG_KW["oidc_client_pem_path"] = (
    ABSOLUTE_OIDC_CLIENT_PEM_PATH
)
W__AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{ABSOLUTE_OIDC_CLIENT_PEM_PATH}"
"""

AUTHSYSTEM_CLIENT_SECRET_LIT = "REALLY BIG SECRET"
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW["client_secret"] = (
    AUTHSYSTEM_CLIENT_SECRET_LIT
)
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    client_secret: "{AUTHSYSTEM_CLIENT_SECRET_LIT}"
"""

CLIENT_SECRET_NAME = "TEST_OIDC_CLIENT_SECRET"
AUTHSYSTEM_CLIENT_SECRET_SECRET = f"secret:{CLIENT_SECRET_NAME}"
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW["client_secret"] = (
    AUTHSYSTEM_CLIENT_SECRET_SECRET
)
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    client_secret: "{AUTHSYSTEM_CLIENT_SECRET_SECRET}"
"""

AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL_NAME = "cacert.pem"
AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL = "./cacert.pem"
W_OIDC_CPP_REL_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_OIDC_CPP_REL_KW["oidc_client_pem_path"] = AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL
W_OIDC_CPP_REL_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL}"
"""

AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS = "/path/to/cacert.pem"
W_OIDC_CPP_ABS_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_OIDC_CPP_ABS_KW["oidc_client_pem_path"] = AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS
W_OIDC_CPP_ABS_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS}"
"""


AGENT_ID = "testing"
SYSTEM_PROMPT = "You are a test"
MODEL_NAME = "test-model"
PROVIDER_BASE_URL = "https://provider.example.com/api"
PROVIDER_KEY_ENVVAR = "TEST_API_KEY"
PROVIDER_KEY_VALUE = "DEADBEEF"
OLLAMA_BASE_URL = "https://example.com:12345"

BARE_INSTALLATION_CONFIG_ENVIRONMENT = {
    "OLLAMA_BASE_URL": PROVIDER_BASE_URL,
    "DEFAULT_AGENT_MODEL": MODEL_NAME,
}

TEST_QUIZ_ID = "test_quiz"
TEST_QUIZ_TITLE = "Test Quiz"
TEST_QUIZ_STEM = "question_file"
TEST_QUIZ_OVR = "/path/to/question_file.json"
INPUTS = "What color is the sky"
EXPECTED_ANSWER = "Blue"
QA_QUESTION_UUID = "DEADBEEF"
MC_QUESTION_UUID = "FACEDACE"
QUESTION_TYPE_QA = "qa"
QUESTION_TYPE_MC = "multiple-choice"
MC_OPTIONS = ["orange", "blue", "purple"]

TEST_QUIZ_W_STEM_KW = {
    "id": TEST_QUIZ_ID,
    "title": TEST_QUIZ_TITLE,
    "question_file": TEST_QUIZ_STEM,
    "randomize": True,
    "max_questions": 3,
}
TEST_QUIZ_W_STEM_YAML = f"""
id: "{TEST_QUIZ_ID}"
title: "{TEST_QUIZ_TITLE}"
question_file: "{TEST_QUIZ_STEM}"
randomize: true
max_questions: 3
"""

TEST_QUIZ_W_OVR_KW = {
    "id": TEST_QUIZ_ID,
    "question_file": TEST_QUIZ_OVR,
}
TEST_QUIZ_W_OVR_YAML = f"""
id: "{TEST_QUIZ_ID}"
question_file: "{TEST_QUIZ_OVR}"
"""

ROOM_ID = "test-room"
ROOM_NAME = "Test Room"
ROOM_DESCRIPTION = "This room is for testing"
WELCOME_MESSAGE = "Welcome to this room!"
SUGGESTION = "Try us out for a spin!"
IMAGE_FILENAME = "test_image.jpg"

HTTP_MCP_URL = "https://example.com/services/baz/mcp"
HTTP_MCP_QP_KEY = "frob"
HTTP_MCP_QP_VALUE = "bazquyth"
HTTP_MCP_QUERY_PARAMS = {HTTP_MCP_QP_KEY: HTTP_MCP_QP_VALUE}
HTTP_MCP_BEARER_TOKEN = "FACEDACE"
HTTP_MCP_AUTH_HEADER = {"Authorization": "Bearer {HTTP_MCP_BEARER_TOKEN}"}
QUIZ_ID = "test_quiz"

DADS_BASE_URL = "https://docs.stage.josce.mil/dev/"
DADS_SSO_SERVER_URL = "https://sso.test.josce.mil/auth/"
DADS_BEARER_TOKEN = "CAFEBEAD"
DADS_API_CONFIG_KW = {
    "base_url": DADS_BASE_URL,
    "sso_server_url": DADS_SSO_SERVER_URL,
    "verify_ssl_certs": False,
    "bearer_token": DADS_BEARER_TOKEN,
}
DADS_API_CONFIG_YAML = f"""
base_url: "{DADS_BASE_URL}"
sso_server_url: "{DADS_SSO_SERVER_URL}"
verify_ssl_certs: false
bearer_token: "{DADS_BEARER_TOKEN}"
"""
FADTC_PROJECT = "test-project"
FADTC_SOURCE_DOC_PATH_1 = "modules/ROOT/pages/test-one.adoc"
FADTC_SOURCE_DOC_PATH_2 = "modules/ROOT/pages/test-two.adoc"
FADTC_CONFIG_KW = {
    "project": FADTC_PROJECT,
    "source_document_paths": [
        FADTC_SOURCE_DOC_PATH_1,
        FADTC_SOURCE_DOC_PATH_2,
    ],
    "dads_api_config_path": None,  # to be replaced
    "allow_mcp": True,
}


EMPTY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
)
EMPTY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
"""


BARE_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    system_prompt=SYSTEM_PROMPT,
    model_name=MODEL_NAME,
)
BARE_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
system_prompt: "{SYSTEM_PROMPT}"
model_name: "{MODEL_NAME}"
"""

W_PROMPT_FILE_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    _system_prompt_path="./prompt.txt",
    model_name=MODEL_NAME,
)
W_PROMPT_FILE_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
system_prompt: ./prompt.txt
model_name: "{MODEL_NAME}"
"""

Q_UUID_1 = "DEADBEEF"
QUESTION_1 = "What color is the sky"
ANSWER_1 = "blue"
TYPE_1 = "qa"

Q_UUID_2 = "FACEDACE"
QUESTION_2 = "What color is grass?"
ANSWER_2 = "green"
TYPE_2 = "multiple-choice"
OPTIONS_2 = ["red", "green", "blue"]

QUESTIONS = [
    config.QuizQuestion(
        inputs=QUESTION_1,
        expected_output=ANSWER_1,
        metadata=config.QuizQuestionMetadata(
            uuid=Q_UUID_1,
            type=TYPE_1,
        ),
    ),
    config.QuizQuestion(
        inputs=QUESTION_2,
        expected_output=ANSWER_2,
        metadata=config.QuizQuestionMetadata(
            type=TYPE_2, uuid=Q_UUID_2, options=OPTIONS_2
        ),
    ),
]

BARE_ROOM_CONFIG_KW = {
    "id": ROOM_ID,
    "name": ROOM_NAME,
    "description": ROOM_DESCRIPTION,
    "agent_config": config.AgentConfig(
        id=f"room-{ROOM_ID}",
        system_prompt=SYSTEM_PROMPT,
    ),
}
BARE_ROOM_CONFIG_YAML = f"""\
id: "{ROOM_ID}"
name: "{ROOM_NAME}"
description: "{ROOM_DESCRIPTION}"
agent:
    system_prompt: "{SYSTEM_PROMPT}"
"""

FULL_ROOM_CONFIG_KW = {
    "id": ROOM_ID,
    "name": ROOM_NAME,
    "description": ROOM_DESCRIPTION,
    "welcome_message": WELCOME_MESSAGE,
    "suggestions": [
        SUGGESTION,
    ],
    "enable_attachments": True,
    "logo_image": f"./{IMAGE_FILENAME}",
    "agent_config": config.AgentConfig(
        id=f"room-{ROOM_ID}",
        system_prompt=SYSTEM_PROMPT,
    ),
    "quizzes": [
        config.QuizConfig(
            id=TEST_QUIZ_ID,
            question_file=TEST_QUIZ_OVR,
        ),
    ],
    "allow_mcp": True,
    "tool_configs": {
        "get_current_datetime": config.ToolConfig(
            tool_name="soliplex.tools.get_current_datetime",
            allow_mcp=True,
        ),
        "search_documents": config.SearchDocumentsToolConfig(
            search_documents_limit=1,
            rag_lancedb_override_path="/dev/null",
            allow_mcp=True,
        ),
    },
    "mcp_client_toolset_configs": {
        "stdio_test": config.Stdio_MCP_ClientToolsetConfig(
            command="cat",
            args=[
                "-",
            ],
            env={
                "foo": "bar",
            },
        ),
        "http_test": config.HTTP_MCP_ClientToolsetConfig(
            url=HTTP_MCP_URL,
            headers={
                "Authorization": f"Bearer {HTTP_MCP_BEARER_TOKEN}",
            },
            query_params=HTTP_MCP_QUERY_PARAMS,
        ),
    },
}
FULL_ROOM_CONFIG_YAML = f"""\
id: "{ROOM_ID}"
name: "{ROOM_NAME}"
description: "{ROOM_DESCRIPTION}"
welcome_message: "{WELCOME_MESSAGE}"
suggestions:
  - "{SUGGESTION}"
enable_attachments: true
logo_image: "./{IMAGE_FILENAME}"
agent:
    system_prompt: "{SYSTEM_PROMPT}"
tools:
    - tool_name: "soliplex.tools.get_current_datetime"
      allow_mcp: true
    - tool_name: "soliplex.tools.search_documents"
      rag_lancedb_override_path: /dev/null
      search_documents_limit: 1
      allow_mcp: true
mcp_client_toolsets:
    stdio_test:
      type: "stdio"
      command: "cat"
      args:
        - "-"
      env:
        foo: "bar"
    http_test:
      type: "http"
      url: "{HTTP_MCP_URL}"
      headers:
        Authorization: "Bearer {HTTP_MCP_BEARER_TOKEN}"
      query_params:
        {HTTP_MCP_QP_KEY}: "{HTTP_MCP_QP_VALUE}"
quizzes:
  - id: "{TEST_QUIZ_ID}"
    question_file: "{TEST_QUIZ_OVR}"
allow_mcp: true
"""

COMPLETION_ID = "test-completion"
COMPLETION_NAME = "Test Completions"

BARE_COMPLETION_CONFIG_KW = {
    "id": COMPLETION_ID,
    "agent_config": config.AgentConfig(
        id=f"completion-{COMPLETION_ID}",
        system_prompt=SYSTEM_PROMPT,
    ),
}
BARE_COMPLETION_CONFIG_YAML = f"""\
id: "{COMPLETION_ID}"
agent:
    system_prompt: "{SYSTEM_PROMPT}"
"""

FULL_COMPLETION_CONFIG_KW = {
    "id": COMPLETION_ID,
    "name": COMPLETION_NAME,
    "agent_config": config.AgentConfig(
        id=f"completion-{COMPLETION_ID}",
        system_prompt=SYSTEM_PROMPT,
    ),
    "tool_configs": {
        "get_current_datetime": config.ToolConfig(
            tool_name="soliplex.tools.get_current_datetime",
        ),
        "search_documents": config.SearchDocumentsToolConfig(
            search_documents_limit=1,
            rag_lancedb_override_path="/dev/null",
        ),
    },
    "mcp_client_toolset_configs": {
        "stdio_test": config.Stdio_MCP_ClientToolsetConfig(
            command="cat",
            args=[
                "-",
            ],
            env={
                "foo": "bar",
            },
        ),
        "http_test": config.HTTP_MCP_ClientToolsetConfig(
            url=HTTP_MCP_URL,
            headers={
                "Authorization": f"Bearer {HTTP_MCP_BEARER_TOKEN}",
            },
            query_params=HTTP_MCP_QUERY_PARAMS,
        ),
    },
}
FULL_COMPLETION_CONFIG_YAML = f"""\
id: "{COMPLETION_ID}"
name: "{COMPLETION_NAME}"
agent:
    system_prompt: "{SYSTEM_PROMPT}"
tools:
    - tool_name: "soliplex.tools.get_current_datetime"
    - tool_name: "soliplex.tools.search_documents"
      rag_lancedb_override_path: /dev/null
      search_documents_limit: 1
mcp_client_toolsets:
    stdio_test:
      type: "stdio"
      command: "cat"
      args:
        - "-"
      env:
        foo: "bar"
    http_test:
      type: "http"
      url: "{HTTP_MCP_URL}"
      headers:
        Authorization: "Bearer {HTTP_MCP_BEARER_TOKEN}"
      query_params:
        {HTTP_MCP_QP_KEY}: "{HTTP_MCP_QP_VALUE}"
"""

SECRET_NAME = "TEST_SECRET"
ENV_VAR_NAME = "TEST_ENV_VAR"
COMMAND = "cat"

INSTALLATION_ID = "test-installation"

BARE_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
}
BARE_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
"""

SECRET_NAME_1 = "TEST_SECRET_ONE"
SECRET_NAME_2 = "TEST_SECRET_TWO"
SECRET_CONFIG_1 = config.SecretConfig(SECRET_NAME_1)
SECRET_CONFIG_2 = config.SecretConfig(SECRET_NAME_2)
SECRET_ENV_VAR = "OTHER_ENV_VAR"
SECRET_FILE_PATH = "./very_seekrit"
SECRET_COMAND = "cat"
SECRET_ARGS = ["-"]
SECRET_NCHARS = 37

W_SECRETS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "secrets": [
        config.SecretConfig(SECRET_NAME_1),
        config.SecretConfig(
            SECRET_NAME_2,
            sources=[
                config.EnvVarSecretSource(SECRET_NAME_2, SECRET_ENV_VAR),
                config.FilePathSecretSource(SECRET_NAME_2, SECRET_FILE_PATH),
                config.SubprocessSecretSource(
                    SECRET_NAME_2,
                    SECRET_COMAND,
                    SECRET_ARGS,
                ),
                config.RandomCharsSecretSource(SECRET_NAME_2, SECRET_NCHARS),
            ],
        ),
    ],
}
W_SECRETS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
secrets:
    - "{SECRET_NAME_1}"
    - secret_name: "{SECRET_NAME_2}"
      sources:
          - kind: "env_var"
            env_var_name: "{SECRET_ENV_VAR}"
          - kind: "file_path"
            file_path: "{SECRET_FILE_PATH}"
          - kind: "subprocess"
            command: "{SECRET_COMAND}"
            args:
            - "-"
          - kind: "random_chars"
            n_chars: {SECRET_NCHARS}
"""

CONFIG_KEY_1 = "key_1"
CONFIG_VAL_1 = "val_1"
CONFIG_KEY_2 = "key_2"
CONFIG_VAL_2 = "val_2"
W_ENVIRONMENT_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "environment": {
        CONFIG_KEY_1: CONFIG_VAL_1,
        CONFIG_KEY_2: CONFIG_VAL_2,
    },
}
W_ENVIRONMENT_LIST_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
environment:
    - name: "{CONFIG_KEY_1}"
      value: "{CONFIG_VAL_1}"
    - name: "{CONFIG_KEY_2}"
      value: "{CONFIG_VAL_2}"
"""
W_ENVIRONMENT_MAPPING_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
environment:
    {CONFIG_KEY_1}: "{CONFIG_VAL_1}"
    {CONFIG_KEY_2}: "{CONFIG_VAL_2}"
"""

OIDC_PATH_1 = "./oidc"
OIDC_PATH_2 = "/path/to/other/oidc"

W_OIDC_PATHS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "oidc_paths": [
        OIDC_PATH_1,
        OIDC_PATH_2,
    ],
}
W_OIDC_PATHS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
oidc_paths:
    - "{OIDC_PATH_1}"
    - "{OIDC_PATH_2}"
"""

W_OIDC_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "oidc_paths": [],
}
W_OIDC_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
oidc_paths:
    -
"""

ROOM_PATH_1 = "./rooms"
ROOM_PATH_2 = "/path/to/other/rooms"

W_ROOM_PATHS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "room_paths": [
        ROOM_PATH_1,
        ROOM_PATH_2,
    ],
}
W_ROOM_PATHS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
room_paths:
    - "{ROOM_PATH_1}"
    - "{ROOM_PATH_2}"
"""

W_ROOM_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "room_paths": [],
}
W_ROOM_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
room_paths:
    -
"""

COMPLETION_PATH_1 = "./completions"
COMPLETION_PATH_2 = "/path/to/other/completions"

W_COMPLETION_PATHS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "completion_paths": [
        COMPLETION_PATH_1,
        COMPLETION_PATH_2,
    ],
}
W_COMPLETION_PATHS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
completion_paths:
    - "{COMPLETION_PATH_1}"
    - "{COMPLETION_PATH_2}"
"""

W_COMPLETION_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "completion_paths": [],
}
W_COMPLETION_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
completion_paths:
    -
"""

QUIZZES_PATH_1 = "./quizzes"
QUIZZES_PATH_2 = "/path/to/other/quizzes"

W_QUIZZES_PATHS_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "quizzes_paths": [
        QUIZZES_PATH_1,
        QUIZZES_PATH_2,
    ],
}
W_QUIZZES_PATHS_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
quizzes_paths:
    - "{QUIZZES_PATH_1}"
    - "{QUIZZES_PATH_2}"
"""

W_QUIZZES_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW = {
    "id": INSTALLATION_ID,
    "quizzes_paths": [],
}
W_QUIZZES_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML = f"""\
id: "{INSTALLATION_ID}"
quizzes_paths:
    -
"""


@pytest.fixture
def installation_config():
    return mock.create_autospec(config.InstallationConfig)


@pytest.mark.parametrize(
    "w_config",
    [
        BARE_AUTHSYSTEM_CONFIG_KW.copy(),
        W_SCOPE_AUTHSYSTEM_CONFIG_KW.copy(),
        W_PEM_AUTHSYSTEM_CONFIG_KW.copy(),
    ],
)
def test_authsystem_from_yaml(installation_config, temp_dir, w_config):
    expected = config.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        **w_config,
    )

    oidc_client_pem_path = w_config.get("oidc_client_pem_path")

    if oidc_client_pem_path is not None:
        expected = dataclasses.replace(
            expected,
            oidc_client_pem_path=pathlib.Path(oidc_client_pem_path),
        )

    expected._config_path = temp_dir

    found = config.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        temp_dir,
        w_config,
    )

    assert found == expected


@pytest.mark.parametrize(
    "exp_config, config_yaml, exp_secret",
    [
        (
            W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW,
            W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_YAML,
            AUTHSYSTEM_CLIENT_SECRET_LIT,
        ),
        (
            W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW,
            W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_YAML,
            AUTHSYSTEM_CLIENT_SECRET_SECRET,
        ),
    ],
)
def test_authsystem_from_yaml_w_client_secret(
    installation_config,
    temp_dir,
    exp_config,
    config_yaml,
    exp_secret,
):
    config_file = temp_dir / "config.yaml"
    config_file.write_text(config_yaml)

    with config_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    expected = config.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        _config_path=config_file,
        **exp_config,
    )
    expected.client_secret = exp_secret

    found = config.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        config_file,
        config_dict["auth_systems"][0],
    )

    assert found == expected


@pytest.mark.parametrize(
    "w_config, exp_path",
    [
        (W_OIDC_CPP_REL_KW, "{temp_dir}/{rel_name}"),
        (
            W_OIDC_CPP_ABS_KW,
            AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS,
        ),
    ],
)
def test_authsystem_from_yaml_w_oid_cpp(
    installation_config,
    temp_dir,
    w_config,
    exp_path,
):
    expected = config.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        **w_config,
    )
    config_path = expected._config_path = temp_dir / "config.yaml"

    if exp_path.startswith("{"):
        kwargs = {
            "temp_dir": temp_dir,
            "rel_name": AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL_NAME,
        }
        exp_path = exp_path.format(**kwargs)

    expected.oidc_client_pem_path = pathlib.Path(exp_path)

    found = config.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        config_path,
        w_config,
    )

    assert found == expected


def test_authsystem_server_metadata_url():
    inst = config.OIDCAuthSystemConfig(**BARE_AUTHSYSTEM_CONFIG_KW)

    assert inst.server_metadata_url == (
        f"{AUTHSYSTEM_SERVER_URL}/{config.WELL_KNOWN_OPENID_CONFIGURATION}"
    )


@pytest.mark.parametrize(
    "w_config, exp_client_kwargs, exp_secret, bare_secret",
    [
        (BARE_AUTHSYSTEM_CONFIG_KW.copy(), {}, "", True),
        (
            W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW,
            {},
            AUTHSYSTEM_CLIENT_SECRET_LIT,
            True,
        ),
        (
            W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW,
            {},
            AUTHSYSTEM_CLIENT_SECRET_SECRET,
            False,
        ),
        (W_SCOPE_AUTHSYSTEM_CONFIG_KW, {"scope": AUTHSYSTEM_SCOPE}, "", True),
        (
            W_OIDC_CPP_ABS_KW,
            {"verify": AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS},
            "",
            True,
        ),
    ],
)
def test_authsystem_oauth_client_args(
    installation_config,
    temp_dir,
    w_config,
    exp_client_kwargs,
    exp_secret,
    bare_secret,
):
    inst = config.OIDCAuthSystemConfig(
        **w_config,
    )
    inst._installation_config = installation_config
    exp_url = (
        f"{AUTHSYSTEM_SERVER_URL}/{config.WELL_KNOWN_OPENID_CONFIGURATION}"
    )

    icgs = installation_config.get_secret

    if bare_secret:
        icgs.side_effect = ValueError("testing")

    found = inst.oauth_client_kwargs

    assert found["name"] == AUTHSYSTEM_ID
    assert found["server_metadata_url"] == exp_url
    assert found["client_id"] == AUTHSYSTEM_CLIENT_ID
    assert found["client_kwargs"] == exp_client_kwargs

    if bare_secret:
        assert found["client_secret"] == exp_secret
    else:
        assert found["client_secret"] is icgs.return_value

    icgs.assert_called_once_with(exp_secret)


def test_toolconfig_from_yaml(installation_config, temp_dir):
    tool_name = "soliplex.tools.test_tool"
    config_path = temp_dir / "thing_config.yaml"

    expected = config.ToolConfig(
        _installation_config=installation_config,
        _config_path=config_path,
        tool_name=tool_name,
        allow_mcp=True,
    )

    tool_config = config.ToolConfig.from_yaml(
        installation_config=installation_config,
        config_path=config_path,
        config={
            "tool_name": tool_name,
            "allow_mcp": True,
        },
    )

    assert tool_config == expected


def test_toolconfig_kind():
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    assert tool_config.kind == "test_tool"


def test_toolconfig_tool_id():
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    assert tool_config.tool_id == "test_tool"


@pytest.mark.parametrize("w_existing", [False, True])
def test_toolconfig_tool(w_existing):
    def existing():  # pragma: NO COVER
        pass

    def test_tool(ctx, tool_config=None):
        "This is a test"

    if w_existing:
        tool_config = config.ToolConfig(
            tool_name="no.such.animal.exists",
        )
        tool_config._tool = existing
    else:
        tool_config = config.ToolConfig(
            tool_name="soliplex.tools.test_tool",
        )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        found = tool_config.tool

    if w_existing:
        assert found is existing

    else:
        assert found is test_tool


def TEST_TOOL_W_CTX_WO_PARAM_WO_TC(
    ctx,
) -> str:
    "This is a test"


def TEST_TOOL_W_CTX_W_PARAM_WO_TC(
    ctx,
    query: str,
) -> str:
    "This is a test"


def TEST_TOOL_W_CTX_WO_PARAM_W_TC(
    ctx,
    tool_config: config.ToolConfig,
) -> str:
    "This is a test"


def TEST_TOOL_W_CTX_W_PARAM_W_TC(
    ctx,
    query: str,
    tool_config: config.ToolConfig,
) -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_WO_PARAM_WO_TC() -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_W_PARAM_WO_TC(
    query: str,
) -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_WO_PARAM_W_TC(
    tool_config: config.ToolConfig,
) -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_W_PARAM_W_TC(
    query: str,
    tool_config: config.ToolConfig,
) -> str:
    "This is a test"


@pytest.mark.parametrize(
    "test_tool",
    [
        TEST_TOOL_W_CTX_WO_PARAM_W_TC,
        TEST_TOOL_W_CTX_W_PARAM_W_TC,
    ],
)
def test_toolconfig_tool_requires_w_conflict(test_tool):
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        with pytest.raises(config.ToolRequirementConflict):
            _ = tool_config.tool_requires


@pytest.mark.parametrize(
    "test_tool",
    [
        TEST_TOOL_W_CTX_WO_PARAM_WO_TC,
        TEST_TOOL_W_CTX_W_PARAM_WO_TC,
        TEST_TOOL_WO_CTX_WO_PARAM_WO_TC,
        TEST_TOOL_WO_CTX_W_PARAM_WO_TC,
        TEST_TOOL_WO_CTX_WO_PARAM_W_TC,
        TEST_TOOL_WO_CTX_W_PARAM_W_TC,
    ],
)
def test_toolconfig_tool_description(test_tool):
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        found = tool_config.tool_description

    assert found == test_tool.__doc__.strip()


@pytest.mark.parametrize(
    "test_tool, expected",
    [
        (TEST_TOOL_W_CTX_WO_PARAM_WO_TC, config.ToolRequires.FASTAPI_CONTEXT),
        (TEST_TOOL_W_CTX_W_PARAM_WO_TC, config.ToolRequires.FASTAPI_CONTEXT),
        (TEST_TOOL_WO_CTX_WO_PARAM_WO_TC, config.ToolRequires.BARE),
        (TEST_TOOL_WO_CTX_W_PARAM_WO_TC, config.ToolRequires.BARE),
        (TEST_TOOL_WO_CTX_WO_PARAM_W_TC, config.ToolRequires.TOOL_CONFIG),
        (TEST_TOOL_WO_CTX_W_PARAM_W_TC, config.ToolRequires.TOOL_CONFIG),
    ],
)
def test_toolconfig_tool_requires(test_tool, expected):
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        found = tool_config.tool_requires

    assert found == expected


@pytest.mark.parametrize(
    "test_tool, exp_wrapped",
    [
        (TEST_TOOL_W_CTX_WO_PARAM_WO_TC, False),
        (TEST_TOOL_W_CTX_W_PARAM_WO_TC, False),
        (TEST_TOOL_WO_CTX_WO_PARAM_WO_TC, False),
        (TEST_TOOL_WO_CTX_W_PARAM_WO_TC, False),
        (TEST_TOOL_WO_CTX_WO_PARAM_W_TC, True),
        (TEST_TOOL_WO_CTX_W_PARAM_W_TC, True),
    ],
)
def test_toolconfig_tool_with_config(test_tool, exp_wrapped):
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        found = tool_config.tool_with_config

    if exp_wrapped:
        assert isinstance(found, functools.partial)
        assert found.func is test_tool
        assert found.keywords == {"tool_config": tool_config}
        assert found.__name__ == test_tool.__name__
        assert found.__doc__ == test_tool.__doc__

        exp_signature = inspect.signature(test_tool)
        for param in found.__signature__.parameters:
            assert param in exp_signature.parameters

    else:
        assert found is test_tool


def test_toolconfig_get_extra_parameters():
    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    assert tool_config.get_extra_parameters() == {}


@pytest.mark.parametrize(
    "stem, override, which",
    [
        (None, None, None),
        ("testing", "/dev/null", None),
        ("testing", None, "stem"),
        (None, "./override", "override"),
    ],
)
def test_sdtc_ctor(installation_config, temp_dir, stem, override, which):
    db_rag_path = temp_dir / "db" / "rag"
    db_rag_path.mkdir(parents=True)

    if which is None:
        expectation = pytest.raises(config.RagDbExactlyOneOfStemOrOverride)
    else:
        expectation = contextlib.nullcontext()

    if stem is not None:
        from_stem = db_rag_path / f"{stem}.lancedb"
        from_stem.touch()

    if override is not None:
        override = temp_dir / override
        from_override = pathlib.Path(override)
        from_override.touch()

    ic_environ = {"RAG_LANCE_DB_PATH": str(db_rag_path)}
    installation_config.get_environment = ic_environ.get

    kw = {"_installation_config": installation_config}

    if stem is not None:
        kw["rag_lancedb_stem"] = stem

    if override is not None:
        kw["rag_lancedb_override_path"] = override

    with expectation:
        sdt_config = config.SearchDocumentsToolConfig(**kw)

    if which is not None and stem != "nonesuch":
        if which == "stem":
            expected = from_stem
        else:
            expected = from_override

        assert sdt_config._config_path is None

        found = sdt_config.rag_lancedb_path
        assert found.resolve() == expected.resolve()

        expected_ep = {
            "rag_lancedb_path": expected,
            "expand_context_radius": 2,
            "search_documents_limit": 5,
            "return_citations": False,
        }

        assert sdt_config.get_extra_parameters() == expected_ep


@pytest.mark.parametrize(
    "stem, override, which",
    [
        (None, None, None),
        ("testing", "/dev/null", None),
        ("testing", None, "stem"),
        ("nonesuch", None, "stem"),
        (None, "./foo.lancedb", "override"),
        (None, "./nonesuch", "override"),
    ],
)
def test_sdtc_from_yaml(installation_config, temp_dir, stem, override, which):
    db_rag_path = temp_dir / "db" / "rag"
    db_rag_path.mkdir(parents=True)

    ic_environ = {"RAG_LANCE_DB_PATH": str(db_rag_path)}
    installation_config.get_environment = ic_environ.get

    kw = {"_installation_config": installation_config}

    if stem is not None:
        kw["rag_lancedb_stem"] = stem
        from_stem = db_rag_path / f"{stem}.lancedb"
        if stem != "nonesuch":
            from_stem.touch()
            expected = from_stem
            expectation = contextlib.nullcontext()
        else:
            expectation = pytest.raises(config.RagDbFileNotFound)
            expected = None

    if override is not None:
        override = str(temp_dir / override)
        kw["rag_lancedb_override_path"] = override
        from_override = pathlib.Path(override)
        if "nonesuch" not in override:
            expectation = contextlib.nullcontext()
            from_override.touch()
            expected = from_override
        else:
            expectation = pytest.raises(config.RagDbFileNotFound)
            expected = None

    room_dir = temp_dir / "rooms" / "testroom"
    config_path = room_dir / "room_config.yaml"

    if which is None:
        with pytest.raises(config.FromYamlException) as exc:
            config.SearchDocumentsToolConfig.from_yaml(
                installation_config=installation_config,
                config_path=config_path,
                config=kw,
            )

        assert exc.value.config_path == config_path

    else:
        sdt_config = config.SearchDocumentsToolConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config=kw,
        )

        assert sdt_config._installation_config == installation_config
        assert sdt_config._config_path == config_path

        with expectation:
            found = sdt_config.rag_lancedb_path

        if expected is not None:
            assert found.resolve() == expected.resolve()


@pytest.mark.parametrize("w_env", [{}, {"foo": "bar"}])
def test_stdio_mctc_toolset_params(w_env):
    stdio_mctc = config.Stdio_MCP_ClientToolsetConfig(
        command="cat",
        args=["-"],
        env=w_env,
    )

    found = stdio_mctc.toolset_params

    assert found["command"] == stdio_mctc.command
    assert found["args"] == stdio_mctc.args
    assert found["env"] == stdio_mctc.env
    assert found["allowed_tools"] == stdio_mctc.allowed_tools


@pytest.mark.parametrize("w_env", [{}, {"foo": "bar"}])
def test_stdio_mctc_tool_kwargs(installation_config, w_env):
    stdio_mctc = config.Stdio_MCP_ClientToolsetConfig(
        command="cat",
        args=["-"],
        env=w_env,
        _installation_config=installation_config,
    )

    found = stdio_mctc.tool_kwargs

    assert found["command"] == stdio_mctc.command
    assert found["args"] == stdio_mctc.args
    assert found["allowed_tools"] == stdio_mctc.allowed_tools

    for (f_key, f_val), (cfg_key, cfg_value) in zip(
        found["env"].items(),
        w_env.items(),
        strict=True,
    ):
        assert f_key == cfg_key
        assert f_val is installation_config.get_environment.return_value
        assert (
            mock.call(cfg_value, cfg_value)
            in installation_config.get_environment.call_args_list
        )


@pytest.mark.parametrize("w_headers", [{}, HTTP_MCP_AUTH_HEADER])
@pytest.mark.parametrize("w_query_params", [{}, HTTP_MCP_QUERY_PARAMS])
def test_http_mctc_toolset_params(w_query_params, w_headers):
    http_mctc = config.HTTP_MCP_ClientToolsetConfig(
        url=HTTP_MCP_URL,
        headers=w_headers,
        query_params=w_query_params,
    )

    found = http_mctc.toolset_params

    assert found["url"] == http_mctc.url
    assert found["query_params"] == http_mctc.query_params
    assert found["headers"] == http_mctc.headers
    assert found["allowed_tools"] == http_mctc.allowed_tools


@pytest.mark.parametrize("w_headers", [{}, HTTP_MCP_AUTH_HEADER])
@pytest.mark.parametrize("w_query_params", [{}, HTTP_MCP_QUERY_PARAMS])
def test_http_mctc_tool_kwargs(installation_config, w_query_params, w_headers):
    installation_config.get_environment.return_value = "<env>"

    http_mctc = config.HTTP_MCP_ClientToolsetConfig(
        url=HTTP_MCP_URL,
        headers=w_headers,
        query_params=w_query_params,
        _installation_config=installation_config,
    )

    found = http_mctc.tool_kwargs

    assert found["allowed_tools"] == http_mctc.allowed_tools

    if w_query_params:
        base, qs = found["url"].split("?")
        assert base == http_mctc.url

        qp_dict = dict(url_parse.parse_qsl(qs))

        for (f_key, f_val), (cfg_key, cfg_value) in zip(
            qp_dict.items(),
            w_query_params.items(),
            strict=True,
        ):
            assert f_key == cfg_key
            assert f_val == installation_config.get_environment.return_value
            assert (
                mock.call(cfg_value, cfg_value)
                in installation_config.get_environment.call_args_list
            )

    else:
        assert found["url"] == http_mctc.url

    for (f_key, f_val), (cfg_key, cfg_value) in zip(
        found["headers"].items(),
        w_headers.items(),
        strict=True,
    ):
        assert f_key == cfg_key
        assert f_val is installation_config.get_environment.return_value
        assert (
            mock.call(cfg_value, cfg_value)
            in installation_config.get_environment.call_args_list
        )


@pytest.mark.parametrize(
    "kw",
    [
        EMPTY_AGENT_CONFIG_KW.copy(),
        BARE_AGENT_CONFIG_KW.copy(),
    ],
)
def test_agentconfig_ctor(installation_config, kw):
    kw["_installation_config"] = installation_config

    found = config.AgentConfig(**kw)

    if "model_name" in kw:
        assert found.model_name == kw["model_name"]
    else:
        assert (
            found.model_name
            is installation_config.get_environment.return_value
        )


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (EMPTY_AGENT_CONFIG_YAML, EMPTY_AGENT_CONFIG_KW.copy()),
        (BARE_AGENT_CONFIG_YAML, BARE_AGENT_CONFIG_KW.copy()),
        (
            W_PROMPT_FILE_AGENT_CONFIG_YAML,
            W_PROMPT_FILE_AGENT_CONFIG_KW.copy(),
        ),
    ],
)
def test_agentconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    expected = config.AgentConfig(**expected_kw)

    expected = dataclasses.replace(
        expected,
        _installation_config=installation_config,
        _config_path=yaml_file,
    )

    with yaml_file.open() as stream:
        yaml_dict = yaml.safe_load(stream)

    found = config.AgentConfig.from_yaml(
        installation_config,
        yaml_file,
        yaml_dict,
    )

    assert found == expected


@pytest.mark.parametrize("w_config_path", [False, True])
@pytest.mark.parametrize(
    "agent_config_kw",
    [
        EMPTY_AGENT_CONFIG_KW.copy(),
        BARE_AGENT_CONFIG_KW.copy(),
        W_PROMPT_FILE_AGENT_CONFIG_KW.copy(),
    ],
)
def test_agentconfig_get_system_prompt(
    temp_dir,
    agent_config_kw,
    w_config_path,
):
    agent_config_kw = agent_config_kw.copy()

    if w_config_path:
        config_path = temp_dir / "prompt.txt"
        config_path.write_text(SYSTEM_PROMPT)

        agent_config_kw["_config_path"] = config_path

    agent_config = config.AgentConfig(**agent_config_kw)

    if agent_config._system_prompt_text is not None:
        found = agent_config.get_system_prompt()
        assert found == agent_config._system_prompt_text
        return

    if agent_config._config_path:
        if agent_config._system_prompt_path is not None:
            expected = SYSTEM_PROMPT
        else:
            expected = None

        assert agent_config.get_system_prompt() == expected

    else:
        if agent_config._system_prompt_path is not None:
            with pytest.raises(config.NoConfigPath):
                agent_config.get_system_prompt()

        else:
            assert agent_config.get_system_prompt() is None


@pytest.mark.parametrize("has_pk", [False, True])
@pytest.mark.parametrize("has_base_url", [False, True])
def test_agentconfig_llm_provider_kw(
    installation_config,
    has_base_url,
    has_pk,
):
    ic_environ = {"OLLAMA_BASE_URL": OLLAMA_BASE_URL}
    installation_config.get_environment = ic_environ.get

    kw = {"_installation_config": installation_config}

    if has_base_url:
        expected_base_url = kw["provider_base_url"] = PROVIDER_BASE_URL
    else:
        expected_base_url = OLLAMA_BASE_URL

    expected = {
        "base_url": expected_base_url + "/v1",
    }

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config.AgentConfig(
        id="test-agent", system_prompt="You are a test", **kw
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.fixture
def qa_question():
    return config.QuizQuestion(
        inputs=INPUTS,
        expected_output=EXPECTED_ANSWER,
        metadata=config.QuizQuestionMetadata(
            uuid=QA_QUESTION_UUID,
            type=QUESTION_TYPE_QA,
            options=None,
        ),
    )


@pytest.fixture
def mc_question():
    return config.QuizQuestion(
        inputs=INPUTS,
        expected_output=EXPECTED_ANSWER,
        metadata=config.QuizQuestionMetadata(
            uuid=MC_QUESTION_UUID,
            type=QUESTION_TYPE_MC,
            options=MC_OPTIONS,
        ),
    )


@pytest.fixture
def quiz_questions(qa_question, mc_question):
    return [qa_question, mc_question]


@pytest.fixture
def quiz_json(quiz_questions):
    return {
        "cases": [dataclasses.asdict(question) for question in quiz_questions]
    }


@pytest.fixture
def populated_quiz(temp_dir, quiz_json):
    quizzes_path = temp_dir / "quizzes"
    quizzes_path.mkdir()
    populated_quiz = quizzes_path / f"{TEST_QUIZ_ID}.json"
    populated_quiz.write_text(json.dumps(quiz_json))
    return populated_quiz


def test_quizconfig_ctor_defaults():
    with pytest.raises(config.QCExactlyOneOfStemOrOverride):
        config.QuizConfig(id=TEST_QUIZ_ID)


def test_quizconfig_ctor_exclusive():
    with pytest.raises(config.QCExactlyOneOfStemOrOverride):
        config.QuizConfig(
            id=TEST_QUIZ_ID,
            _question_file_stem="question_file.json",
            _question_file_path_override="/path/to/question_file.json",
        )


@pytest.mark.parametrize(
    "qf, exp_stem, exp_ovr",
    [
        ("foo.json", "foo", None),
        ("bar", "bar", None),
        ("/path/to/foo.json", None, "/path/to/foo.json"),
    ],
)
def test_quizconfig_ctor_w_question_file(
    installation_config,
    temp_dir,
    qf,
    exp_stem,
    exp_ovr,
):
    qp_1 = temp_dir / "qp_1"
    qp_1.mkdir()

    qp_2 = temp_dir / "qp_2"
    qp_2.mkdir()

    if exp_stem == "foo":
        qf_in_qp2 = qp_2 / "foo.json"
        qf_in_qp2.write_text("{}")

    installation_config.quizzes_paths = [qp_1, qp_2]

    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file=qf,
        _installation_config=installation_config,
    )
    assert qc._question_file_stem == exp_stem
    assert qc._question_file_path_override == exp_ovr

    found = qc.question_file_path

    if exp_stem == "foo":
        assert found == qf_in_qp2
    elif exp_stem == "bar":
        assert found is None
    else:
        assert found == pathlib.Path(exp_ovr)


def test_quizconfig_from_yaml_exceptions(installation_config, temp_dir):
    config_kw = {
        "id": TEST_QUIZ_ID,
        "title": TEST_QUIZ_TITLE,
    }

    config_path = temp_dir / "test.yaml"

    with pytest.raises(config.FromYamlException) as exc:
        config.QuizConfig.from_yaml(
            installation_config,
            config_path,
            config_kw,
        )

    assert exc.value.config_path == config_path


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (TEST_QUIZ_W_STEM_YAML, TEST_QUIZ_W_STEM_KW),
        (TEST_QUIZ_W_OVR_YAML, TEST_QUIZ_W_OVR_KW),
    ],
)
def test_quizconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    expected = config.QuizConfig(**expected_kw)

    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)
    expected = dataclasses.replace(
        expected,
        _installation_config=installation_config,
        _config_path=yaml_file,
    )

    with yaml_file.open() as stream:
        yaml_dict = yaml.safe_load(stream)

    found = config.QuizConfig.from_yaml(
        installation_config,
        yaml_file,
        yaml_dict,
    )

    assert found == expected


def test_quizconfig_provider_url(installation_config):
    ic_environ = {"OLLAMA_BASE_URL": OLLAMA_BASE_URL}
    installation_config.get_environment = ic_environ.get

    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file="/dev/null",
        _installation_config=installation_config,
    )

    assert qc.provider_base_url == OLLAMA_BASE_URL


def test_quizconfig__load_questions_file_miss_w_stem(
    installation_config,
    temp_dir,
):
    installation_config.quizzes_paths = [temp_dir]
    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file="nonesuch",
        _installation_config=installation_config,
    )

    with pytest.raises(config.QuestionFileNotFoundWithStem):
        qc._load_questions_file()


def test_quizconfig__load_questions_file_miss_w_override(
    installation_config,
    temp_dir,
):
    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file=str(temp_dir / "nonesuch.json"),
        _installation_config=installation_config,
    )

    with pytest.raises(config.QuestionFileNotFoundWithOverride):
        qc._load_questions_file()


def test_quizconfig__load_questions_file(temp_dir, populated_quiz, quiz_json):
    expected_questions = quiz_json["cases"]

    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file=str(populated_quiz),
    )

    found = qc.get_questions()

    for f_question, e_question in zip(
        found,
        expected_questions,
        strict=True,
    ):
        assert f_question.inputs == e_question["inputs"]
        assert f_question.expected_output == e_question["expected_output"]
        assert f_question.metadata.type == e_question["metadata"]["type"]
        assert f_question.metadata.uuid == e_question["metadata"]["uuid"]
        options = e_question["metadata"].get("options")
        assert f_question.metadata.options == options


@pytest.mark.parametrize("w_max_questions", [None, 1])
@pytest.mark.parametrize("w_loaded", [False, True])
def test_quizconfig_get_questions(quiz_questions, w_loaded, w_max_questions):
    expected_questions = quiz_questions

    kwargs = {"id": TEST_QUIZ_ID, "question_file": "ignored.json"}

    if w_max_questions is not None:
        kwargs["max_questions"] = w_max_questions
        expected_questions = expected_questions[:w_max_questions]

    q_map = {
        question.metadata.uuid: question for question in expected_questions
    }

    qc = config.QuizConfig(**kwargs)

    if w_loaded:
        qc._questions_map = q_map
    else:
        qc._load_questions_file = mock.Mock(spec_set=(), return_value=q_map)

    found = qc.get_questions()

    assert found == list(q_map.values())


@mock.patch("random.shuffle")
def test_quizconfig_get_questions_w_randomize(
    shuffle,
    temp_dir,
    populated_quiz,
    quiz_json,
):
    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file=str(populated_quiz),
        randomize=True,
    )

    found = qc.get_questions()

    shuffle.assert_called_once_with(found)


@pytest.mark.parametrize("w_miss", [False, True])
@pytest.mark.parametrize("w_loaded", [False, True])
def test_quizconfig_get_question(w_loaded, w_miss):
    UUID = "DEADBEEF"
    expected = object()

    qc = config.QuizConfig(
        id=TEST_QUIZ_ID,
        question_file="ignored.json",
    )
    q_map = {}

    if w_loaded:
        qc._questions_map = q_map
    else:
        qc._load_questions_file = mock.Mock(spec_set=(), return_value=q_map)

    if w_miss:
        with pytest.raises(KeyError):
            qc.get_question(UUID)

    else:
        q_map[UUID] = expected

        found = qc.get_question(UUID)

        assert found is expected


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BARE_ROOM_CONFIG_YAML, BARE_ROOM_CONFIG_KW),
        (FULL_ROOM_CONFIG_YAML, FULL_ROOM_CONFIG_KW),
    ],
)
def test_roomconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    expected = config.RoomConfig(**expected_kw)

    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    expected = dataclasses.replace(
        expected,
        _installation_config=installation_config,
        _config_path=yaml_file,
    )

    expected.agent_config = dataclasses.replace(
        expected.agent_config,
        _installation_config=installation_config,
        _config_path=yaml_file,
    )

    if len(expected_kw.get("tool_configs", {})) > 0:
        for tool_config in expected_kw["tool_configs"].values():
            tool_config._installation_config = installation_config
            tool_config._config_path = yaml_file

    if len(expected_kw.get("mcp_client_toolset_configs", {})) > 0:
        for mcts_config in expected_kw["mcp_client_toolset_configs"].values():
            mcts_config._installation_config = installation_config
            mcts_config._config_path = yaml_file

    if "quizzes" in config_yaml:
        expected.quizzes = [
            dataclasses.replace(
                qc,
                _installation_config=installation_config,
                _config_path=yaml_file,
            )
            for qc in expected.quizzes
        ]

    with yaml_file.open() as stream:
        yaml_dict = yaml.safe_load(stream)

    found = config.RoomConfig.from_yaml(
        installation_config,
        yaml_file,
        yaml_dict,
    )

    assert found == expected


@pytest.mark.parametrize("w_existing", [False, True])
def test_roomconfig_quiz_map(w_existing):
    NUM_QUIZZES = 3
    quizzes = [
        mock.create_autospec(
            config.QuizConfig,
            id=f"quiz-{iq}",
            question_file=f"ignored-{iq}.json",
        )
        for iq in range(NUM_QUIZZES)
    ]

    existing = object()
    room_config = config.RoomConfig(**BARE_ROOM_CONFIG_KW)

    if w_existing:
        room_config._quiz_map = existing
    else:
        room_config.quizzes = quizzes

    found = room_config.quiz_map

    if w_existing:
        assert found is existing

    else:
        for (_f_id, f_quiz), e_quiz in zip(
            found.items(),
            quizzes,
            strict=True,
        ):
            assert f_quiz is e_quiz


@pytest.mark.parametrize("w_order", [False, True])
def test_roomconfig_sort_key(w_order):
    _ORDER = "explicitly_ordered"

    room_config_kw = BARE_ROOM_CONFIG_KW.copy()

    if w_order:
        room_config_kw["_order"] = _ORDER

    room_config = config.RoomConfig(**room_config_kw)

    found = room_config.sort_key

    if w_order:
        assert found == _ORDER
    else:
        assert found == ROOM_ID


@pytest.mark.parametrize("w_config_path", [False, True])
@pytest.mark.parametrize(
    "room_config_kw",
    [BARE_ROOM_CONFIG_KW, FULL_ROOM_CONFIG_KW],
)
def test_roomconfig_get_logo_image(temp_dir, room_config_kw, w_config_path):
    room_config_kw = room_config_kw.copy()

    if w_config_path:
        room_config_kw["_config_path"] = temp_dir / "room_config.yaml"

    room_config = config.RoomConfig(**room_config_kw)

    if room_config._config_path:
        if room_config._logo_image is not None:
            expected = temp_dir / room_config._logo_image
        else:
            expected = None

        found = room_config.get_logo_image()

        assert found == expected

    else:
        if room_config._logo_image is not None:
            with pytest.raises(config.NoConfigPath):
                room_config.get_logo_image()

        else:
            assert room_config.get_logo_image() is None


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BARE_COMPLETION_CONFIG_YAML, BARE_COMPLETION_CONFIG_KW),
        (FULL_COMPLETION_CONFIG_YAML, FULL_COMPLETION_CONFIG_KW),
    ],
)
def test_completionconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    if "name" not in expected_kw:
        expected_kw = expected_kw.copy()
        expected_kw["name"] = expected_kw["id"]

    expected = config.CompletionConfig(**expected_kw)

    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)
    expected = dataclasses.replace(
        expected,
        _installation_config=installation_config,
        _config_path=yaml_file,
    )
    expected.agent_config = dataclasses.replace(
        expected.agent_config,
        _installation_config=installation_config,
        _config_path=yaml_file,
    )

    if len(expected_kw.get("tool_configs", {})) > 0:
        for tool_config in expected_kw["tool_configs"].values():
            tool_config._installation_config = installation_config
            tool_config._config_path = yaml_file

    if len(expected_kw.get("mcp_client_toolset_configs", {})) > 0:
        for mcts_config in expected_kw["mcp_client_toolset_configs"].values():
            mcts_config._installation_config = installation_config
            mcts_config._config_path = yaml_file

    with yaml_file.open() as stream:
        yaml_dict = yaml.safe_load(stream)

    found = config.CompletionConfig.from_yaml(
        installation_config,
        yaml_file,
        yaml_dict,
    )

    assert found == expected


@pytest.mark.parametrize(
    "w_params, exp_env_var_name",
    [
        ({}, SECRET_NAME),
        ({"env_var_name": ENV_VAR_NAME}, ENV_VAR_NAME),
    ],
)
def test_envvar_secret_source_ctor(w_params, exp_env_var_name):
    source = config.EnvVarSecretSource(SECRET_NAME, **w_params)
    assert source.env_var_name == exp_env_var_name


@pytest.mark.parametrize("yaml_config", [{}, {"env_var_name": ENV_VAR_NAME}])
def test_envvarsecretsource_from_yaml(temp_dir, yaml_config):
    config_path = temp_dir / "installation.yaml"
    yaml_config["secret_name"] = SECRET_NAME

    source = config.EnvVarSecretSource.from_yaml(config_path, yaml_config)

    assert source._config_path == config_path
    assert source.secret_name == SECRET_NAME

    if "env_var_name" in yaml_config:
        assert source.env_var_name == ENV_VAR_NAME
    else:
        assert source.env_var_name == SECRET_NAME


@pytest.mark.parametrize("file_path", ["/path/to/file", "./file"])
def test_filepathsecretsource_from_yaml(temp_dir, file_path):
    config_path = temp_dir / "installation.yaml"
    yaml_config = {"secret_name": SECRET_NAME, "file_path": file_path}

    source = config.FilePathSecretSource.from_yaml(config_path, yaml_config)

    assert source._config_path == config_path
    assert source.secret_name == SECRET_NAME
    assert source.file_path == file_path


@pytest.mark.parametrize(
    "w_args, exp_command_line",
    [
        ((), COMMAND),
        (["-a", "foo"], f"{COMMAND} -a foo"),
    ],
)
def test_subprocess_secret_source_command_line(w_args, exp_command_line):
    source = config.SubprocessSecretSource(SECRET_NAME, COMMAND, w_args)
    assert source.command_line == exp_command_line


@pytest.mark.parametrize(
    "w_sources, exp_sources",
    [
        (None, [config.EnvVarSecretSource(SECRET_NAME)]),
        ([config.EnvVarSecretSource(SECRET_NAME, ENV_VAR_NAME)], None),
    ],
)
def test_secretconfig_ctor(w_sources, exp_sources):
    if exp_sources is None:
        exp_sources = w_sources

    secret = config.SecretConfig(SECRET_NAME, w_sources)

    assert secret.secret_name == SECRET_NAME
    assert secret.sources == exp_sources


def test__load_config_yaml_w_missing(temp_dir):
    config_path = temp_dir / "oidc"
    config_path.mkdir()
    missing_cfg = config_path / "config.yaml"

    with pytest.raises(config.NoSuchConfig) as exc:
        config._load_config_yaml(missing_cfg)

    assert exc.value.config_path == missing_cfg


@pytest.mark.parametrize(
    "invalid",
    [
        b"\xde\xad\xbe\xef",  # raises UnicodeDecodeError
        "",  # parses as None
        "123",  # parses as int
        "4.56",  # parses as float
        '"foo"',  # parses as str
        '- "abc"\n- "def"',  # parses as list of str
    ],
)
def test__load_config_yaml_w_invalid(temp_dir, invalid):
    config_path = temp_dir / "oidc"
    config_path.mkdir()
    invalid_cfg = config_path / "config.yaml"

    if isinstance(invalid, bytes):
        invalid_cfg.write_bytes(invalid)
    else:
        invalid_cfg.write_text(invalid)

    with pytest.raises(config.FromYamlException) as exc:
        config._load_config_yaml(invalid_cfg)

    assert exc.value.config_path == invalid_cfg


def test__find_configs_w_single(temp_dir):
    THING_ID = "testing"
    CONFIG_FILENAME = "config.yaml"
    to_search = temp_dir / "to_search"
    to_search.mkdir()
    config_file = to_search / CONFIG_FILENAME
    config_file.write_text(f"id: {THING_ID}")
    expected = {"id": THING_ID}

    found = list(config._find_configs(to_search, CONFIG_FILENAME))

    assert found == [(config_file, expected)]


def test__find_configs_w_multiple(temp_dir):
    THING_IDS = ["foo", "bar", "baz", "qux"]
    CONFIG_FILENAME = "config.yaml"

    expected_things = []

    for thing_id in sorted(THING_IDS):
        thing_path = temp_dir / thing_id
        if thing_id == "baz":  # file, not dir
            thing_path.write_text("DEADBEEF")
        elif thing_id == "qux":  # empty dir
            thing_path.mkdir()
        else:
            thing_path.mkdir()
            config_file = thing_path / CONFIG_FILENAME
            config_file.write_text(f"id: {thing_id}")
            expected_thing = {"id": thing_id}
            expected_things.append((config_file, expected_thing))

    found_things = list(config._find_configs(temp_dir, CONFIG_FILENAME))

    for (f_key, f_thing), (e_key, e_thing) in zip(
        sorted(found_things),
        sorted(expected_things),
        strict=True,
    ):
        assert f_key == e_key
        assert f_thing == e_thing


NoRaise = contextlib.nullcontext()
NotASecret = pytest.raises(config.NotASecret)


@pytest.mark.parametrize(
    "secret_name_exp_pfx, expectation, expected",
    [
        ("secret:test", NoRaise, "test"),
        ("invalid", NotASecret, None),
    ],
)
def test_strip_secret_prefix(secret_name_exp_pfx, expectation, expected):
    with expectation:
        found = config.strip_secret_prefix(secret_name_exp_pfx)

    if expected is not None:
        assert found == expected


def test_installationconfig_secrets_map_wo_existing():
    secrets = [
        mock.create_autospec(
            config.SecretConfig,
            secret_name=f"secret-{i_secret}",
        )
        for i_secret in range(5)
    ]

    i_config = config.InstallationConfig(id="test-ic", secrets=secrets)

    found = i_config.secrets_map

    for (_f_key, f_val), secret in zip(
        sorted(found.items()),
        secrets,
        strict=True,
    ):
        assert f_val is secret


def test_installationconfig_secrets_map_w_existing():
    already = object()
    i_config = config.InstallationConfig(id="test-ic", _secrets_map=already)

    found = i_config.secrets_map

    assert found is already


NoSuchSecret = pytest.raises(KeyError)
NoRaise = contextlib.nullcontext()


@pytest.mark.parametrize(
    "secret_map, expectation",
    [
        ({}, NoSuchSecret),
        ({SECRET_NAME_1: SECRET_CONFIG_1}, NoRaise),
    ],
)
@mock.patch("soliplex.secrets.get_secret")
def test_installationconfig_get_secret(gs, secret_map, expectation):
    i_config = config.InstallationConfig(
        id="test-ic",
        _secrets_map=secret_map,
    )

    with mock.patch("os.environ", clear=True):
        with expectation as expected:
            found = i_config.get_secret(f"secret:{SECRET_NAME_1}")

    if expected is None:
        assert found is gs.return_value
        gs.assert_called_once_with(SECRET_CONFIG_1)
    else:
        gs.assert_not_called()


@pytest.mark.parametrize("w_default", [False, True])
@pytest.mark.parametrize("w_hit", [False, True])
def test_installationconfig_get_environment(w_hit, w_default):
    KEY = "test-key"
    VALUE = "test-value"
    DEFAULT = "test-default"

    kwargs = {}

    if w_default:
        kwargs["default"] = DEFAULT

    i_config = config.InstallationConfig(id="test-ic")

    if w_hit:
        i_config.environment[KEY] = VALUE

    found = i_config.get_environment(KEY, **kwargs)

    if w_hit:
        assert found == VALUE
    elif w_default:
        assert found == DEFAULT
    else:
        assert found is None


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BARE_INSTALLATION_CONFIG_YAML, BARE_INSTALLATION_CONFIG_KW),
        (
            W_SECRETS_INSTALLATION_CONFIG_YAML,
            W_SECRETS_INSTALLATION_CONFIG_KW,
        ),
        (
            W_ENVIRONMENT_LIST_INSTALLATION_CONFIG_YAML,
            W_ENVIRONMENT_INSTALLATION_CONFIG_KW,
        ),
        (
            W_ENVIRONMENT_MAPPING_INSTALLATION_CONFIG_YAML,
            W_ENVIRONMENT_INSTALLATION_CONFIG_KW,
        ),
        (
            W_OIDC_PATHS_INSTALLATION_CONFIG_YAML,
            W_OIDC_PATHS_INSTALLATION_CONFIG_KW,
        ),
        (
            W_OIDC_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML,
            W_OIDC_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW,
        ),
        (
            W_ROOM_PATHS_INSTALLATION_CONFIG_YAML,
            W_ROOM_PATHS_INSTALLATION_CONFIG_KW,
        ),
        (
            W_ROOM_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML,
            W_ROOM_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW,
        ),
        (
            W_COMPLETION_PATHS_INSTALLATION_CONFIG_YAML,
            W_COMPLETION_PATHS_INSTALLATION_CONFIG_KW,
        ),
        (
            W_COMPLETION_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML,
            W_COMPLETION_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW,
        ),
        (
            W_QUIZZES_PATHS_INSTALLATION_CONFIG_YAML,
            W_QUIZZES_PATHS_INSTALLATION_CONFIG_KW,
        ),
        (
            W_QUIZZES_PATHS_ONLY_NULL_INSTALLATION_CONFIG_YAML,
            W_QUIZZES_PATHS_ONLY_NULL_INSTALLATION_CONFIG_KW,
        ),
    ],
)
def test_installationconfig_from_yaml(
    temp_dir,
    config_yaml,
    expected_kw,
):
    expected = config.InstallationConfig(**expected_kw)

    yaml_file = temp_dir / "installation.yaml"
    yaml_file.write_text(config_yaml)
    expected = dataclasses.replace(
        expected,
        _config_path=yaml_file,
    )

    if "secrets" in expected_kw:
        replaced_secrets = []
        for secret in expected.secrets:
            replaced_sources = [
                dataclasses.replace(source, _config_path=yaml_file)
                for source in secret.sources
            ]
            replaced_secrets.append(
                dataclasses.replace(
                    secret,
                    sources=replaced_sources,
                    _config_path=yaml_file,
                )
            )
        expected = dataclasses.replace(expected, secrets=replaced_secrets)

    if "oidc_paths" in expected_kw:
        exp_oidc_paths = [
            temp_dir / oidc_path for oidc_path in expected_kw["oidc_paths"]
        ]
    else:
        exp_oidc_paths = [temp_dir / "oidc"]

    expected = dataclasses.replace(expected, oidc_paths=exp_oidc_paths)

    if "room_paths" in expected_kw:
        exp_room_paths = [
            temp_dir / room_path for room_path in expected_kw["room_paths"]
        ]
    else:
        exp_room_paths = [temp_dir / "rooms"]

    expected = dataclasses.replace(expected, room_paths=exp_room_paths)

    with yaml_file.open() as stream:
        yaml_dict = yaml.safe_load(stream)

    found = config.InstallationConfig.from_yaml(yaml_file, yaml_dict)

    assert found == expected


def test_installationconfig_from_yaml_w_dotenv(temp_dir):
    REPLACEMENT = "other value"
    DOTENV_TEXT = f"""
{CONFIG_KEY_1}={REPLACEMENT}
IGNORED=bogus
"""
    dotenv_file = temp_dir / ".env"
    dotenv_file.write_text(DOTENV_TEXT)

    config_yaml = W_ENVIRONMENT_MAPPING_INSTALLATION_CONFIG_YAML
    yaml_file = temp_dir / "installation.yaml"
    yaml_file.write_text(config_yaml)

    expected_kw = W_ENVIRONMENT_INSTALLATION_CONFIG_KW.copy()
    expected_kw["environment"][CONFIG_KEY_1] = REPLACEMENT
    expected = config.InstallationConfig(**expected_kw)
    expected = dataclasses.replace(
        expected,
        _config_path=yaml_file,
        oidc_paths=[temp_dir / "oidc"],
        room_paths=[temp_dir / "rooms"],
        completion_paths=[temp_dir / "completions"],
        quizzes_paths=[temp_dir / "quizzes"],
    )

    with yaml_file.open() as stream:
        yaml_dict = yaml.safe_load(stream)

    found = config.InstallationConfig.from_yaml(yaml_file, yaml_dict)

    assert found == expected


@pytest.mark.parametrize(
    "w_pem_path",
    [
        ABSOLUTE_OIDC_CLIENT_PEM_PATH,
        RELATIVE_OIDC_CLIENT_PEM_PATH,
    ],
)
@pytest.mark.parametrize("w_pem", [False, "bare_top", "bare_authsys"])
@mock.patch("soliplex.config._load_config_yaml")
def test_installationconfig_oidc_auth_system_configs_wo_existing(
    lcy,
    temp_dir,
    w_pem,
    w_pem_path,
):
    if w_pem_path.startswith("."):
        exp_oidc_client_pem_path = temp_dir / "oidc_bare" / w_pem_path
    else:
        exp_oidc_client_pem_path = pathlib.Path(w_pem_path)

    bare_config_yaml = {
        "auth_systems": [BARE_AUTHSYSTEM_CONFIG_KW.copy()],
    }

    if w_pem == "bare_top":
        bare_config_yaml["oidc_client_pem_path"] = w_pem_path
    elif w_pem == "bare_authsys":
        authsys = bare_config_yaml["auth_systems"][0]
        authsys["oidc_client_pem_path"] = w_pem_path
    else:
        assert not w_pem
        exp_oidc_client_pem_path = None

    w_scope_config_yaml = {
        "auth_systems": [W_SCOPE_AUTHSYSTEM_CONFIG_KW.copy()],
    }

    lcy.side_effect = [bare_config_yaml, w_scope_config_yaml]

    oidc_bare_path = temp_dir / "oidc_bare"
    oidc_bare_config = oidc_bare_path / "config.yaml"

    oidc_w_scope_path = temp_dir / "oidc_w_scope"
    oidc_w_scope_config = oidc_w_scope_path / "config.yaml"

    oidc_bare_kw = BARE_AUTHSYSTEM_CONFIG_KW.copy()
    oidc_bare_kw["oidc_client_pem_path"] = exp_oidc_client_pem_path
    oidc_bare_kw["_config_path"] = oidc_bare_config

    oidc_w_scope_kw = W_SCOPE_AUTHSYSTEM_CONFIG_KW.copy()
    oidc_w_scope_kw["oidc_client_pem_path"] = None
    oidc_w_scope_kw["_config_path"] = oidc_w_scope_config

    i_config_kw = BARE_INSTALLATION_CONFIG_KW.copy()
    i_config_kw["oidc_paths"] = [oidc_bare_path, oidc_w_scope_path]

    i_config = config.InstallationConfig(**i_config_kw)

    expected = [
        config.OIDCAuthSystemConfig(
            _installation_config=i_config,
            **oidc_bare_kw,
        ),
        config.OIDCAuthSystemConfig(
            _installation_config=i_config,
            **oidc_w_scope_kw,
        ),
    ]

    found = i_config.oidc_auth_system_configs

    for f_asc, e_asc in zip(found, expected, strict=True):
        assert f_asc == e_asc


def test_installationconfig_oidc_auth_system_configs_w_existing():
    OASC_1, OASC_2 = object(), object()

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_oidc_auth_system_configs"] = [OASC_1, OASC_2]

    i_config = config.InstallationConfig(**kw)

    found = i_config.oidc_auth_system_configs

    assert found == [OASC_1, OASC_2]


def test_installationconfig_room_configs_wo_existing(temp_dir):
    ROOM_IDS = ["foo", "bar"]

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_config_path"] = temp_dir / "installation.yaml"
    kw["environment"] = BARE_INSTALLATION_CONFIG_ENVIRONMENT

    rooms = temp_dir / "rooms"
    rooms.mkdir()

    for room_id in ROOM_IDS:
        room_path = rooms / room_id
        room_path.mkdir()
        room_config = room_path / "room_config.yaml"
        room_config.write_text(
            BARE_ROOM_CONFIG_YAML.replace(
                f'id: "{ROOM_ID}"',
                f'id: "{room_id}"',
                1,
            ),
        )

    i_config = config.InstallationConfig(**kw)

    found = i_config.room_configs

    assert found["foo"].id == "foo"
    assert found["bar"].id == "bar"


def test_installationconfig_room_configs_wo_existing_w_conflict(temp_dir):
    ROOM_PATHS = ["./foo", "./bar"]

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_config_path"] = temp_dir / "installation.yaml"
    kw["environment"] = BARE_INSTALLATION_CONFIG_ENVIRONMENT
    kw["room_paths"] = ROOM_PATHS

    for room_path in ROOM_PATHS:
        room_path = temp_dir / room_path
        room_path.mkdir()
        room_config = room_path / "room_config.yaml"
        room_config.write_text(
            BARE_ROOM_CONFIG_YAML.replace(
                # f'id: "{ROOM_ID}"', f'id: "{room_id}"', 1, # conflict on ID
                f'name: "{ROOM_NAME}"',
                f'name: "{room_path.name}"',
                1,
            )
        )

    i_config = config.InstallationConfig(**kw)

    found = i_config.room_configs

    assert found[ROOM_ID].id == ROOM_ID
    # order of 'room_paths' governs who wins
    assert found[ROOM_ID].name == "foo"


def test_installationconfig_room_configs_w_existing():
    RC_1, RC_2 = object(), object()
    existing = {"room_1": RC_1, "room_2": RC_2}

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_room_configs"] = existing

    i_config = config.InstallationConfig(**kw)

    found = i_config.room_configs

    assert found["room_1"] == RC_1
    assert found["room_2"] == RC_2


def test_installationconfig_completion_configs_wo_existing(temp_dir):
    COMPLETION_IDS = ["foo", "bar"]

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_config_path"] = temp_dir / "installation.yaml"
    kw["environment"] = BARE_INSTALLATION_CONFIG_ENVIRONMENT

    completions = temp_dir / "completions"
    completions.mkdir()

    for completion_id in COMPLETION_IDS:
        completion_path = completions / completion_id
        completion_path.mkdir()
        completion_config = completion_path / "completion_config.yaml"
        completion_config.write_text(
            BARE_COMPLETION_CONFIG_YAML.replace(
                f'id: "{COMPLETION_ID}"',
                f'id: "{completion_id}"',
                1,
            ),
        )

    i_config = config.InstallationConfig(**kw)

    found = i_config.completion_configs

    assert found["foo"].id == "foo"
    assert found["bar"].id == "bar"


def test_installationconfig_completion_configs_wo_existing_w_conflict(
    temp_dir,
):
    COMPLETION_PATHS = ["./foo", "./bar"]

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_config_path"] = temp_dir / "installation.yaml"
    kw["environment"] = BARE_INSTALLATION_CONFIG_ENVIRONMENT
    kw["completion_paths"] = COMPLETION_PATHS

    for completion_path in COMPLETION_PATHS:
        completion_path = temp_dir / completion_path
        completion_path.mkdir()
        completion_config = completion_path / "completion_config.yaml"
        completion_config.write_text(
            FULL_COMPLETION_CONFIG_YAML.replace(
                # f'id: "{COMPLETION_ID}"',
                # f'id: "{completion_id}"',
                # 1, # conflict on ID
                f'name: "{COMPLETION_NAME}"',
                f'name: "{completion_path.name}"',
                1,
            )
        )

    i_config = config.InstallationConfig(**kw)

    found = i_config.completion_configs

    assert found[COMPLETION_ID].id == COMPLETION_ID
    # order of 'completion_paths' governs who wins
    assert found[COMPLETION_ID].name == "foo"


def test_installationconfig_completion_configs_w_existing():
    CC_1, CC_2 = object(), object()
    existing = {"completion_1": CC_1, "completion_2": CC_2}

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_completion_configs"] = existing

    i_config = config.InstallationConfig(**kw)

    found = i_config.completion_configs

    assert found["completion_1"] == CC_1
    assert found["completion_2"] == CC_2


def test_installationconfig_reload_configurations():
    existing = object()

    kw = BARE_INSTALLATION_CONFIG_KW.copy()
    kw["_oidc_auth_system_configs"] = existing
    kw["_room_configs"] = existing
    kw["_completion_configs"] = existing
    i_config = config.InstallationConfig(**kw)

    with mock.patch.multiple(
        i_config,
        _load_oidc_auth_system_configs=mock.DEFAULT,
        _load_room_configs=mock.DEFAULT,
        _load_completion_configs=mock.DEFAULT,
    ) as patched:
        i_config.reload_configurations()

    assert (
        i_config._oidc_auth_system_configs
        is patched["_load_oidc_auth_system_configs"].return_value
    )

    assert i_config._room_configs is patched["_load_room_configs"].return_value

    assert (
        i_config._completion_configs
        is patched["_load_completion_configs"].return_value
    )


@pytest.fixture
def populated_temp_dir(temp_dir):
    default = temp_dir / "installation.yaml"
    default.write_text('id: "testing"')

    not_a_yaml_file = temp_dir / "not_a_yaml_file.yaml"
    not_a_yaml_file.write_bytes(b"\xde\xad\xbe\xef")

    there_but_no_config = temp_dir / "there-but-no-config"
    there_but_no_config.mkdir()

    there_with_config = temp_dir / "there-with-config"
    there_with_config.mkdir()
    there_with_config_filename = there_with_config / "installation.yaml"
    there_with_config_filename.write_text('id: "there-with-config"')

    alt_config = temp_dir / "alt-config"
    alt_config.mkdir()
    alt_config_filename = alt_config / "filename.yaml"
    alt_config_filename.write_text('id: "alt-config"')

    return temp_dir


@pytest.mark.parametrize(
    "rel_path, raises, expected_id",
    [
        (".", False, "testing"),
        ("./installation.yaml", False, "testing"),
        ("no_such_filename.yaml", config.NoSuchConfig, None),
        ("not_a_yaml_file.yaml", config.FromYamlException, None),
        ("/dev/null", config.NoSuchConfig, None),
        ("./not-there", config.NoSuchConfig, None),
        ("./there-but-no-config", config.NoSuchConfig, None),
        ("./there-with-config", False, "there-with-config"),
        ("./alt-config/filename.yaml", False, "alt-config"),
    ],
)
def test_load_installation(populated_temp_dir, rel_path, raises, expected_id):
    target = populated_temp_dir / rel_path

    if raises:
        with pytest.raises(raises):
            config.load_installation(target)

    else:
        installation = config.load_installation(target)

        assert installation.id == expected_id
