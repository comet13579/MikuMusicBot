import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import os
from objects.music_objects import GuildPlayer, MusicDatabase
import json


class Music(commands.Cog):
    
    def __init__(self, bot):
        self.__bot = bot
        self.__players = {}
            
    def __userInVoiceChannel(self, interaction, msg = True) -> bool:
        voice = interaction.user.voice
        if voice is None:
            return False
        return True
    
    def __botInVoiceChannel(self, interaction, msg = True) -> bool:
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            return False
        return True
    
    async def __do_join(self, interaction: discord.Interaction):
        """Internal join logic, separate from command to allow programmatic calls."""
        if self.__userInVoiceChannel(interaction) is False: return
        await interaction.user.voice.channel.connect()

        if self.__players.get(interaction.guild.id, None) is None:
            self.__players[interaction.guild.id] = GuildPlayer(interaction)

    async def __do_leave(self, interaction: discord.Interaction):
        """Internal leave logic, separate from command to allow programmatic calls."""
        if self.__botInVoiceChannel(interaction) is False: return
        await interaction.guild.voice_client.disconnect()
        del self.__players[interaction.guild.id]

    @app_commands.command(name = "join", description = "Call the bot to join your voice channel")
    async def join(self, interaction: discord.Interaction):
        await self.__do_join(interaction)
        await interaction.response.send_message("Joined your voice channel")
    
    @app_commands.command(name = "leave", description = "Call the bot to leave your voice channel")
    async def leave(self, interaction: discord.Interaction):
        await self.__do_leave(interaction)
        await interaction.response.send_message("Left your voice channel")
    
    @app_commands.command(name = "play", description = "Play a song with the given url or search term")
    @app_commands.describe(query = "The url or search term of the song")
    async def play(self, interaction: discord.Interaction, query: str):
        message = ""
        if self.__userInVoiceChannel(interaction) is False: 
            await interaction.response.send_message("You need to be in a voice channel to use this command.")
            return
        if self.__botInVoiceChannel(interaction, False) is False:
            await self.__do_join(interaction)
            message += "Joined your voice channel\n"
        
        message += f"Searching for `{query}`..."
        await interaction.response.send_message(message)
        msg = await interaction.original_response()
        player: GuildPlayer = self.__players.get(interaction.guild.id, None)
        await player.play(interaction, query, msg)


    @app_commands.command(name = "repeat", description = "Repeat the current song")
    async def repeat(self, interaction: discord.Interaction):
        player: GuildPlayer = self.__players.get(interaction.guild.id, None)
        if player is None:
            return await interaction.response.send_message("not playing anything")
        if player.nowplaying is None:
            return await interaction.response.send_message("not playing anything")
        
        await player.repeat(interaction)
        return await interaction.response.send_message("repeated")

    @app_commands.command(name = "previous", description = "Play the previous song")
    async def previous(self, interaction: discord.Interaction):
        player: GuildPlayer = self.__players.get(interaction.guild.id, None)
        if player is None:
            return await interaction.response.send_message("not playing anything")
        if len(player.history) == 0:
            return await interaction.response.send_message("playing history is empty")
        await player.previous(interaction)
        return await interaction.response.send_message("playing previous")
    
    @app_commands.command(name = "pause", description = "pause the playing song")
    async def pause(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            return await interaction.response.send_message("not playing anything")
        if voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("paused")
        elif voice_client.is_paused():
            await interaction.response.send_message("it was already paused")
        else:
            await interaction.response.send_message("not playing anything")
    
    @app_commands.command(name = "resume", description = "resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            return await interaction.response.send_message("not playing anything")
        if voice_client.is_playing():
            await interaction.response.send_message("it is already playing")
        elif voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("resumed")
        else:
            await interaction.response.send_message("I ain't playing anything")
    
    @app_commands.command(name = "stop", description = "Stop the playing song")
    async def stop(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            return await interaction.response.send_message("not playing anything")
        voice_client.stop()
        player: GuildPlayer = self.__players.get(interaction.guild.id, None)
        player.queue.clear()
        await interaction.response.send_message("stopped, cleared queue")
    
    @app_commands.command(name = "skip", description = "Skip the playing song")
    async def skip(self, interaction: discord.Interaction):
        player: GuildPlayer = self.__players.get(interaction.guild.id, None)
        if player is None:
            return await interaction.response.send_message("not playing anything")
        if player.nowplaying_music is None:
            return await interaction.response.send_message("not playing anything")
        voice_client = interaction.guild.voice_client
        voice_client.stop()
        return await interaction.response.send_message("skipped")
    
    @app_commands.command(name = "queue", description = "Show the queue")
    async def queue(self, interaction: discord.Interaction):
        player: GuildPlayer = self.__players.get(interaction.guild.id, None)
        if player is None:
            return await interaction.response.send_message("the queue is empty")
        queue = player.queue
        if len(queue) == 0:
            nowplaying = await player.nowplaying()
            if nowplaying is None:
                return await interaction.response.send_message("the queue is empty")
            else:
                return await interaction.response.send_message(nowplaying + "\n" + "the queue is empty")
        
        output = "".join([f"    {i}: `{x[1].title}`\n" for i, x in enumerate(queue, start=1)])
        msg = await player.nowplaying() + "\n" + "Queue:" + "\n" + output
        
        await interaction.response.send_message(msg)
    
    @app_commands.command(name = "remove", description = "remove the song from the queue by using the queue number")
    @app_commands.describe(num = "The queue number")
    async def remove(self, interaction: discord.Interaction, num: str):
        player: GuildPlayer = self.__players.get(interaction.guild.id, None)
        if player is None:
            return await interaction.response.send_message("the queue is empty")
        queue = player.queue
        if num == "all":
            queue.clear()
            return await interaction.response.send_message("removed all")
        if num.isdigit():
            if int(num) in range(1, len(queue)+1):
                music = queue[int(num)-1][1]
                del queue[int(num)-1]  # deque doesn't support pop(index), use del instead
                return await interaction.response.send_message(f"removed `{music.title}`")
            else:
                return await interaction.response.send_message("invalid no.")
        else:
            return await interaction.response.send_message("invalid no.")
    
    @app_commands.command(name = "history", description = "show playlist history")
    async def history(self, interaction: discord.Interaction):
        player: GuildPlayer = self.__players.get(interaction.guild.id, None)
        if player is None:
            return await interaction.response.send_message("the playlist history is empty")
        history = player.history
        if len(history) == 0:
            nowplaying = await player.nowplaying()
            if nowplaying is None:
                return await interaction.response.send_message("the queue history is empty")
            return await interaction.response.send_message(nowplaying + "\n" + "the playlist history is empty")
        
        output = "".join([f"    -{i}: `{x[1].title}`\n" for i, x in enumerate(history, start=1)])
        np = await player.nowplaying()
        np = "" if np is None else np
        msg = np + "\n" + "History:" + "\n" + output
        
        await interaction.response.send_message(msg)
        
    @app_commands.command(name = "nowplaying", description = "show the nowplaying song")
    async def nowplaying(self, interaction: discord.Interaction):
        player: GuildPlayer = self.__players.get(interaction.guild.id, None)       
        if player is None:
            return await interaction.response.send_message("not playing anything")

        np = await player.nowplaying()
        if np is None:
            return await interaction.response.send_message("not playing anything")
        else:
            return await interaction.response.send_message(np)
        
    @app_commands.command(name = "volume", description = "show or set the volume")
    @app_commands.describe(percentage = "percentage volume (0-100)")
    async def volume(self, interaction: discord.Interaction, percentage: str = ""):
        player: GuildPlayer = self.__players.get(interaction.guild.id, None)
        if player is None:
            return await interaction.response.send_message("not playing anything")
        volume = player.volume
        if percentage == "":
            return await interaction.response.send_message(f"volume: `{volume}%`")
        else:
            new_volume = percentage
            if new_volume.isdigit():
                if int(new_volume) in range(101):
                    player.volume = int(new_volume)
                    interaction.guild.voice_client.source.volume = int(new_volume) / 100
                    return await interaction.response.send_message(f"volume has been changed from `{volume}%` to `{new_volume}%`")
                else:
                    return await interaction.response.send_message("volume has to be an integer between 0 and 100 inclusively")
            else:
                return await interaction.response.send_message("volume has to be an integer between 0 and 100 inclusively")

async def setup(bot):
    await bot.add_cog(Music(bot))