import datetime
import json
import uuid

import fastapi
from fastapi import responses
from fastapi import security
from pydantic_ai import messages as ai_messages

from soliplex import auth
from soliplex import convos
from soliplex import installation
from soliplex import models
from soliplex import util

router = fastapi.APIRouter(tags=["conversations"])

depend_the_installation = installation.depend_the_installation

# =============================================================================
#   API endpoints for convos
# =============================================================================


@util.logfire_span("POST /v1/convos/new")
@router.post(
    "/v1/convos/new",
    summary="Post new conversation",
    deprecated=True,
)
async def post_convos_new(
    request: fastapi.Request,
    convo_msg: models.NewConvoClientMessage,
    the_installation: installation.Installation = depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.Conversation:
    """Create a new conversation

    Room ID supplied in the request body, along with the initial
    user message.
    """
    user = auth.authenticate(the_installation, token)
    user_profile = models.UserProfile(
        given_name=user.get("given_name", "<unknown>"),
        family_name=user.get("family_name", "<unknown>"),
        email=user.get("email", "<unknown>"),
        preferred_username=user.get("preferred_username", "<unknown>"),
    )
    user_name = user_profile.preferred_username

    try:
        agent = the_installation.get_agent_for_room(
            convo_msg.room_id,
            user=user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {convo_msg.room_id}",
        ) from None

    agent_deps = models.AgentDependencies(
        the_installation=the_installation,
        user=user_profile,
    )

    async with agent.run_stream(
        convo_msg.text,
        message_history=[],
        deps=agent_deps,
    ) as result:
        await result.get_output()
        new_messages = result.new_messages()

    context_messages = convos._filter_context_messages(new_messages)

    info = await the_convos.new_conversation(
        user_name,
        convo_msg.room_id,
        convo_msg.text,
        new_messages=context_messages,
    )
    return models.Conversation.from_convos_info(info)


@util.logfire_span("POST /v1/convos/new/{room_id}")
@router.post("/v1/convos/new/{room_id}", summary="Post new conversation")
async def post_convos_new_room(
    request: fastapi.Request,
    room_id: str,
    convo_msg: models.UserPromptClientMessage,
    the_installation: installation.Installation = depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.Conversation:
    """Create a new conversation

    Room ID supplied in the URL.
    """
    user = auth.authenticate(the_installation, token)
    user_profile = models.UserProfile(
        given_name=user.get("given_name", "<unknown>"),
        family_name=user.get("family_name", "<unknown>"),
        email=user.get("email", "<unknown>"),
        preferred_username=user.get("preferred_username", "<unknown>"),
    )
    user_name = user_profile.preferred_username

    try:
        agent = the_installation.get_agent_for_room(
            room_id,
            user=user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    agent_deps = models.AgentDependencies(
        the_installation=the_installation,
        user=user_profile,
    )

    async with agent.run_stream(
        convo_msg.text,
        message_history=[],
        deps=agent_deps,
    ) as result:
        await result.get_output()
        new_messages = result.new_messages()

    context_messages = convos._filter_context_messages(new_messages)

    info = await the_convos.new_conversation(
        user_name,
        room_id,
        convo_msg.text,
        new_messages=context_messages,
    )
    return models.Conversation.from_convos_info(info)


@util.logfire_span("GET /v1/convos")
@router.get("/v1/convos", summary="Get Conversations")
async def get_convos(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.ConversationMap:
    """Return the user's conversations"""
    user = auth.authenticate(the_installation, token)
    user_name = user.get("preferred_username", "<unknown>")
    user_convos = await the_convos.user_conversations(user_name)
    return {
        convo_uuid: models.Conversation.from_convos_info(info)
        for convo_uuid, info in user_convos.items()
    }


@util.logfire_span("GET /v1/convos/{convo_uuid}")
@router.get("/v1/convos/{convo_uuid}", summary="Get Conversation")
async def get_convo(
    request: fastapi.Request,
    convo_uuid: uuid.UUID,
    the_installation: installation.Installation = depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.Conversation:
    """Return the conversation specified by its UUID.

    Include the message history for the conversation, along with room ID, etc.
    """
    user = auth.authenticate(the_installation, token)
    user_name = user.get("preferred_username", "<unknown>")
    info = await the_convos.get_conversation_info(user_name, convo_uuid)
    return models.Conversation.from_convos_info(info)


@util.logfire_span("POST /v1/convos/{convo_uuid}")
@router.post("/v1/convos/{convo_uuid}", summary="Post to Conversation")
async def post_convo(
    request: fastapi.Request,
    convo_uuid: uuid.UUID,
    convo_msg: models.UserPromptClientMessage,
    the_installation: installation.Installation = depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> responses.StreamingResponse:
    """Send another user message to an existing conversation

    Return the final response message.
    """
    user = auth.authenticate(the_installation, token)

    user_profile = models.UserProfile(
        given_name=user.get("given_name", "<unknown>"),
        family_name=user.get("family_name", "<unknown>"),
        email=user.get("email", "<unknown>"),
        preferred_username=user.get("preferred_username", "<unknown>"),
    )
    user_name = user_profile.preferred_username

    convo = await the_convos.get_conversation(user_name, convo_uuid)

    try:
        agent = the_installation.get_agent_for_room(
            convo.room_id,
            user=user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {convo.room_id}",
        ) from None

    agent_deps = models.AgentDependencies(
        the_installation=the_installation,
        user=user_profile,
    )

    async def stream_messages(text: str, convo: convos.Conversation):
        """Streams new line delimited JSON `Message`s to the client."""
        # stream the user prompt so that can be displayed straight away
        timestamp = datetime.datetime.now(tz=datetime.UTC).isoformat()

        yield (
            json.dumps(
                {
                    "role": "user",
                    "timestamp": timestamp,
                    "content": text,
                }
            ).encode("utf-8")
            + b"\n"
        )

        async with agent.run_stream(
            text,
            message_history=convo.message_history,
            deps=agent_deps,
        ) as result:
            # output = await result.get_output()
            async for text in result.stream(debounce_by=0.01):
                # text here is a `str` and the frontend wants
                # JSON encoded ModelResponse, so we create one
                text_part = ai_messages.TextPart(text)
                mr = ai_messages.ModelResponse(
                    parts=[text_part], timestamp=result.timestamp()
                )
                yield (
                    json.dumps(
                        convos._to_convo_message(mr),
                    ).encode("utf-8")
                    + b"\n"
                )

            new_messages = result.new_messages()

        context_messages = convos._filter_context_messages(new_messages)

        await the_convos.append_to_conversation(
            user_name,
            convo_uuid,
            context_messages,
        )

    return responses.StreamingResponse(
        stream_messages(convo_msg.text, convo),
        media_type="text/plain",
    )


@util.logfire_span("DELETE /v1/convos/{convo_uuid}")
@router.delete(
    "/v1/convos/{convo_uuid}",
    status_code=204,
    summary="Delete Conversation",
)
async def delete_convo(
    request: fastapi.Request,
    convo_uuid: uuid.UUID,
    the_installation: installation.Installation = depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
):
    """Delete an existing conversation"""
    user = auth.authenticate(the_installation, token)
    user_name = user.get("preferred_username", "<unknown>")

    await the_convos.delete_conversation(user_name, convo_uuid)
