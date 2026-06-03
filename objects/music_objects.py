import datetime
import asyncio
import os
import discord
import yt_dlp
from collections import deque

from tools.datetime_formatting import DatetimeFormatting as DF
from tools.youtube_url_check import Check
from pytube import Playlist
from youtubesearchpython import VideosSearch


class MusicDatabase():
    
    def __init__(self, url: str, info: dict):
        self.url = url
        self.id = info.get("id", None)
        self.display_id = info.get("display_id", self.id)
        self.title = info.get("title", None)
        self.duration = info.get("duration", None)
        
class GuildPlayer():
    
    def __init__(self, interaction):
        self.__bot = interaction.client
        self.__guild = interaction.guild
        self.__channel = interaction.channel
        
        self.queue = deque()
        #[filename, MusicDatabase]
        self._queue_lock = asyncio.Lock()
        self.history = deque()
        
        self.nowplaying_music = None #(str, MusicDatabase)
        self.nowplaying_start_time = None
        
        self.volume = 50
        
        self.__timeout_start_time = None
    
    async def addToQueue(self, music: MusicDatabase, pos = -1):
        async with self._queue_lock:
            video_display_id = music.display_id
            item = (os.path.join("music", str(self.__guild.id), f"{video_display_id}.mp3"), music)
            if pos == 0:
                self.queue.appendleft(item)  # O(1) — prepend
            else:
                self.queue.append(item)      # O(1) — append to end
        return f"`{music.title}` is added to queue"

    async def dlmusic_one(self, url: str) -> MusicDatabase:
        video_opt = {
            "outtmpl": os.path.join("music", str(self.__guild.id), "%(display_id)s.%(ext)s"),
            "format": 'bestaudio',
            "extract_audio": True,
            "quiet": True,
            "ignoreerrors": True,
            'noprogress': True,
            'no_warnings': True,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3'
                }
            ],
        }
        def func():
            with yt_dlp.YoutubeDL(video_opt) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return None
                if not os.path.isfile(os.path.join("music", str(self.__guild.id), f"{info['display_id']}.mp3")):
                    print(f"downloading {info['title']}")
                    ydl.download(url)
                music = MusicDatabase(url, info)
                return music
        music = await asyncio.to_thread(func)
        return music
    
    async def dlmusic_many(self, interaction, urls: list[str]) -> list[MusicDatabase]:
        """
            including add to queue
        """
        message = await interaction.channel.send(f"adding playlist")
            
        async def func(url):
            music = await self.dlmusic_one(url)
            await self.addToQueue(music)

        coros = [func(url) for url in urls]
        await asyncio.gather(*coros)
        print(f"finished adding {len(urls)} songs")
        await message.edit(content=f"finished adding")
    
    async def playerLoop(self, interaction):
        await self.__bot.wait_until_ready()
        while True:
            if self.nowplaying_music is not None:
                await asyncio.sleep(1)
                continue
            
            async with self._queue_lock:
                queue_empty = len(self.queue) == 0
                if not queue_empty:
                    filename, music = self.queue.popleft()  # O(1) vs O(n) for list.pop(0)
                else:
                    filename, music = None, None
            
            if queue_empty:
                if self.__timeout_start_time is None:
                    self.__timeout_start_time = datetime.datetime.now()
                else:
                    delta = (datetime.datetime.now() - self.__timeout_start_time).total_seconds()
                    if delta > 300:
                        voice_client = self.__bot.get_guild(self.__guild.id).voice_client
                        if voice_client is not None:
                            await voice_client.disconnect()
                            await interaction.channel.send("Timeout (idle over 5 mins)")
                        return
                await asyncio.sleep(1)
                continue
            
            # queue is not empty, filename and music are already set
            if os.path.isfile(filename) is False:
                await self.dlmusic_one(music.url)
            self.nowplaying_music = (filename, music)
            
            volume = self.volume / 100
            source = discord.FFmpegPCMAudio(
                filename,
                before_options=["-reconnect 1", "-reconnect_streamed 1", "-reconnect_delay_max 5"]
            )
            source = discord.PCMVolumeTransformer(source, volume=volume)
            
            def after(error):
                source.cleanup()
                self.__timeout_start_time = datetime.datetime.now()
                if error is not None:
                    coro = interaction.channel.send(str(error))
                    asyncio.run_coroutine_threadsafe(coro, self.__bot.loop)
                self.history.appendleft((filename, music))  # O(1) vs O(n) for list.insert(0, ...)
                self.nowplaying_music = None
            
            self.nowplaying_start_time = datetime.datetime.now()
            voice_client = self.__bot.get_guild(self.__guild.id).voice_client
            if voice_client:
                voice_client.play(source, after=after)
            
            msg = await self.nowplaying()
            await interaction.channel.send(msg)
    
    async def play(self, interaction: discord.Interaction, messages, sent_message: discord.Message):
        message = "".join(messages)
        if Check().is_watch_url(message):
            url = message
            music = await self.dlmusic_one(url)
            await sent_message.edit(content=await self.addToQueue(music))
        elif Check().is_playlist_url(message):
            urls = Playlist(message)
            print(urls)
            await sent_message.edit(content="Playlist function is not implemented yet")
        else: #not url
            url = self.__search(message)
            if url is None:
                await sent_message.edit(content="No result found")
                return
            music = await self.dlmusic_one(url)
            await sent_message.edit(content=await self.addToQueue(music))
        
        if self.nowplaying_music is None:
            await self.playerLoop(interaction)
    
    def __search(self, message: str) -> str:
        videosSearch = VideosSearch(message, limit = 1)
        try:
            url = videosSearch.result()['result'][0]['link']
        except IndexError:
            return None
        return url

    async def nowplaying(self):
        if self.nowplaying_music is None: return None
        
        music = self.nowplaying_music[1]
        start = self.nowplaying_start_time
        delta = datetime.datetime.now() - start
        duration = datetime.timedelta(seconds=music.duration)
        delta = DF().format_time(delta)
        duration = DF().format_time(duration)
        output = f"""
        Now playing:
    `{music.title}`
    {delta} / {duration}
        """
        return output
    
    async def repeat(self, interaction):
        _, music = self.nowplaying_music
        await self.addToQueue(music, 0)
        voice_client = self.__bot.get_guild(self.__guild.id).voice_client
        if voice_client:
            voice_client.stop()

    async def previous(self, interaction):
        async with self._queue_lock:
            if len(self.history) == 0:
                return
            self.queue.appendleft(self.nowplaying_music)          # O(1) vs O(n) for list.insert(0, ...)
            self.queue.appendleft(self.history.popleft())          # O(1) vs O(n) for list.pop(0)
        voice_client = self.__bot.get_guild(self.__guild.id).voice_client
        if voice_client:
            voice_client.stop()