import discord
from discord.ext import commands
from discord import app_commands

class BasicCommand(commands.Cog):
    
    def __init__(self, bot):
        self.__bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.__bot.latency * 1000)
        await interaction.response.send_message(f"{latency}ms")

async def setup(bot):
    await bot.add_cog(BasicCommand(bot))