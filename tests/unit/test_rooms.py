from unittest import mock

import fastapi
import pytest

from soliplex import config
from soliplex import installation
from soliplex import rooms

ROOM_IDS = ["foo", "bar", "baz"]


@pytest.fixture(scope="module", params=[(), ROOM_IDS])
def room_configs(request):
    return {
        room_id: mock.create_autospec(config.RoomConfig, sort_key=room_id)
        for room_id in request.param
    }


@pytest.mark.anyio
@mock.patch("soliplex.models.Room.from_config")
async def test_get_rooms(fc, room_configs):

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = room_configs

    found = await rooms.get_rooms(
        request, the_installation=the_installation,
    )

    for (found_key, found_room), room_id, fc_call in zip(
        found.items(),   # should already be sorted
        sorted(room_configs),
        fc.call_args_list,
        strict=True,
    ):
        assert found_key == room_id
        assert found_room is fc.return_value
        assert fc_call == mock.call(room_configs[room_id])


@pytest.mark.anyio
@mock.patch("soliplex.models.Room.from_config")
async def test_get_room(fc, room_configs):
    ROOM_ID = "foo"

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = room_configs

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms.get_room(
                request, ROOM_ID, the_installation=the_installation,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "No such room: foo"

    else:
        found = await rooms.get_room(
            request, ROOM_ID, the_installation=the_installation,
        )

        assert found is fc.return_value
        fc.assert_called_once_with(room_configs[ROOM_ID])
