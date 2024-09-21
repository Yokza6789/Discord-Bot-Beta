import discord
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
from collections import deque
import re
from googleapiclient.discovery import build

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = discord.Client(intents=intents)

voice_clients = {}
playlists = {}


def sanitize_filename(title):
    return re.sub(r'[<>:"/\\|?*]', '', title)


def is_valid_url(url):
    return re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.?be)/.+$', url)


def download_vid(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'music/%(title)s.%(ext)s',
        'ffmpeg_location': r'C:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe',
        'quiet': False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            sanitized_title = sanitize_filename(info['title'])
            sanitized_file_path = f'music/{sanitized_title}.mp3'

            if os.path.exists(sanitized_file_path):
                return sanitized_file_path
            else:
                print("File download failed or file does not exist.")
                return None
        except Exception as e:
            print(f"Error downloading video: {e}")
            return None


async def play_next(guild_id):
    voice_client = voice_clients.get(guild_id)

    if guild_id in playlists and playlists[guild_id]:
        next_song = playlists[guild_id].popleft()
        file_path = download_vid(next_song)

        if file_path and os.path.exists(file_path):
            player = discord.FFmpegPCMAudio(file_path, executable=r'C:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe')
            voice_client.play(player,
                              after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), client.loop))
        else:
            print(f"File not found or download failed: {file_path}")
            await voice_client.disconnect()
    else:
        await voice_client.disconnect()


@client.event
async def on_ready():
    print(f'{client.user} is now jamming!')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!play"):
        if not message.author.voice:
            await message.channel.send("คุณต้องอยู่ในช่องเสียงเพื่อเล่นเพลง!")
            return

        song_url = message.content[len("!play "):].strip()

        if not is_valid_url(song_url):
            await message.channel.send("กรุณาใส่ URL ของเพลงที่ถูกต้อง!")
            return

        guild_id = message.guild.id

        if guild_id not in playlists:
            playlists[guild_id] = deque()

        playlists[guild_id].append(song_url)
        await message.channel.send(f"เพิ่มเพลงลงใน Playlist: {song_url}")

        # ใช้ .get() เพื่อป้องกันข้อผิดพลาด UnboundLocalError
        voice_client = voice_clients.get(guild_id)

        if guild_id not in voice_clients:
            voice_client = await message.author.voice.channel.connect()
            voice_clients[guild_id] = voice_client

        if not voice_client.is_playing():
            await play_next(guild_id)

    elif message.content.startswith("!stop"):
        voice_client = voice_clients.get(message.guild.id)
        if voice_client:
            await voice_client.disconnect()
            del voice_clients[message.guild.id]
            del playlists[message.guild.id]
            await message.channel.send("หยุดเพลงและออกจากช่องเสียง!")

    elif message.content.startswith("!skip"):
        voice_client = voice_clients.get(message.guild.id)
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await message.channel.send("ข้ามเพลงแล้ว!")
            await play_next(message.guild.id)
        else:
            await message.channel.send("ไม่มีเพลงที่กำลังเล่นอยู่!")


@client.event
async def on_voice_state_update(member, before, after):
    if before.channel is not None and len(before.channel.members) == 1:
        guild_id = member.guild.id
        voice_client = voice_clients.pop(guild_id, None)
        if voice_client:
            await voice_client.disconnect()
            del playlists[guild_id]


client.run(TOKEN)
