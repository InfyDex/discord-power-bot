"""Interactive dropdown for /search: lets the user pick which result to queue."""
import discord


class _SearchSelect(discord.ui.Select):
    def __init__(self, tracks: list[dict], on_choose):
        self._tracks = tracks
        self._on_choose = on_choose
        options = [
            discord.SelectOption(
                label=t['title'][:100],
                description=f"{t['duration'] // 60}:{t['duration'] % 60:02d}",
                value=str(i),
            )
            for i, t in enumerate(tracks)
        ]
        super().__init__(placeholder="Pick a track to queue...", options=options)

    async def callback(self, interaction: discord.Interaction):
        track = self._tracks[int(self.values[0])]
        for child in self.view.children:
            child.disabled = True
        await interaction.message.edit(view=self.view)
        await self._on_choose(interaction, track)


class SearchView(discord.ui.View):
    def __init__(self, tracks: list[dict], on_choose, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.add_item(_SearchSelect(tracks, on_choose))
