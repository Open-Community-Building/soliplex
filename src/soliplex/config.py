from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import functools
import importlib
import inspect
import json
import pathlib
import random
import typing
from collections import abc
from urllib import parse as url_parse

import dotenv
import yaml

SECRET_PREFIX = "secret:"
FILE_PREFIX = "file:"

# ============================================================================
#   Exceptions raised during YAML config processing
# ============================================================================


class FromYamlException(ValueError):
    def __init__(self, config_path):
        self.config_path = config_path
        super().__init__(f"Error in YAML configuration: {config_path}")


class NoConfigPath(ValueError):
    def __init__(self):
        super().__init__("No '_config_path' set")


class NoSuchConfig(ValueError):
    def __init__(self, config_path):
        self.config_path = config_path
        super().__init__(f"Config path is not a YAML file: {config_path}")


class NotADict(ValueError):
    def __init__(self, found):
        self.found = found
        super().__init__(f"YAML did not parse as a dict: {found}")


class ToolRequirementConflict(ValueError):
    def __init__(self, tool_name):
        self.tool_name = tool_name
        super().__init__(
            f"Tool {tool_name} requires both context and tool config"
        )


class RagDbExactlyOneOfStemOrOverride(TypeError):
    _config_path = None

    def __init__(self):
        super().__init__(
            "Configure exactly one of 'rag_lancedb_stem' or "
            "'rag_lancedb_override_path'"
        )


class RagDbFileNotFound(ValueError):
    _config_path = None

    def __init__(self, rag_db_filename):
        self.rag_db_filename = rag_db_filename
        super().__init__(f"RAG DB file not found: {rag_db_filename}")


class QCExactlyOneOfStemOrOverride(TypeError):
    def __init__(self):
        super().__init__(
            "Configure exactly one of '_question_file_stem' or "
            "'_question_file_override_path'"
        )


class QuestionFileNotFoundWithStem(ValueError):
    def __init__(self, stem, quizzes_paths):
        self.stem = stem
        self.quizzes_paths = quizzes_paths
        super().__init__(
            f"'{stem}.json' file not found on paths: "
            f"{','.join([str(qp) for qp in quizzes_paths])}"
        )


class QuestionFileNotFoundWithOverride(ValueError):
    def __init__(self, override):
        self.override = override
        super().__init__(f"'{override}' file not found")


class NotASecret(ValueError):
    def __init__(self, config_str):
        self.config_str = config_str
        super().__init__(
            f"Config '{config_str}' must be prefixed with 'secret:'"
        )


# ============================================================================
#   OIDC Authentication system configuration types
# ============================================================================

WELL_KNOWN_OPENID_CONFIGURATION = ".well-known/openid-configuration"


@dataclasses.dataclass
class OIDCAuthSystemConfig:
    id: str
    title: str

    server_url: str
    token_validation_pem: str
    client_id: str
    scope: str = None
    client_secret: str = ""  # "env:{JOSCE_CLIENT_SECRET}"
    oidc_client_pem_path: pathlib.Path = None

    # Set in 'from_yaml' below
    _installation_config: InstallationConfig = None
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path

        oidc_client_pem_path = config.pop("oidc_client_pem_path", None)
        if oidc_client_pem_path is not None:
            config["oidc_client_pem_path"] = (
                config_path.parent / oidc_client_pem_path
            )

        return cls(**config)

    @property
    def server_metadata_url(self):
        return f"{self.server_url}/{WELL_KNOWN_OPENID_CONFIGURATION}"

    @property
    def oauth_client_kwargs(self) -> dict:
        client_kwargs = {}

        if self.scope is not None:
            client_kwargs["scope"] = self.scope

        if self.oidc_client_pem_path is not None:
            client_kwargs["verify"] = str(self.oidc_client_pem_path)

        try:
            client_secret = self._installation_config.get_secret(
                self.client_secret
            )
        except Exception:
            client_secret = self.client_secret

        return {
            "name": self.id,
            "server_metadata_url": self.server_metadata_url,
            "client_id": self.client_id,
            "client_secret": client_secret,
            "client_kwargs": client_kwargs,
            # added by the auth setup
            # "authorize_state": main.SESSION_SECRET_KEY,
        }


@dataclasses.dataclass
class AvailableOIDCAuthSystemConfigs:
    systems: list[OIDCAuthSystemConfig] = dataclasses.field(
        default_factory=list,
    )


# ============================================================================
#   Tool configuration types
# ============================================================================


class ToolRequires(enum.StrEnum):
    FASTAPI_CONTEXT = "fastapi_context"
    TOOL_CONFIG = "tool_config"
    BARE = "bare"


@dataclasses.dataclass
class ToolConfig:
    tool_name: str

    allow_mcp: bool = False

    _tool: abc.Callable[..., typing.Any] = None

    # Set in 'from_yaml' below
    _installation_config: InstallationConfig = None
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path
        return cls(**config)

    @property
    def kind(self):
        _, kind = self.tool_name.rsplit(".", 1)
        return kind

    @property
    def tool_id(self):
        return self.kind

    @property
    def tool(self):
        if self._tool is None:
            module_name, tool_id = self.tool_name.rsplit(".", 1)
            module = importlib.import_module(module_name)
            self._tool = getattr(module, tool_id)

        return self._tool

    @property
    def tool_description(self) -> str:
        return inspect.getdoc(self.tool)

    @property
    def tool_requires(self) -> ToolRequires | None:
        tool_params = inspect.signature(self.tool).parameters

        if "ctx" in tool_params and "tool_config" in tool_params:
            raise ToolRequirementConflict(self.tool_name)

        if "ctx" in tool_params:
            return ToolRequires.FASTAPI_CONTEXT
        elif "tool_config" in tool_params:
            return ToolRequires.TOOL_CONFIG
        else:
            return ToolRequires.BARE

    @property
    def tool_with_config(self) -> abc.Callable[..., typing.Any]:
        if self.tool_requires == ToolRequires.TOOL_CONFIG:
            tool_func_sig = inspect.signature(self.tool)
            wo_tc_sig = tool_func_sig.replace(
                parameters=[
                    param
                    for param in tool_func_sig.parameters.values()
                    if param.name != "tool_config"
                ]
            )
            tool_w_config = functools.update_wrapper(
                functools.partial(self.tool, tool_config=self),
                self.tool,
            )
            tool_w_config.__signature__ = wo_tc_sig

            return tool_w_config
        else:
            return self.tool

    def get_extra_parameters(self) -> dict:
        return {}


@dataclasses.dataclass
class SearchDocumentsToolConfig(ToolConfig):
    kind: str = "search_documents"
    tool_name: str = "soliplex.tools.search_documents"

    # Set in '__post_init__' below
    _rag_lancedb_path: pathlib.Path = None

    # One of these two options must be specfied
    rag_lancedb_stem: str = None
    rag_lancedb_override_path: str = None

    expand_context_radius: int = 2
    search_documents_limit: int = 5
    return_citations: bool = False

    # Set in 'from_yaml' below
    _installation_config: InstallationConfig = None
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path
        try:
            instance = cls(**config)
        except RagDbExactlyOneOfStemOrOverride as exactly_one:
            raise FromYamlException(config_path) from exactly_one

        return instance

    def __post_init__(self):
        exclusive_required = [
            self.rag_lancedb_stem,
            self.rag_lancedb_override_path,
        ]
        passed = list(filter(None, exclusive_required))

        if len(list(passed)) != 1:
            raise RagDbExactlyOneOfStemOrOverride()

    @property
    def rag_lancedb_path(self) -> pathlib.Path:
        """Compute the path for the room's RAG rag_lancedb_path database"""
        if self.rag_lancedb_override_path is not None:
            rsop = self.rag_lancedb_override_path

            if self._config_path is not None:
                rsop = (self._config_path.parent / rsop).resolve()
            else:
                rsop = pathlib.Path(rsop).resolve()

            if not rsop.is_dir():
                raise RagDbFileNotFound(rsop)

            return rsop
        else:
            db_rag_dir = pathlib.Path(
                self._installation_config.get_environment(
                    "RAG_LANCE_DB_PATH",
                )
            )
            rspdb = (db_rag_dir / f"{self.rag_lancedb_stem}.lancedb").resolve()

            if not rspdb.is_dir():
                raise RagDbFileNotFound(rspdb)

            return rspdb

    def get_extra_parameters(self) -> dict:
        return {
            "expand_context_radius": self.expand_context_radius,
            "search_documents_limit": self.search_documents_limit,
            "return_citations": self.return_citations,
            "rag_lancedb_path": self.rag_lancedb_path,
        }


TOOL_CONFIG_CLASSES_BY_TOOL_NAME = {
    klass.tool_name: klass
    for klass in [
        SearchDocumentsToolConfig,
    ]
}


def extract_tool_configs(
    installation_config: InstallationConfig,
    config_path: pathlib.Path,
    config: dict,
):
    tool_configs = {}

    for t_config in config.pop("tools", ()):
        tool_name = t_config.get("tool_name")
        tc_class = TOOL_CONFIG_CLASSES_BY_TOOL_NAME.get(tool_name, ToolConfig)

        tool_config = tc_class.from_yaml(
            installation_config,
            config_path,
            t_config,
        )
        tool_configs[tool_config.kind] = tool_config

    return tool_configs


ToolConfigMap = dict[str, ToolConfig]


@dataclasses.dataclass
class Stdio_MCP_ClientToolsetConfig:
    """Configure an MCP client toolset which runs as a subprocess"""

    kind: typing.ClassVar[str] = "stdio"
    command: str
    args: list[str] = dataclasses.field(
        default_factory=list,
    )

    env: dict[str, str] = dataclasses.field(
        default_factory=dict,
    )
    allowed_tools: list[str] = None

    # set in 'from_yaml' class factory
    _installation_config: InstallationConfig = None
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path
        return cls(**config)

    @property
    def toolset_params(self) -> dict:
        return {
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def tool_kwargs(self) -> dict:
        env_map = {
            key: self._installation_config.get_environment(value, value)
            for (key, value) in self.env.items()
        }
        return {
            "command": self.command,
            "args": self.args,
            "env": env_map,
            "allowed_tools": self.allowed_tools,
        }


@dataclasses.dataclass
class HTTP_MCP_ClientToolsetConfig:
    """Configure an MCP client toolset which makes calls over streaming HTTP"""

    kind: typing.ClassVar[str] = "http"
    url: str
    headers: dict[str, typing.Any] = dataclasses.field(
        default_factory=dict,
    )

    query_params: dict[str, str] = dataclasses.field(
        default_factory=dict,
    )
    allowed_tools: list[str] = None

    # set in 'from_yaml' class factory
    _installation_config: InstallationConfig = None
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path
        return cls(**config)

    @property
    def toolset_params(self) -> dict:
        return {
            "url": self.url,
            "headers": self.headers,
            "query_params": self.query_params,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def tool_kwargs(self) -> dict:
        url = self.url

        headers = {
            key: self._installation_config.get_environment(value, value)
            for (key, value) in self.headers.items()
        }

        if self.query_params:
            qp = {
                key: self._installation_config.get_environment(value, value)
                for (key, value) in self.query_params.items()
            }
            qs = url_parse.urlencode(qp)
            url = f"{url}?{qs}"

        return {
            "url": url,
            "headers": headers,
            "allowed_tools": self.allowed_tools,
        }


MCP_CONFIG_CLASSES_BY_TYPE = {
    "stdio": Stdio_MCP_ClientToolsetConfig,
    "http": HTTP_MCP_ClientToolsetConfig,
}


def extract_mcp_client_toolset_configs(
    installation_config: InstallationConfig,
    config_path: pathlib.Path,
    config: dict,
):
    mcp_client_toolset_configs = {}

    for mcp_name, mcp_client_toolset_config in config.pop(
        "mcp_client_toolsets", {}
    ).items():
        type_ = mcp_client_toolset_config.pop("type")
        mcp_config_klass = MCP_CONFIG_CLASSES_BY_TYPE[type_]
        mcp_client_toolset_configs[mcp_name] = mcp_config_klass.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config=mcp_client_toolset_config,
        )

    return mcp_client_toolset_configs


MCP_ClientToolsetConfig = (
    Stdio_MCP_ClientToolsetConfig | HTTP_MCP_ClientToolsetConfig
)

MCP_ClientToolsetConfigMap = dict[str, MCP_ClientToolsetConfig]


# ============================================================================
#   Agent-related configuration types
# ============================================================================


class LLMProviderType(enum.StrEnum):
    OPENAI = "openai"
    OLLAMA = "ollama"


@dataclasses.dataclass
class AgentConfig:
    #
    # Agent-specific options
    #
    id: str  # set as 'room-{room_id}' or 'completion-{completion_id}'
    model_name: str = None

    system_prompt: dataclasses.InitVar[str] = None
    _system_prompt_text: str = None
    _system_prompt_path: pathlib.Path = None

    provider_type: LLMProviderType = LLMProviderType.OLLAMA
    provider_base_url: str = None  # installation config provides default
    provider_key: str = None  # 'secret containing API key

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = None
    _config_path: pathlib.Path = None

    def __post_init__(self, system_prompt):
        if self.model_name is None:
            if self._installation_config is not None:
                self.model_name = self._installation_config.get_environment(
                    "DEFAULT_AGENT_MODEL",
                )

        if system_prompt is not None:
            self._system_prompt_text = system_prompt

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict,
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path

        if "system_prompt" in config:
            system_prompt = config.pop("system_prompt")

            if system_prompt.startswith("./"):
                config["_system_prompt_path"] = system_prompt
            else:
                config["system_prompt"] = system_prompt

        return cls(**config)

    def get_system_prompt(self) -> str | None:
        if self._system_prompt_text is not None:
            return self._system_prompt_text

        if self._system_prompt_path is not None:
            if self._config_path is None:
                raise NoConfigPath()

            system_prompt_file = (
                self._config_path.parent / self._system_prompt_path
            )
            return system_prompt_file.read_text()

        else:  # pragma: NO COVER
            pass

    @property
    def llm_provider_kw(self) -> dict:
        if self.provider_base_url is None:
            provider_base_url = self._installation_config.get_environment(
                "OLLAMA_BASE_URL"
            )
        else:
            provider_base_url = self.provider_base_url

        provider_kw = {
            "base_url": f"{provider_base_url}/v1",
        }

        if self.provider_key is not None:
            provider_kw["api_key"] = self._installation_config.get_secret(
                self.provider_key
            )

        return provider_kw


# ============================================================================
#   Quiz-related configuration types
# ============================================================================


class QuizQuestionType(enum.StrEnum):
    QA = "qa"
    FILL_BLANK = "fill-blank"
    MULTIPLE_CHOICE = "multiple-choice"


@dataclasses.dataclass
class QuizQuestionMetadata:
    type: QuizQuestionType
    uuid: str
    options: list[str] = dataclasses.field(
        default_factory=list,
    )


@dataclasses.dataclass
class QuizQuestion:
    inputs: str
    expected_output: str
    metadata: QuizQuestionMetadata


@dataclasses.dataclass
class QuizConfig:
    id: str
    question_file: dataclasses.InitVar[str] = None
    _question_file_stem: str = None
    _question_file_path_override: str = None
    _questions_map: dict[str, QuizQuestion] = None

    title: str = "Quiz"
    randomize: bool = False
    max_questions: int = None

    judge_agent_model: str = "gpt-oss:20b"

    def __post_init__(self, question_file):
        if question_file is not None:
            if "/" in question_file:
                self._question_file_path_override = question_file
            else:
                if question_file.endswith(".json"):
                    question_file = question_file[: -len(".json")]

                self._question_file_stem = question_file
        if (
            self._question_file_stem is None
            and self._question_file_path_override is None
        ) or (
            self._question_file_stem is not None
            and self._question_file_path_override is not None
        ):
            raise QCExactlyOneOfStemOrOverride()

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = None
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict,
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path

        try:
            return cls(**config)
        except QCExactlyOneOfStemOrOverride as exc:
            raise FromYamlException(config_path) from exc

    @property
    def provider_base_url(self):
        return self._installation_config.get_environment("OLLAMA_BASE_URL")

    @property
    def question_file_path(self) -> pathlib.Path:
        if self._question_file_path_override is not None:
            return pathlib.Path(self._question_file_path_override)
        else:
            for quizzes_path in self._installation_config.quizzes_paths:
                qf_path = quizzes_path / f"{self._question_file_stem}.json"

                if qf_path.is_file():
                    return qf_path

    @staticmethod
    def _make_question(question: dict) -> QuizQuestion:
        metadata = QuizQuestionMetadata(
            uuid=question["metadata"]["uuid"],
            type=question["metadata"]["type"],
            options=question["metadata"].get("options", []),
        )
        return QuizQuestion(
            inputs=question["inputs"],
            expected_output=question["expected_output"],
            metadata=metadata,
        )

    def _load_questions_file(self) -> dict[str, QuizQuestion]:
        question_file = self.question_file_path

        if question_file is None:
            raise QuestionFileNotFoundWithStem(
                self._question_file_stem,
                self._installation_config.quizzes_paths,
            )

        if not question_file.is_file():
            raise QuestionFileNotFoundWithOverride(
                self._question_file_path_override,
            )

        quiz_json = json.loads(self.question_file_path.read_text())
        return {
            q_dict["metadata"]["uuid"]: self._make_question(q_dict)
            for q_dict in quiz_json["cases"]
        }

    def get_questions(self) -> list[QuizQuestion]:
        if self._questions_map is None:
            self._questions_map = self._load_questions_file()

        questions = list(self._questions_map.values())

        if self.randomize:
            random.shuffle(questions)

        if self.max_questions is not None:
            questions = questions[: self.max_questions]

        return questions

    def get_question(self, uuid: str) -> QuizQuestion:
        if self._questions_map is None:
            self._questions_map = self._load_questions_file()

        return self._questions_map[uuid]


# ============================================================================
#   Room-related configuration types
# ============================================================================


@dataclasses.dataclass
class RoomConfig:
    """Configuration for a chat room."""

    #
    # Required room metadata
    #
    id: str
    name: str
    description: str
    agent_config: AgentConfig

    #
    # Room UI options
    #
    _order: str = None  # defaults to 'id'
    welcome_message: str = None
    suggestions: list[str] = dataclasses.field(
        default_factory=list,
    )
    enable_attachments: bool = False

    #
    # Tool options
    #
    tool_configs: ToolConfigMap = dataclasses.field(default_factory=dict)
    mcp_client_toolset_configs: MCP_ClientToolsetConfigMap = dataclasses.field(
        default_factory=dict
    )

    #
    # MCP options
    #
    allow_mcp: bool = False

    #
    # Quiz-specific options
    #
    quizzes: list[QuizConfig] = dataclasses.field(
        default_factory=list,
    )
    _quiz_map: dict[str, QuizConfig] = None

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = None
    _config_path: pathlib.Path = None

    logo_image: dataclasses.InitVar[str] = None
    _logo_image: str = None

    def __post_init__(self, logo_image: str | None):
        if logo_image is not None:
            self._logo_image = logo_image

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict,
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path

        room_id = config["id"]
        agent_config_yaml = config.pop("agent")
        agent_config_yaml["id"] = f"room-{room_id}"

        config["agent_config"] = AgentConfig.from_yaml(
            installation_config,
            config_path,
            agent_config_yaml,
        )

        config["tool_configs"] = extract_tool_configs(
            installation_config,
            config_path,
            config,
        )

        config["mcp_client_toolset_configs"] = (
            extract_mcp_client_toolset_configs(
                installation_config,
                config_path,
                config,
            )
        )

        quizzes_config_yaml = config.pop("quizzes", None)
        if quizzes_config_yaml is not None:
            config["quizzes"] = [
                QuizConfig.from_yaml(
                    installation_config,
                    config_path,
                    quiz_config_yaml,
                )
                for quiz_config_yaml in quizzes_config_yaml
            ]

        logo_image = config.pop("logo_image", None)
        config["_logo_image"] = logo_image

        return cls(**config)

    @property
    def sort_key(self):
        if self._order is not None:
            return self._order

        return self.id

    @property
    def quiz_map(self) -> dict[str, QuizConfig]:
        if self._quiz_map is None:
            self._quiz_map = {quiz.id: quiz for quiz in self.quizzes}

        return self._quiz_map

    def get_logo_image(self) -> pathlib.Path | None:
        if self._logo_image is not None:
            if self._config_path is None:
                raise NoConfigPath()

            return self._config_path.parent / self._logo_image


# ============================================================================
#   Completions endpoint-related configuration types
# ============================================================================


@dataclasses.dataclass
class CompletionConfig:
    """Configuration for a completion endpoint."""

    #
    # Required metadata
    #
    id: str
    agent_config: AgentConfig

    name: str = None

    #
    # Tool options
    #
    tool_configs: dict[str, ToolConfig] = dataclasses.field(
        default_factory=dict,
    )
    mcp_client_toolset_configs: dict[
        str, Stdio_MCP_ClientToolsetConfig | HTTP_MCP_ClientToolsetConfig
    ] = dataclasses.field(default_factory=dict)

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = None
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict,
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path

        completion_id = config["id"]

        if "name" not in config:
            config["name"] = completion_id

        agent_config_yaml = config.pop("agent")
        agent_config_yaml["id"] = f"completion-{completion_id}"

        config["agent_config"] = AgentConfig.from_yaml(
            installation_config,
            config_path,
            agent_config_yaml,
        )

        config["tool_configs"] = extract_tool_configs(
            installation_config,
            config_path,
            config,
        )

        config["mcp_client_toolset_configs"] = (
            extract_mcp_client_toolset_configs(
                installation_config,
                config_path,
                config,
            )
        )

        return cls(**config)


# ============================================================================
#   Secrets configuration types
# ============================================================================


class _BaseSecretSource:
    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict):
        config["_config_path"] = config_path
        return cls(**config)


@dataclasses.dataclass
class EnvVarSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "env_var"
    secret_name: str
    env_var_name: str | None = None
    _config_path: pathlib.Path = None

    def __post_init__(self):
        if self.env_var_name is None:
            self.env_var_name = self.secret_name

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"env_var_name": self.env_var_name}


@dataclasses.dataclass
class FilePathSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "file_path"
    secret_name: str
    file_path: str
    _config_path: pathlib.Path = None

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"file_path": self.file_path}


@dataclasses.dataclass
class SubprocessSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "subprocess"
    secret_name: str
    command: str
    args: list[str] | tuple[str] = ()
    _config_path: pathlib.Path = None

    @property
    def command_line(self) -> str:
        listed = [self.command, *self.args]
        return " ".join(listed)

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"command_line": self.command_line}


@dataclasses.dataclass
class RandomCharsSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "random_chars"
    secret_name: str
    n_chars: int = 32
    _config_path: pathlib.Path = None

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"n_chars": self.n_chars}


SecretSource = (
    EnvVarSecretSource
    | FilePathSecretSource
    | SubprocessSecretSource
    | RandomCharsSecretSource
)


SecretSources = list[SecretSource]


SourceClassesByKind = {
    klass.kind: klass
    for klass in [
        EnvVarSecretSource,
        FilePathSecretSource,
        SubprocessSecretSource,
        RandomCharsSecretSource,
    ]
}


@dataclasses.dataclass
class SecretConfig:
    secret_name: str
    sources: SecretSources = None

    # Set in 'from_yaml' below
    _config_path: pathlib.Path = None
    _resolved: str = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = [EnvVarSecretSource(self.secret_name)]

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict | str):
        if isinstance(config, str):
            config = {
                "secret_name": config,
                "sources": [
                    {"kind": "env_var", "env_var_name": config},
                ],
            }

        config["_config_path"] = config_path
        source_configs = config.pop("sources", None)

        sources = []

        for source_config in source_configs:
            source_config["secret_name"] = config["secret_name"]
            source_kind = source_config.pop("kind")
            source_klass = SourceClassesByKind[source_kind]
            source_inst = source_klass.from_yaml(config_path, source_config)
            sources.append(source_inst)

        config["sources"] = sources

        return cls(**config)

    @property
    def resolved(self) -> str | None:
        return self._resolved


# ============================================================================
#   Installation configuration types
# ============================================================================


def _check_is_dict(config_yaml):
    if not isinstance(config_yaml, dict):
        raise NotADict(config_yaml)

    return config_yaml


def _load_config_yaml(config_path: pathlib.Path) -> dict:
    """Load a YAML config file"""
    if not config_path.is_file():
        raise NoSuchConfig(config_path)

    try:
        with config_path.open() as stream:
            config_yaml = _check_is_dict(
                yaml.load(stream, yaml.Loader),
            )

    except Exception as exc:
        raise FromYamlException(config_path) from exc

    return config_yaml


def _find_configs(
    to_search: pathlib.Path,
    filename_yaml: str,
) -> typing.Sequence[tuple[pathlib.Path, dict]]:
    """Yield a sequence of YAML configs found under 'to_search'

    Yielded values are tuples, '(config_path, config_yaml)', suitable for
    passing to a config class's 'from_yaml'.

    If 'to_search' has its own copy of 'filename_yaml', just yield the one
    config parsed from it.

    Otherwise, itterate over immediate subdirectories, yielding configs
    parsed from any which have copies of 'filename_yaml'
    """
    config_file = to_search / filename_yaml

    try:
        yield config_file, _load_config_yaml(config_file)

    except NoSuchConfig:
        for sub in sorted(to_search.glob("*")):
            if sub.is_dir():
                sub_config = sub / filename_yaml
                try:
                    yield sub_config, _load_config_yaml(sub_config)
                except NoSuchConfig:
                    continue
            else:  # pragma: NO COVER
                pass


_find_room_configs = functools.partial(
    _find_configs,
    filename_yaml="room_config.yaml",
)

_find_completion_configs = functools.partial(
    _find_configs,
    filename_yaml="completion_config.yaml",
)


def strip_secret_prefix(config_str: str) -> str:
    if not config_str.startswith(SECRET_PREFIX):
        raise NotASecret(config_str)

    return config_str[len(SECRET_PREFIX) :]


def resolve_file_prefix(env_value: str, config_path: pathlib.Path) -> str:
    if env_value.startswith(FILE_PREFIX):
        env_value = config_path.parent / env_value[len(FILE_PREFIX) :]

    return str(env_value)


@dataclasses.dataclass
class InstallationConfig:
    """Configuration for a set of rooms, completion, etc."""

    #
    # Required metadata
    #
    id: str

    #
    # Secrets name values looked up from env vars or other sources.
    #
    secrets: list[SecretConfig] = dataclasses.field(
        default_factory=list,
    )
    _secrets_map: dict[str, SecretConfig] = None

    @property
    def secrets_map(self) -> dict[str, SecretConfig]:
        if self._secrets_map is None:
            self._secrets_map = {
                secret_config.secret_name: secret_config
                for secret_config in self.secrets
            }

        return self._secrets_map

    def get_secret(self, secret_name) -> str:
        from soliplex import secrets as secrets_module  # avoid cycle

        secret_name = strip_secret_prefix(secret_name)
        secret_config = self.secrets_map[secret_name]
        return secrets_module.get_secret(secret_config)

    #
    # Map values similar to 'os.environ'.
    #
    environment: dict[str, str] = dataclasses.field(
        default_factory=dict,
    )

    def get_environment(self, key, default=None):
        """Find the configured value for a given quasi-envvar"""
        return self.environment.get(key, default)

    #
    # Path(s) to OIDC Authentication System configs
    #
    # Defaults to one path: './oidc' (set in '__post_init__')
    #
    oidc_paths: list[pathlib.Path | None] = None

    _oidc_auth_system_configs: list[OIDCAuthSystemConfig] = None

    #
    # Path(s) to room configs:  each item can be either a single
    # room config (a directory containing its own 'room_config.yaml' file),
    # or a directory containing such room configs.
    #
    # Defaults to one path: './rooms' (set in '__post_init__'), which is
    # normally a "container" directory for room config directories.
    #
    room_paths: list[pathlib.Path] = None

    _room_configs: dict[str, RoomConfig] = None

    #
    # Path(s) to completion configs:  each item can be either a single
    # completion config (a directory containing its own
    # 'completion_config.yaml' file), or a directory containing such
    # completion configs.
    #
    # Defaults to one path: './completion' (set in '__post_init__'), which is
    # normally a "container" directory for completion config directories.
    #
    completion_paths: list[pathlib.Path] = None

    _completion_configs: dict[str, CompletionConfig] = None

    #
    # Path(s) to quiz data:  each item must be a single directory containing
    # one or more '*.json' files, each holding question data for a single quiz.
    #
    # Defaults to one path: './quizzes' (set in '__post_init__').
    #
    quizzes_paths: list[pathlib.Path] = None

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict):
        config["_config_path"] = config_path

        environment = config.get("environment", {})

        secret_configs = [
            SecretConfig.from_yaml(config_path, secret_config)
            for secret_config in config.pop("secrets", ())
        ]
        config["secrets"] = secret_configs

        if isinstance(environment, list):
            config["environment"] = {
                item["name"]: resolve_file_prefix(item["value"], config_path)
                for item in environment
            }
        else:
            config["environment"] = {
                key: resolve_file_prefix(value, config_path)
                for key, value in environment.items()
            }

        dotenv_file = config_path.parent / ".env"

        if dotenv_file.is_file():
            with dotenv_file.open() as stream:
                dotenv_env = dotenv.dotenv_values(stream=stream)

            for key, value in dotenv_env.items():
                if key in config["environment"]:
                    config["environment"][key] = value

        return cls(**config)

    def __post_init__(self):
        if self.oidc_paths is None:
            self.oidc_paths = ["./oidc"]

        if self.room_paths is None:
            self.room_paths = ["./rooms"]

        if self.completion_paths is None:
            self.completion_paths = ["./completions"]

        if self.quizzes_paths is None:
            self.quizzes_paths = ["./quizzes"]

        if self._config_path is not None:
            parent_dir = self._config_path.parent

            self.oidc_paths = [
                parent_dir / oidc_path
                for oidc_path in self.oidc_paths
                if oidc_path is not None
            ]

            self.room_paths = [
                parent_dir / room_path
                for room_path in self.room_paths
                if room_path is not None
            ]

            self.completion_paths = [
                parent_dir / completion_path
                for completion_path in self.completion_paths
                if completion_path is not None
            ]

            self.quizzes_paths = [
                parent_dir / quizzes_path
                for quizzes_path in self.quizzes_paths
                if quizzes_path is not None
            ]

    def _load_oidc_auth_system_configs(self) -> list[OIDCAuthSystemConfig]:
        oas_configs = []

        for oidc_path in self.oidc_paths:
            oidc_config = oidc_path / "config.yaml"
            config_yaml = _load_config_yaml(oidc_config)

            oidc_client_pem_path = config_yaml.get("oidc_client_pem_path")
            if oidc_client_pem_path is not None:
                oidc_client_pem_path = oidc_path / oidc_client_pem_path

            for auth_system_yaml in config_yaml["auth_systems"]:
                if "oidc_client_pem_path" not in auth_system_yaml:
                    auth_system_yaml["oidc_client_pem_path"] = (
                        oidc_client_pem_path
                    )
                oas_config = OIDCAuthSystemConfig.from_yaml(
                    self,
                    oidc_config,
                    auth_system_yaml,
                )
                oas_configs.append(oas_config)

        return oas_configs

    @property
    def oidc_auth_system_configs(self) -> list[OIDCAuthSystemConfig]:
        if self._oidc_auth_system_configs is None:
            self._oidc_auth_system_configs = (
                self._load_oidc_auth_system_configs()
            )

        return self._oidc_auth_system_configs

    def _load_room_configs(self) -> dict[str, RoomConfig]:
        room_configs = {}

        for room_path in self.room_paths:
            for config_path, config_yaml in _find_room_configs(room_path):
                # XXX  order of 'room_paths' controls first-past-the-post
                #      for any conflict on room ID.
                config_id = config_yaml["id"]
                if config_id not in room_configs:
                    room_configs[config_id] = RoomConfig.from_yaml(
                        self,
                        config_path,
                        config_yaml,
                    )

        return room_configs

    @property
    def room_configs(self) -> dict[str, RoomConfig]:
        if self._room_configs is None:
            self._room_configs = self._load_room_configs()

        return self._room_configs.copy()

    def _load_completion_configs(self) -> dict[str, CompletionConfig]:
        completion_configs = {}

        for completion_path in self.completion_paths:
            for config_path, config_yaml in _find_completion_configs(
                completion_path
            ):
                # XXX  order of 'completion_paths' controls
                #      first-past-the-post for any conflict on completion ID.
                config_id = config_yaml["id"]
                if config_id not in completion_configs:
                    completion_configs[config_id] = CompletionConfig.from_yaml(
                        self,
                        config_path,
                        config_yaml,
                    )

        return completion_configs

    @property
    def completion_configs(self) -> dict[str, CompletionConfig]:
        if self._completion_configs is None:
            self._completion_configs = self._load_completion_configs()

        return self._completion_configs.copy()

    def reload_configurations(self):
        """Load all dependent configuration sets"""
        self._oidc_auth_system_configs = self._load_oidc_auth_system_configs()
        self._room_configs = self._load_room_configs()
        self._completion_configs = self._load_completion_configs()


def load_installation(config_path: pathlib.Path) -> InstallationConfig:
    config_path = config_path.resolve()

    if config_path.is_dir():
        config_path = config_path / "installation.yaml"

    config_yaml = _load_config_yaml(config_path)

    return InstallationConfig.from_yaml(config_path, config_yaml)
