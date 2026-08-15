"""SearchView / dropdown tests."""
from unittest.mock import AsyncMock, MagicMock

import discord

from cogs.music_system.views import SearchView

from conftest import track_dict


def make_tracks(n=3, **overrides):
    return [track_dict(i, **overrides) for i in range(n)]


class TestOptionBuild:
    async def test_one_option_per_track(self):
        view = SearchView(make_tracks(5), on_choose=AsyncMock())
        select = view.children[0]
        assert len(select.options) == 5
        assert [o.value for o in select.options] == [str(i) for i in range(5)]

    async def test_title_truncated_to_100(self):
        tracks = [track_dict(1, title='y' * 150)]
        view = SearchView(tracks, on_choose=AsyncMock())
        assert len(view.children[0].options[0].label) == 100

    async def test_duration_formatting(self):
        tracks = [track_dict(1, duration=605)]  # 10:05
        view = SearchView(tracks, on_choose=AsyncMock())
        assert view.children[0].options[0].description == '10:05'


class TestCallback:
    async def test_callback_disables_and_forwards(self):
        tracks = make_tracks(3)
        on_choose = AsyncMock()
        view = SearchView(tracks, on_choose)
        select = view.children[0]

        interaction = MagicMock(spec=discord.Interaction)
        interaction.message.edit = AsyncMock()
        select._values = ['1']  # discord.py stores raw values here
        await select.callback(interaction)

        assert all(child.disabled for child in view.children)
        interaction.message.edit.assert_awaited_once()
        on_choose.assert_awaited_once()
        chosen = on_choose.call_args.args[1]
        assert chosen['id'] == tracks[1]['id']
