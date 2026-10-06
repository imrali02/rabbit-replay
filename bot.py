#!/usr/bin/env python3
import os
import re
import html
import logging
import asyncio

import aiohttp
import discord
import yt_dlp
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
if not token:
    raise ValueError("DISCORD_TOKEN environment variable is not set!")


class MusicBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Register slash commands with Discord
        synced = await self.tree.sync()
        logging.info(f"Synced {len(synced)} slash commands.")


bot = MusicBot()

# Global (single-guild) playback state
voice_client: discord.VoiceClient = None
queue = []  # list of resolved track dicts: {"title": str, "url": str}
is_playing = False
inactive_seconds = 0

YOUTUBE_URL_RE = re.compile(r"(?:youtube\.com|youtu\.be)", re.IGNORECASE)
SPOTIFY_URL_RE = re.compile(r"open\.spotify\.com/(?:intl-\w+/)?(track|album|playlist)/([A-Za-z0-9]+)", re.IGNORECASE)
SPOTIFY_URI_RE = re.compile(r"spotify:(track|album|playlist):([A-Za-z0-9]+)", re.IGNORECASE)

YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "socket_timeout": 10,
    # YouTube extraction needs a JS runtime; yt-dlp only enables deno by default
    "js_runtimes": {"node": {}},
}
if os.path.exists("cookies.txt"):
    YDL_OPTS["cookiefile"] = "cookies.txt"

FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"


async def spotify_track_to_query(track_id: str) -> str:
    """Resolve a Spotify track id to a 'artist title' search string using Spotify's
    public track page metadata. No API credentials required."""
    url = f"https://open.spotify.com/track/{track_id}"
    async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                raise ValueError(f"Spotify returned status {resp.status} for that track.")
            page = await resp.text()

    title_match = re.search(r'<meta property="og:title" content="([^"]*)"', page)
    desc_match = re.search(r'<meta property="og:description" content="([^"]*)"', page)

    if not title_match:
        raise ValueError("Couldn't read metadata for that Spotify track.")

    title = html.unescape(title_match.group(1))
    artist = None
    if desc_match:
        desc = html.unescape(desc_match.group(1))
        artist = desc.split(" · ")[0]

    return f"{artist} {title}" if artist else title


def _extract(query: str) -> dict:
    """Blocking yt-dlp extraction, run off the event loop via run_in_executor."""
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(query, download=False)
        if info is None:
            raise ValueError("No results found.")
        if "entries" in info:
            entries = [e for e in info["entries"] if e]
            if not entries:
                raise ValueError("No results found.")
            info = entries[0]
        return info


async def resolve_track(query: str) -> dict:
    """Turn a YouTube URL, Spotify track URL/URI, or plain keywords into a
    playable {"title", "url"} dict."""
    spotify_match = SPOTIFY_URL_RE.search(query) or SPOTIFY_URI_RE.search(query)
    if spotify_match:
        kind, track_id = spotify_match.group(1), spotify_match.group(2)
        if kind != "track":
            raise ValueError("Only Spotify track links are supported right now (not albums/playlists).")
        search_terms = await spotify_track_to_query(track_id)
        ydl_query = f"ytsearch1:{search_terms}"
    elif YOUTUBE_URL_RE.search(query):
        ydl_query = query
    else:
        ydl_query = f"ytsearch1:{query}"

    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(None, _extract, ydl_query)
    return {"title": info.get("title") or query, "url": info["url"]}


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user}")
    if not inactivity_checker.is_running():
        inactivity_checker.start()


async def connect_to_author(interaction: discord.Interaction) -> bool:
    """Connect to the invoking user's voice channel if not already connected."""
    global voice_client
    if not interaction.user.voice:
        return False
    if not voice_client or not voice_client.is_connected():
        voice_client = await interaction.user.voice.channel.connect()
    return True


@bot.tree.command()
@app_commands.guild_only()
async def join(interaction: discord.Interaction):
    """Join your voice channel."""
    await interaction.response.defer()
    if await connect_to_author(interaction):
        await interaction.followup.send(f"Joined {voice_client.channel.mention}.")
    else:
        await interaction.followup.send("You must be in a voice channel for me to join!")


@bot.tree.command()
@app_commands.guild_only()
async def leave(interaction: discord.Interaction):
    """Leave the voice channel and clear the queue."""
    global voice_client, queue, is_playing
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await interaction.response.send_message("Left the voice channel.")
    else:
        await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)
    voice_client = None
    queue.clear()
    is_playing = False


@bot.tree.command()
@app_commands.guild_only()
@app_commands.describe(query="YouTube URL, Spotify track URL, or search keywords")
async def play(interaction: discord.Interaction, query: str):
    """Queue and play a YouTube URL, a Spotify track URL, or search keywords."""
    global queue, is_playing

    if not interaction.user.voice:
        await interaction.response.send_message(
            "You must be in a voice channel for me to play music!", ephemeral=True
        )
        return

    # Resolving can take longer than Discord's 3s reply window
    await interaction.response.defer(thinking=True)

    await connect_to_author(interaction)

    try:
        track = await resolve_track(query)
    except Exception as e:
        logging.error(f"Failed to resolve '{query}': {e}")
        await interaction.followup.send(f"Couldn't find that: {e}")
        return

    queue.append(track)
    await interaction.followup.send(f"Queued: {track['title']}")

    if not is_playing:
        await play_next(interaction.channel)


@bot.tree.command()
@app_commands.guild_only()
async def stop(interaction: discord.Interaction):
    """Stop playback and clear the queue."""
    global queue, is_playing

    # Clear the queue first so the after_playing callback has nothing to advance to
    queue.clear()
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("Stopped and cleared the queue.")
    else:
        await interaction.response.send_message("The bot is not playing anything.", ephemeral=True)

    is_playing = False


@bot.tree.command()
@app_commands.guild_only()
async def skip(interaction: discord.Interaction):
    """Skip the current song and move to the next."""
    if voice_client and voice_client.is_playing():
        voice_client.stop()  # after_playing callback advances the queue
        await interaction.response.send_message("Skipped.")
    else:
        await interaction.response.send_message("There is no song playing to skip.", ephemeral=True)


async def play_next(channel: discord.abc.Messageable):
    """Play the next song in the queue."""
    global queue, is_playing, voice_client

    if not queue:
        is_playing = False
        return

    is_playing = True
    track = queue.pop(0)

    def after_playing(error):
        if error:
            logging.error(f"Playback error: {error}")
        coro = play_next(channel)
        fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
        try:
            fut.result()
        except Exception as ex:
            logging.error(f"Error after playing audio: {ex}")

    try:
        source = discord.FFmpegPCMAudio(
            track["url"], before_options=FFMPEG_BEFORE_OPTIONS, options=FFMPEG_OPTIONS
        )
        voice_client.play(source, after=after_playing)
        await channel.send(f"Now playing: {track['title']}")
    except Exception as e:
        logging.error(f"Error starting playback of '{track['title']}': {e}")
        await channel.send(f"Failed to play: {track['title']}")
        await play_next(channel)


@tasks.loop(seconds=10)
async def inactivity_checker():
    """Disconnect if inactive (not playing, empty queue) for 5 minutes."""
    global inactive_seconds, voice_client, is_playing

    if voice_client and not is_playing and not queue:
        inactive_seconds += 10
        if inactive_seconds >= 300:
            await voice_client.disconnect()
            voice_client = None
            inactive_seconds = 0
            logging.info("Disconnected due to inactivity.")
    else:
        inactive_seconds = 0


bot.run(token)
