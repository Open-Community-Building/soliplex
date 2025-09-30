import dataclasses
import json
import pathlib
import uuid
from unittest import mock

import pytest

from soliplex import config
from soliplex import convos
from soliplex import models
from soliplex import tools

QUIZ_ID = "test_quiz"
QUIZ_TITLE = "Test Quiz"
QUIZ_MAX_QUESTIONS = 14
QUIZ_PATH_OVERRIDE = "/dev/null"
INPUTS = "What color is the sky"
EXPECTED_ANSWER = "Blue"
QA_QUESTION_UUID = "DEADBEEF"
MC_QUESTION_UUID = "FACEDACE"
QUESTION_TYPE_QA = "qa"
QUESTION_TYPE_MC = "multiple-choice"
MC_OPTIONS = ["orange", "blue", "purple"]

ROOM_ID = "test_room"
ROOM_NAME = "Test Room"
ROOM_DESCRIPTION = "This room is made for testing"
ROOM_WELCOME = "Welcome!"
ROOM_SUGGESTION = "Why is the sky blue?"

COMPLETION_ID = "test_room"
COMPLETION_NAME = "Test Room"

AGENT_ID = "test_agent"
AGENT_MODEL = "test_model"
AGENT_PROMPT = "You are a test"
AGENT_BASE_URL = "https://provider.example.com/base"
OLLAMA_BASE_URL = "https://ollama.example.com/base"

INSTALLATION_ID = "test-installation"
INSTALLATION_SECRET = "Seeeeeekrit!"
INSTALLATION_ENVVAR_NAME = "TEST_ENVVAR"
INSTALLATION_ENVVAR_VALUE = "Test Envvar"
INSTALLATION_OIDC_PATH = pathlib.Path("/path/to/oidc")
INSTALLATION_ROOM_PATH = pathlib.Path("/path/to/rooms")
INSTALLATION_COMPLETION_PATH = pathlib.Path("/path/to/completions")
INSTALLATION_QUIZZES_PATH = pathlib.Path("/path/to/quizzes")

INSTALLATION_OIDC_AUTH_SYSTEM_ID = "oidc-test"
INSTALLATION_OIDC_AUTH_SYSTEM_TITLE = "OIDC Test"
INSTALLATION_OIDC_AUTH_SYSTEM_SERVER_URL = "https://oidc.example.com/"
INSTALLATION_OIDC_AUTH_SYSTEM_TOKEN_VALIDATION_PEM = "PEM GOES HERE"
INSTALLATION_OIDC_AUTH_SYSTEM_CLIENT_ID = "oicd-client-test"
INSTALLATION_OIDC_AUTH_SYSTEM_SCOPE = "oicd-client-scope"
INSTALLATION_OIDC_AUTH_SYSTEM_CONFIG = config.OIDCAuthSystemConfig(
    id=INSTALLATION_OIDC_AUTH_SYSTEM_ID,
    title=INSTALLATION_OIDC_AUTH_SYSTEM_TITLE,
    server_url=INSTALLATION_OIDC_AUTH_SYSTEM_SERVER_URL,
    token_validation_pem=INSTALLATION_OIDC_AUTH_SYSTEM_TOKEN_VALIDATION_PEM,
    client_id=INSTALLATION_OIDC_AUTH_SYSTEM_CLIENT_ID,
    client_secret="SHHHHHHH! DON't SHOW ME",
    scope=INSTALLATION_OIDC_AUTH_SYSTEM_SCOPE,
)

CONVO_UUID = uuid.uuid4()
USER_TEXT = "Why is the sky blue?"
CONVO_NAME = USER_TEXT
CONVO_ROOM_ID = "test-room"
TIMESTAMP = "2025-09-30T18:18:27Z"


def _from_param(request, key):
    kw = {}
    if request.param is not None:
        kw[key] = request.param
    return kw


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
def quiz_path(temp_dir, quiz_json):
    quizzes_path = temp_dir / "quizzes"
    quizzes_path.mkdir()
    populated_quiz = quizzes_path / f"{QUIZ_ID}.json"
    populated_quiz.write_text(json.dumps(quiz_json))
    return populated_quiz


@pytest.fixture(params=[None, False, True])
def quiz_randomize(request):
    return _from_param(request, "randomize")


@pytest.fixture(params=[None, QUIZ_MAX_QUESTIONS])
def quiz_max_questions(request):
    return _from_param(request, "max_questions")


def test_quiz_from_config(
    quiz_path,
    quiz_json,
    quiz_questions,
    quiz_randomize,
    quiz_max_questions,
):
    quiz_config = config.QuizConfig(
        id=QUIZ_ID,
        title=QUIZ_TITLE,
        _question_file_path_override=str(quiz_path),
        **quiz_randomize,
        **quiz_max_questions,
    )

    quiz_model = models.Quiz.from_config(quiz_config)

    assert quiz_model.id == QUIZ_ID
    assert quiz_model.title == QUIZ_TITLE

    if quiz_randomize:
        assert quiz_model.randomize == quiz_randomize["randomize"]
    else:
        assert quiz_model.randomize is False

    if quiz_max_questions:
        assert quiz_model.max_questions == quiz_max_questions["max_questions"]
    else:
        assert quiz_model.max_questions is None

    if quiz_randomize:
        for expected in quiz_questions:
            assert expected in quiz_model.questions
    else:
        assert quiz_model.questions == quiz_questions


def test_tool_from_config_w_toolconfig():
    def test_tool():
        """This is a test tool"""

    tool_config = config.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        tool_model = models.Tool.from_config(tool_config)

    assert tool_model.kind == "test_tool"
    assert tool_model.tool_name == "soliplex.tools.test_tool"
    assert tool_model.tool_description == test_tool.__doc__.strip()
    assert tool_model.tool_requires == config.ToolRequires.BARE
    assert tool_model.allow_mcp is False
    assert tool_model.extra_parameters == {}


def test_tool_from_config_w_sdtc(temp_dir):
    sdtc_rag_lance_db_path = temp_dir / "rag.lancedb"
    sdtc_rag_lance_db_path.mkdir()

    tool_config = config.SearchDocumentsToolConfig(
        rag_lancedb_override_path=str(sdtc_rag_lance_db_path),
        expand_context_radius=3,
        search_documents_limit=7,
        return_citations=True,
        allow_mcp=True,
    )

    tool_model = models.Tool.from_config(tool_config)

    assert tool_model.kind == "search_documents"
    assert tool_model.tool_name == "soliplex.tools.search_documents"
    assert (
        tool_model.tool_description == tools.search_documents.__doc__.strip()
    )
    assert tool_model.tool_requires == config.ToolRequires.TOOL_CONFIG
    assert tool_model.allow_mcp is True
    assert tool_model.extra_parameters == dict(
        rag_lancedb_path=sdtc_rag_lance_db_path,
        expand_context_radius=3,
        search_documents_limit=7,
        return_citations=True,
    )


def test_mcp_client_toolset_from_config_w_toolconfig():
    def test_tool():
        """This is a test tool"""

    mcp_ct_config = config.Stdio_MCP_ClientToolsetConfig(
        command="cat",
        args=["-"],
        env={"foo": "env:not_in_my_environment_really"},
    )

    toolset_model = models.MCPClientToolset.from_config(mcp_ct_config)

    assert toolset_model.kind == mcp_ct_config.kind
    assert toolset_model.allowed_tools == mcp_ct_config.allowed_tools

    params = toolset_model.toolset_params
    assert params["command"] == mcp_ct_config.command
    assert params["args"] == mcp_ct_config.args
    # No interpolation!
    assert params["env"] == mcp_ct_config.env


def test_mcp_client_toolset_from_config_w_sdtc():
    mcp_ct_config = config.HTTP_MCP_ClientToolsetConfig(
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer env:{BEARER_TOKEN}"},
        query_params={"foo": "env:not_in_my_environment_really"},
    )

    toolset_model = models.MCPClientToolset.from_config(mcp_ct_config)

    assert toolset_model.kind == mcp_ct_config.kind
    assert toolset_model.allowed_tools == mcp_ct_config.allowed_tools

    params = toolset_model.toolset_params
    assert params["url"] == mcp_ct_config.url
    # No interpolation on either of these!
    assert params["headers"] == mcp_ct_config.headers
    assert params["query_params"] == mcp_ct_config.query_params


@pytest.fixture(params=[*config.LLMProviderType])
def agent_provider_type(request):
    return _from_param(request, "provider_type")


@pytest.fixture(params=[None, AGENT_BASE_URL])
def agent_provider_base_url(request):
    return _from_param(request, "provider_base_url")


@pytest.fixture
def installation_config():
    environ = {"OLLAMA_BASE_URL": OLLAMA_BASE_URL}
    installation = mock.create_autospec(config.InstallationConfig)
    installation.get_environment = environ.get
    return installation


def test_agent_from_config(
    agent_provider_type,
    agent_provider_base_url,
    installation_config,
):
    agent_config = config.AgentConfig(
        id=AGENT_ID,
        model_name=AGENT_MODEL,
        system_prompt=AGENT_PROMPT,
        _installation_config=installation_config,
        **agent_provider_type,
        **agent_provider_base_url,
    )

    if not agent_provider_base_url:
        exp_base = f"{OLLAMA_BASE_URL}/v1"
    else:
        exp_base = f"{AGENT_BASE_URL}/v1"

    agent_model = models.Agent.from_config(agent_config)

    assert agent_model.id == AGENT_ID
    assert agent_model.model_name == AGENT_MODEL
    assert agent_model.system_prompt == AGENT_PROMPT
    assert agent_model.provider_base_url == exp_base


@pytest.fixture(params=[None, ROOM_WELCOME])
def room_welcome(request):
    return _from_param(request, "welcome_message")


@pytest.fixture(params=[None, [ROOM_SUGGESTION]])
def room_suggestions(request):
    return _from_param(request, "suggestions")


@pytest.fixture(params=[False, True])
def room_tools(request):
    kw = {}
    if request.param:
        kw["tool_configs"] = {
            "get_current_datetime": config.ToolConfig(
                tool_name="soliplex.tools.get_current_datetime",
            ),
        }
    return kw


@pytest.fixture(params=[False, True])
def room_quizzes(request, quiz_path):
    kw = {}
    if request.param:
        kw["quizzes"] = [
            config.QuizConfig(
                id=QUIZ_ID,
                title=QUIZ_TITLE,
                _question_file_path_override=str(quiz_path),
            )
        ]
    return kw


@pytest.fixture
def room_agent(installation_config):
    return config.AgentConfig(
        id=AGENT_ID,
        model_name=AGENT_MODEL,
        system_prompt=AGENT_PROMPT,
        _installation_config=installation_config,
    )


def test_room_from_config(
    room_agent,
    room_welcome,
    room_suggestions,
    room_tools,
    room_quizzes,
):
    room_config = config.RoomConfig(
        id=ROOM_ID,
        name=ROOM_NAME,
        description=ROOM_DESCRIPTION,
        agent_config=room_agent,
        **room_welcome,
        **room_suggestions,
        **room_tools,
        **room_quizzes,
    )

    room_model = models.Room.from_config(room_config)

    assert room_model.id == ROOM_ID
    assert room_model.name == ROOM_NAME
    assert room_model.description == ROOM_DESCRIPTION

    assert room_model.agent.id == AGENT_ID
    assert room_model.agent.model_name == AGENT_MODEL
    assert room_model.agent.system_prompt == AGENT_PROMPT

    if room_welcome:
        assert room_model.welcome_message == room_welcome["welcome_message"]
    else:
        assert room_model.welcome_message == ROOM_DESCRIPTION

    if room_suggestions:
        assert room_model.suggestions == room_suggestions["suggestions"]
    else:
        assert room_model.suggestions == []

    if room_tools:
        assert room_model.tools == {
            key: models.Tool.from_config(tool_config)
            for (key, tool_config) in room_tools["tool_configs"].items()
        }
    else:
        assert room_model.tools == {}

    if room_quizzes:
        assert room_model.quizzes == {
            quiz.id: models.Quiz.from_config(quiz)
            for quiz in room_quizzes["quizzes"]
        }
    else:
        assert room_model.quizzes == {}


def test_completion_from_config(room_agent, room_tools):
    completion_config = config.CompletionConfig(
        id=COMPLETION_ID,
        name=COMPLETION_NAME,
        agent_config=room_agent,
        **room_tools,
    )

    completion_model = models.Completion.from_config(completion_config)

    assert completion_model.id == ROOM_ID
    assert completion_model.name == ROOM_NAME

    assert completion_model.agent.id == AGENT_ID
    assert completion_model.agent.model_name == AGENT_MODEL
    assert completion_model.agent.system_prompt == AGENT_PROMPT

    if room_tools:
        assert completion_model.tools == {
            key: models.Tool.from_config(tool_config)
            for (key, tool_config) in room_tools["tool_configs"].items()
        }
    else:
        assert completion_model.tools == {}


@pytest.fixture(params=[None, [config.SecretConfig(INSTALLATION_SECRET)]])
def installation_secrets(request):
    return _from_param(request, "secrets")


@pytest.fixture(
    params=[
        None,
        {INSTALLATION_ENVVAR_NAME: INSTALLATION_ENVVAR_VALUE},
    ],
)
def installation_environment(request):
    return _from_param(request, "environment")


@pytest.fixture(params=[None, [INSTALLATION_OIDC_PATH]])
def installation_oidc_paths(request):
    return _from_param(request, "oidc_paths")


@pytest.fixture(params=[None, [INSTALLATION_ROOM_PATH]])
def installation_room_paths(request):
    return _from_param(request, "room_paths")


@pytest.fixture(params=[None, [INSTALLATION_COMPLETION_PATH]])
def installation_completion_paths(request):
    return _from_param(request, "completion_paths")


@pytest.fixture(params=[None, [INSTALLATION_QUIZZES_PATH]])
def installation_quizzes_paths(request):
    return _from_param(request, "quizzes_paths")


@pytest.fixture(
    params=[
        None,
        [INSTALLATION_OIDC_AUTH_SYSTEM_CONFIG],
    ],
)
def installation_oidc_auth_system_configs(request):
    kwargs = _from_param(request, "_oidc_auth_system_configs")
    if not kwargs:
        kwargs["_oidc_auth_system_configs"] = []
    return kwargs


def test_installation_from_config(
    installation_secrets,
    installation_environment,
    installation_oidc_paths,
    installation_room_paths,
    installation_completion_paths,
    installation_quizzes_paths,
    installation_oidc_auth_system_configs,
):
    installation_config = config.InstallationConfig(
        id=INSTALLATION_ID,
        **installation_secrets,
        **installation_environment,
        **installation_oidc_paths,
        **installation_room_paths,
        **installation_completion_paths,
        **installation_quizzes_paths,
        **installation_oidc_auth_system_configs,
    )

    installation_model = models.Installation.from_config(installation_config)

    assert installation_model.id == INSTALLATION_ID

    for m_secret, c_secret in zip(
        installation_model.secrets,
        installation_secrets.get("secrets", ()),
        strict=True,
    ):
        assert m_secret.secret_name == c_secret.secret_name

    if installation_environment:
        assert (
            installation_model.environment
            == installation_environment["environment"]
        )
    else:
        assert installation_model.environment == {}

    if installation_oidc_paths:
        assert (
            installation_model.oidc_paths
            == installation_oidc_paths["oidc_paths"]
        )
    else:
        assert installation_model.oidc_paths == [pathlib.Path("oidc")]

    if installation_room_paths:
        assert (
            installation_model.room_paths
            == installation_room_paths["room_paths"]
        )
    else:
        assert installation_model.room_paths == [pathlib.Path("rooms")]

    if installation_completion_paths:
        assert (
            installation_model.completion_paths
            == installation_completion_paths["completion_paths"]
        )
    else:
        assert installation_model.completion_paths == [
            pathlib.Path("completions")
        ]

    if installation_quizzes_paths:
        assert (
            installation_model.quizzes_paths
            == installation_quizzes_paths["quizzes_paths"]
        )
    else:
        assert installation_model.quizzes_paths == [pathlib.Path("quizzes")]

    for found, expected in zip(
        installation_model.oidc_auth_systems,
        installation_oidc_auth_system_configs["_oidc_auth_system_configs"],
        strict=True,
    ):
        assert found.id == expected.id


def test_conversationhistorymessage_from_convos_message():
    convos_message = convos.ConvoHistoryMessage(
        origin="user",
        text=USER_TEXT,
        timestamp=TIMESTAMP,
    )
    message = models.ConvoHistoryMessage.from_convos_message(convos_message)

    assert message.origin == "user"
    assert message.text == USER_TEXT
    assert message.timestamp == TIMESTAMP


def test_conversation_from_convos_info():
    convos_message = convos.ConvoHistoryMessage(
        origin="user",
        text=USER_TEXT,
        timestamp=TIMESTAMP,
    )
    info = convos.ConversationInfo(
        convo_uuid=CONVO_UUID,
        name=CONVO_NAME,
        room_id=CONVO_ROOM_ID,
        message_history=[convos_message],
    )

    convo = models.Conversation.from_convos_info(info)

    assert convo.convo_uuid == CONVO_UUID
    assert convo.name == CONVO_NAME
    assert convo.room_id == CONVO_ROOM_ID

    for f_msg, e_msg in zip(
        convo.message_history,
        info.message_history,
        strict=True,
    ):
        assert f_msg.origin == e_msg.origin
        assert f_msg.text == e_msg.text
        assert f_msg.timestamp == e_msg.timestamp
