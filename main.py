from typing import Final
from friend import Friend
from bot_interface import send_command_all, send_command_list, send_command_single
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

# LOAD ENV VARIABLES
load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')
MQTT_PASSWORD: Final[str] = os.getenv('MQTT_PASSWORD')
SERVER_IP: Final[str] = os.getenv('SERVER_IP')

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

# retrieves a comma separated list of all connected signals. useful if youre wondering if it went off or not. why am i adding new features at this hour? i am sick. this is sickness. i do love sockets though.
def send_command_list(ip, port):
    try:
        client_socket = connect_to_server(ip, port)
        client_socket.sendall(b"indescribableemptiness")
        response = client_socket.recv(1024).decode()
        client_socket.close()
        if response == "":
            return "request failed"
        else:
            return response
    except Exception as e:
        return "request failed"


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

def main() -> None:
    connect_to_server(SERVER_IP, 42069)
    bot.run(token=TOKEN)
    print("Bot started")

