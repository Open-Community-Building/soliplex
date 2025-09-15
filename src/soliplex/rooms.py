
import fastapi

from . import installation
from . import models

router = fastapi.APIRouter()


@router.get("/v1/rooms")
async def get_rooms(
    request: fastapi.Request,
    the_installation: installation.Installation =
        installation.depend_the_installation,
) -> models.ConfiguredRooms:
    # TODO: add authn check
    user = {"name": "test"}
    room_configs = the_installation.get_room_configs(user)

    def _key(item):
        key, value = item
        return value.sort_key

    rc_items = sorted(room_configs.items(), key=_key)

    return {
        room_id: models.Room.from_config(room)
        for room_id, room in rc_items
    }


@router.get("/v1/rooms/{room_id}")
async def get_room(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    #token: security.HTTPAuthorizationCredentials =
    #    auth_module.oauth2_predicate,
) -> models.Room:
    #user = auth_module.authenticate(request, token)
    user = {"name": "test"}
    room_configs = the_installation.get_room_configs(user)

    try:
        room_config = room_configs[room_id]
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such room: {room_id}",
        ) from None

    return models.Room.from_config(room_config)
