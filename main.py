from typing import Final
from friend import Friend
from bot_helper import send_command_all, send_command_list, send_command_single
import os
from dotenv import load_dotenv
import discord
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

# Create an instance of a bot (we'll register application/slash commands on the bot's tree)
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
is_playing = False  # Flag to track if a song is currently playing
downloaded_files = []  # List to track downloaded MP3 files
inactive_seconds = 0  # Counter for inactivity time
DOWNLOAD_DIR = "downloads"  # Directory to store downloaded MP3 files
        
@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user}')
    # Sync application (slash) commands to Discord
    try:
        await bot.tree.sync()
        logging.info("Command tree synced")
    except Exception as e:
        logging.error(f"Failed to sync command tree: {e}")
    inactivity_checker.start()

@bot.tree.command(name="p", description="Add a song to the queue and play it.")
async def p(interaction: discord.Interaction, url: str):
    """Add a song to the queue and play it (slash command).

    This command defers the interaction and uses followups for messages.
    """
    await interaction.response.defer()
    global queue, is_playing, voice_client

    # Ensure the user is in a voice channel
    if not interaction.user or not getattr(interaction.user, "voice", None):
        await interaction.followup.send("You must be in a voice channel for me to play music!")
        return

    # Connect to the user's voice channel if not connected
    if not voice_client or not voice_client.is_connected():
        channel = interaction.user.voice.channel
        voice_client = await channel.connect()

    # Add the song to the queue
    queue.append(url)

    # Start playback if not already playing
    if not is_playing:
        await play_next(interaction.channel)
    await interaction.followup.send(f"Queued: {url}")

@bot.tree.command(name="stop", description="Stop playback and clear the queue.")
async def s(interaction: discord.Interaction):
    """Stop playback and clear the queue (slash command)."""
    await interaction.response.defer()
    global voice_client, queue, is_playing, downloaded_files

    if voice_client and voice_client.is_playing():
        voice_client.stop()  # Stop playing audio
    else:
        await interaction.followup.send("The bot is not playing anything.")

    # Clear the queue, reset playback state, and delete downloaded files
    queue.clear()
    is_playing = False

    # Remove all downloaded MP3 files
    for file in downloaded_files:
        if os.path.exists(file):
            os.remove(file)
    downloaded_files.clear()
    await interaction.followup.send("Stopped and cleared queue.")

@bot.tree.command(name="skip", description="Skip the current song and move to the next.")
async def skip(interaction: discord.Interaction):
    """Skip the current song and move to the next (slash command)."""
    await interaction.response.defer()
    global voice_client

    if voice_client and voice_client.is_playing():
        voice_client.stop()  # Stop the current song
        await play_next(interaction.channel)  # Immediately move to the next song in the queue
        await interaction.followup.send("Skipped.")
    else:
        await interaction.followup.send("There is no song playing to skip.")

async def play_next(channel):
    """Play the next song in the queue. 'channel' should be a TextChannel-like object used for sending messages."""
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
        try:
            await channel.send(f"Failed to download audio: {url}")
        except Exception:
            logging.exception("Failed to notify channel about download failure")
        is_playing = False
        await play_next(channel)  # Skip to the next song
        return

    # Keep track of the downloaded file
    downloaded_files.append(mp3_file)

    # Play the MP3 file in the voice channel
    try:
        def after_playing(e):
            coro = play_next(channel)
            fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
            try:
                fut.result()
            except Exception as ex:
                logging.error(f"Error after playing audio: {ex}")

        voice_client.play(discord.FFmpegPCMAudio(mp3_file), after=after_playing)

    except Exception as e:
        logging.error(f"Error during playback: {e}")
        is_playing = False
        await play_next(channel)

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

@bot.tree.command(name="join", description="Have the bot join your voice channel.")
async def join(interaction: discord.Interaction):
    """Join the voice channel of the user who issued the command (slash command)."""
    await interaction.response.defer()
    global voice_client
    if interaction.user and getattr(interaction.user, "voice", None):
        channel = interaction.user.voice.channel
        if not voice_client or not voice_client.is_connected():
            voice_client = await channel.connect()
        await interaction.followup.send(f"Joined {channel}")
    else:
        await interaction.followup.send("You must be in a voice channel for me to join!")

@bot.tree.command(name="leave", description="Make the bot leave the voice channel.")
async def leave(interaction: discord.Interaction):
    """Leave the current voice channel (slash command)."""
    await interaction.response.defer()
    global voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        voice_client = None
        await interaction.followup.send("Left the voice channel.")
    else:
        await interaction.followup.send("I'm not in a voice channel.")

@bot.tree.command(name="goon", description="Join the gooning squad.")
async def goon(interaction: discord.Interaction):
    await interaction.response.defer()
    if interaction.user.id not in goon_users:
        goon_users.add(interaction.user.id)
        await interaction.followup.send(
            f"{interaction.user.mention} has joined the gooning squad! {len(goon_users)}/2"
        )

        if len(goon_users) == 2:
            await interaction.channel.send("It's gooning time!")
            results = send_command_all(ip, port)
            goon_users.clear()
            await interaction.channel.send(results)

@bot.tree.command(name="goon_target", description="Send goons after a target.")
async def goon_target(interaction: discord.Interaction, target: str):
    await interaction.response.defer()
    await interaction.followup.send(f"sending the goons after {target}")
    result = send_command_single(ip, port, target)
    await interaction.followup.send(result)


@bot.tree.command(name="goon_list", description="Ask server for goon targets list.")
async def goon_list(interaction: discord.Interaction):
    await interaction.response.defer()
    result = send_command_list(ip, port)
    await interaction.followup.send(result)

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


