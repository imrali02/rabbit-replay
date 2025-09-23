from typing import Final
from friend import Friend
from bot_helper import send_command_all, send_command_list, send_command_single
import os
from dotenv import load_dotenv
from discord import Intents, VoiceClient
from discord.ext import commands, tasks
import yt_dlp as youtube_dl
import threading
import time
import socket
import select
import asyncio
import logging
import subprocess
import hashlib

# LOAD ENV VARIABLES
load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')
MQTT_PASSWORD: Final[str] = os.getenv('MQTT_PASSWORD')
SERVER_IP: Final[str] = os.getenv('SERVER_IP')
ip = SERVER_IP
port = 42069

# BOT SETUP
intents: Intents = Intents.default()
intents.message_content = True

# Create an instance of a bot with the new command prefix '!'
bot = commands.Bot(command_prefix="!", intents=intents)

# USER DICTIONARY
user_dict = {
    323527384588353557: "scrounch",
    518899324177088513: "goontern",
    262065524890927105: "stinkfish",
    299329028421189632: "frozenravager",
    262409000929198080: "goonerobama"
}

# Global variables
voice_client: VoiceClient = None
last_activity_time = None
goon_users = set()
is_gooning = False
queue = []  # Queue to store song URLs
        
@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user}')
    inactivity_checker.start()

@bot.command()
async def p(ctx, url: str):
    """Add a song to the queue and play it."""
    global queue, is_playing

    # Ensure the bot is in a voice channel
    if not ctx.author.voice:
        await ctx.send("You must be in a voice channel for me to play music!")
        return
    if not voice_client or not voice_client.is_connected():
        await join(ctx)

    # Add the song to the queue
    queue.append(url)

    # Start playback if not already playing
    if not is_playing:
        await play_next(ctx)

@bot.command()
async def s(ctx):
    """Stop playback and clear the queue."""
    global voice_client, queue, is_playing, downloaded_files

    if voice_client and voice_client.is_playing():
        voice_client.stop()  # Stop playing audio
    else:
        await ctx.send("The bot is not playing anything.")

    # Clear the queue, reset playback state, and delete downloaded files
    queue.clear()
    is_playing = False

    # Remove all downloaded MP3 files
    for file in downloaded_files:
        if os.path.exists(file):
            os.remove(file)
    downloaded_files.clear()

@bot.command()
async def skip(ctx):
    """Skip the current song and move to the next."""
    global voice_client

    if voice_client and voice_client.is_playing():
        voice_client.stop()  # Stop the current song
        await play_next(ctx)  # Immediately move to the next song in the queue
    else:
        await ctx.send("There is no song playing to skip.")

async def play_next(ctx):
    """Play the next song in the queue."""
    global queue, is_playing, voice_client, downloaded_files

    if not queue:
        is_playing = False
        return

    is_playing = True

    # Get the next URL from the queue
    url = queue.pop(0)

    # Download the MP3 file
    mp3_file = await download_mp3(url)
    if not mp3_file:
        await ctx.send(f"Failed to download audio: {url}")
        is_playing = False
        await play_next(ctx)  # Skip to the next song
        return

    # Keep track of the downloaded file
    downloaded_files.append(mp3_file)

    # Play the MP3 file in the voice channel
    try:
        def after_playing(e):
            coro = play_next(ctx)
            fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
            try:
                fut.result()
            except Exception as ex:
                logging.error(f"Error after playing audio: {ex}")

        voice_client.play(discord.FFmpegPCMAudio(mp3_file), after=after_playing)

    except Exception as e:
        logging.error(f"Error during playback: {e}")
        is_playing = False
        await play_next(ctx)

async def download_mp3(url: str):
    """Download the MP3 from the provided YouTube URL using yt-dlp CLI."""
    try:
        # Generate a unique file name for the MP3 based on the URL
        file_hash = hashlib.md5(url.encode()).hexdigest()
        mp3_file = os.path.join(DOWNLOAD_DIR, f'{file_hash}.mp3')

        # Ensure the cookies file exists
        cookies_file = 'cookies.txt'
        if not os.path.exists(cookies_file):
            logging.error("Cookies file 'cookies.txt' is missing!")
            return None

        # Run yt-dlp via subprocess to download the audio as MP3
        command = [
            'yt-dlp',
            '--format', 'bestaudio/best',  # Download the best audio format
            '--extract-audio',  # Extract audio only (no video)
            '--audio-format', 'mp3',
            '--output', mp3_file,  # Output file path
            '--cookies', cookies_file  # Use cookies file
        ]

        # Execute the command
        subprocess.run(command + [url], check=True)

        return mp3_file
    except subprocess.CalledProcessError as e:
        logging.error(f"Error downloading audio: {e}")
        return None

@bot.command()
async def join(ctx):
    """Join the voice channel of the user who issued the command."""
    global voice_client
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if not voice_client or not voice_client.is_connected():
            voice_client = await channel.connect()
    else:
        await ctx.send("You must be in a voice channel for me to join!")

@bot.command()
async def leave(ctx):
    """Leave the current voice channel."""
    global voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        voice_client = None

@bot.command()
async def goon(ctx):
    if ctx.author.id not in goon_users:
        goon_users.add(ctx.author.id)
        await ctx.channel.send(
            f"{ctx.author.mention} has joined the gooning squad! {len(goon_users)}/2"
        )

        if len(goon_users) == 2:
            await ctx.channel.send("It's gooning time!")
            results = send_command_all(ip, port)
            goon_users.clear()
            await ctx.channel.send(results)

@bot.command()
async def goon_target(ctx, target: str):
    await ctx.send(f"sending the goons after {target}")
    result = send_command_single(ip, port, target)
    await ctx.send(result)


@bot.command()
async def goon_list(ctx):
    result = send_command_list(ip, port)
    await ctx.send(result)

@tasks.loop(seconds=10)
async def inactivity_checker():
    """Check for inactivity and disconnect if inactive for 5 minutes."""
    global inactive_seconds, voice_client, is_playing

    if voice_client and not is_playing and not queue:
        inactive_seconds += 10
        if inactive_seconds >= 300:  # 5 minutes
            await voice_client.disconnect()
            voice_client = None
            inactive_seconds = 0
            logging.info("Disconnected due to inactivity.")
    else:
        inactive_seconds = 0  # Reset inactivity timer if playing or queue is not empty

# needed for the fns, irrelevant to you
def connect_to_server(ip, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((ip, port))
        print(f"Connected to server at {ip}:{port}")
        return client_socket
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

if __name__ == "__main__":
    connect_to_server(ip, port)
    bot.run(token=TOKEN)
    print("Bot started")


