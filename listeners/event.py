import discord
from discord.ext import commands

class Event(commands.Cog):
    def __init__(self, bot):
        self.__bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.__bot.user:
            return
            
async def setup(bot):
    await bot.add_cog(Event(bot))