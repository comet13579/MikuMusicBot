from objects.postgresql import PostgreSQLManager
from discord.ext import commands, tasks
from discord import app_commands
import discord
import datetime


class AdminHelpView(discord.ui.View):
    """View with a toggle button to switch between English and Chinese admin help."""

    def __init__(self, interaction: discord.Interaction, chinese: bool = False):
        super().__init__(timeout=180)
        self.__interaction = interaction
        self.__chinese = chinese
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
            title="⚙️ Admin Command List",
            description="Admin-only commands",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(
            name="📊 Activity Monitor",
            value="`/enableactivity` - Enable activity monitor on this server\n`/inactivity <days>` - Generate inactivity report for this server\n`/adminhelp` - Show this admin command list",
            inline=False,
        )
        embed.set_footer(
            text="MikuMusicBot • Admin Only",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None,
        )
        return embed

    def _chinese_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = discord.Embed(
            title="⚙️ 管理員指令列表",
            description="管理員專用指令",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(
            name="📊 活動監控",
            value="`/enableactivity` - 在此伺服器啟用活動監控\n`/inactivity <天數>` - 生成此伺服器的不活躍報告\n`/adminhelp` - 顯示此管理員指令列表",
            inline=False,
        )
        embed.set_footer(
            text="MikuMusicBot • 僅管理員",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None,
        )
        return embed

    @discord.ui.button(label="🌐 中文", style=discord.ButtonStyle.secondary)
    async def toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.__chinese = not self.__chinese
        self.update_button()
        embed = self._build_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)

class ActivityMonitor(commands.Cog):
    def __init__(self, bot):
        self.__bot = bot

    async def cog_load(self):
        self.db = PostgreSQLManager()
        await self.db.connect()
        self.tables = set(await self.db.list_tables())

    async def cog_unload(self):
        await self.db.close()

    @commands.Cog.listener()
    async def on_thread_create(thread):
        if thread.joinable:
            await thread.join()

    @commands.Cog.listener()
    async def on_message(self, message):
        """Print message content, username, and whether the user is a server owner."""
        if message.author.bot or str(message.guild.id) not in self.tables:
            return
        await self.db.update_user_activity(
            str(message.guild.id),
            discord_user_id=message.author.id,
            activity_type="text",
            last_channel_id=message.channel.id,
            last_message_id=message.id
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Print voice state updates."""
        if member.bot or str(member.guild.id) not in self.tables:
            return
        channel_id = after.channel.id if after.channel else before.channel.id if before.channel else None
        if not channel_id:
            return
        await self.db.update_user_activity(
            str(member.guild.id),
            discord_user_id=member.id,
            activity_type="voice",
            last_channel_id=channel_id,
            last_message_id=None
        )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Print member join events."""
        if member.bot or str(member.guild.id) not in self.tables:
            return
        await self.db.insert_default_user_activity(str(member.guild.id), member.id)


    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Print member leave events."""
        if member.bot or str(member.guild.id) not in self.tables:
            return
        await self.db.remove_user_activity(str(member.guild.id), member.id)


    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="test", description="Test command (administrator only)")
    async def test(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have administrator permissions.", ephemeral=True)
            return
        await interaction.response.send_message("✅ Test command executed successfully!")

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="helpadmin", description="Show admin-only commands (Administrator only)")
    async def admin_help(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have administrator permissions.", ephemeral=True)
            return
        view = AdminHelpView(interaction, chinese=False)
        embed = view._english_embed(interaction)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="enableactivity", description="Enable activity monitor on this server (Administrator only)")
    async def enable_activity(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have administrator permissions.", ephemeral=True)
            return
        if str(interaction.guild.id) in self.tables:
            await interaction.response.send_message("Activity monitor is already enabled for this server.", ephemeral=True)
            return
        await self.db.insert_timeline_entry(interaction.guild.id)
        await self.db.create_user_activity_table(str(interaction.guild.id))
        self.tables.add(str(interaction.guild.id))
        for member in interaction.guild.members:
            if not member.bot:
                await self.db.insert_default_user_activity(str(interaction.guild.id), member.id)
        await interaction.response.send_message("✅ Activity monitor enabled for this server!")

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="inactivity", description="Generate inactivity report for this server (Administrator only)")
    @app_commands.describe(days="Number of days to consider for inactivity")
    async def inactivity_report(self, interaction: discord.Interaction, days: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have administrator permissions.", ephemeral=True)
            return
        if str(interaction.guild.id) not in self.tables:
            await interaction.response.send_message("Activity monitor is not enabled for this server. Use /enableactivity to enable it.", ephemeral=True)
            return
        report = await self.db.get_inactive_users(str(interaction.guild.id), days)
        activateTime = await self.db.get_timeline_time(interaction.guild.id)
        days_since_activation = (discord.utils.utcnow() - activateTime).days if activateTime else "unknown"
        if not report:
            await interaction.response.send_message(f"No inactivity data found for the past {days} days.\nNote: This function is activated since {days_since_activation} days ago, so anything before that is not included.")
            return
        report_lines = [f"**Inactivity Report for {interaction.guild.name} (Last {days} Days)**\n",f"Note: This function is activated since {days_since_activation} days ago, so anything before that is not included.\n"]
        for entry in report:
            user_id, last_active_at = entry
            user = interaction.guild.get_member(user_id)
            username = user.name if user else f"User ID {user_id}"
            last_active_str = last_active_at.strftime("%Y-%m-%d %H:%M:%S") if last_active_at else "Never"
            report_lines.append(f"- **{username}**: Last Active: {last_active_str}")
        report_content = "\n".join(report_lines)
        await interaction.response.send_message(report_content)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="userlatest", description="Get the latest activity of a user (Administrator only)")
    @app_commands.describe(user="The user to check")
    async def user_latest(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have administrator permissions.", ephemeral=True)
            return
        if str(interaction.guild.id) not in self.tables:
            await interaction.response.send_message("Activity monitor is not enabled for this server. Use /enableactivity to enable it.", ephemeral=True)
            return
        activity = await self.db.get_user_activity(str(interaction.guild.id), user.id)
        if not activity:
            await interaction.response.send_message(f"No activity data found for {user.name}.")
            return
        print(activity)
        activity_type, last_channel_id, last_message_id, last_active_at = activity
        last_active_str = last_active_at.strftime("%Y-%m-%d %H:%M:%S") if last_active_at else "Never"
        channel_mention = f"<#{last_channel_id}>" if last_channel_id else "N/A"
        message_link = f"https://discord.com/channels/{interaction.guild.id}/{last_channel_id}/{last_message_id}" if last_message_id and last_channel_id else "N/A"
        response = (
            f"**Latest Activity for {user.name}**\n"
            f"- Activity Type: {activity_type}\n"
            f"- Last Active At: {last_active_str}\n"
            f"- Last Channel: {channel_mention}\n"
            f"- Last Message: {message_link}"
        )
        await interaction.response.send_message(response)

async def setup(bot):
    await bot.add_cog(ActivityMonitor(bot))