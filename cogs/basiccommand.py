from enum import member

import discord
from discord.ext import commands
from discord import app_commands
import datetime


class HelpView(discord.ui.View):
    """View with a toggle button to switch between English and Chinese help."""

    def __init__(self, interaction: discord.Interaction, chinese: bool = False):
        super().__init__(timeout=180)
        self.__interaction = interaction
        self.__chinese = chinese
        # Update button label based on current language
        self.update_button()

    def update_button(self):
        if self.__chinese:
            self.toggle_button.label = "🌐 English"
        else:
            self.toggle_button.label = "🌐 中文"

    def _build_embed(self, interaction: discord.Interaction) -> discord.Embed:
        if self.__chinese:
            return self._chinese_embed(interaction)
        return self._english_embed(interaction)

    def _english_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = discord.Embed(
            title="MikuMusicBot - Command List",
            description="Here are all the available commands",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(
            name="🔧 General",
            value="`/ping` - Check the bot's latency\n`/help` - Show this command list",
            inline=False
        )
        embed.add_field(
            name="🎙️ Voice",
            value="`/join` - Join your voice channel\n`/leave` - Leave your voice channel",
            inline=False
        )
        embed.add_field(
            name="🎵 Playback",
            value="`/play <query>` - Play a song (URL or search)\n`/pause` - Pause the current song\n`/resume` - Resume the paused song\n`/stop` - Stop and clear the queue\n`/skip` - Skip to the next song\n`/repeat` - Repeat the current song\n`/previous` - Play the previous song",
            inline=False
        )
        embed.add_field(
            name="📋 Queue",
            value="`/queue` - Show the current queue\n`/remove <num>` - Remove a song from queue\n`/history` - Show playlist history\n`/nowplaying` - Show the now playing song",
            inline=False
        )
        embed.set_footer(
            text="MikuMusicBot",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        return embed

    def _chinese_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = discord.Embed(
            title="MikuMusicBot - 指令列表",
            description="以下是所有可用的指令",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(
            name="🔧 一般",
            value="`/ping` - 查看机器人延迟\n`/help` - 显示此指令列表",
            inline=False
        )
        embed.add_field(
            name="🎙️ 语音",
            value="`/join` - 加入你的语音频道\n`/leave` - 离开语音频道",
            inline=False
        )
        embed.add_field(
            name="🎵 播放",
            value="`/play <查询>` - 播放歌曲（URL 或搜索）\n`/pause` - 暂停当前歌曲\n`/resume` - 恢复暂停的歌曲\n`/stop` - 停止并清空播放队列\n`/skip` - 跳过当前歌曲\n`/repeat` - 重复当前歌曲\n`/previous` - 播放上一首歌曲",
            inline=False
        )
        embed.add_field(
            name="📋 队列",
            value="`/queue` - 显示当前队列\n`/remove <编号>` - 从队列中移除歌曲\n`/history` - 显示播放历史\n`/nowplaying` - 显示当前播放的歌曲",
            inline=False
        )
        embed.set_footer(
            text="MikuMusicBot",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        return embed

    @discord.ui.button(label="🌐 中文", style=discord.ButtonStyle.secondary)
    async def toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Toggle language
        self.__chinese = not self.__chinese
        self.update_button()
        # Rebuild embed with the new language and edit the message
        embed = self._build_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)


class BasicCommand(commands.Cog):

    def __init__(self, bot):
        self.__bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.__bot.latency * 1000)
        await interaction.response.send_message(f"{latency}ms")

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        view = HelpView(interaction, chinese=False)
        embed = view._english_embed(interaction)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(BasicCommand(bot))