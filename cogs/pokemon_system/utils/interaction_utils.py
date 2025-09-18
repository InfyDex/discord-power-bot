"""Utility functions for handling both context and interaction objects."""

import discord
from discord.ext import commands
from typing import Union, Any

class UnifiedContext:
    """A wrapper that unifies discord.ext.commands.Context and discord.Interaction"""
    
    def __init__(self, ctx_or_interaction: Union[commands.Context, discord.Interaction]):
        self._original = ctx_or_interaction
        self._is_interaction = isinstance(ctx_or_interaction, discord.Interaction)
    
    @property
    def author(self):
        """Get the author/user who triggered the command"""
        return self._original.user if self._is_interaction else self._original.author
    
    @property
    def guild(self):
        """Get the guild where the command was used"""
        return self._original.guild
    
    @property
    def channel(self):
        """Get the channel where the command was used"""
        return self._original.channel
    
    async def send(self, content=None, **kwargs):
        """Send a message, handling both context and interaction"""
        if self._is_interaction:
            # For interactions, we need to respond or followup
            if not self._original.response.is_done():
                await self._original.response.send_message(content, **kwargs)
            else:
                await self._original.followup.send(content, **kwargs)
        else:
            # For regular commands, use ctx.send
            await self._original.send(content, **kwargs)

def create_unified_context(ctx_or_interaction):
    """Create a unified context from either a Context or Interaction"""
    return UnifiedContext(ctx_or_interaction)