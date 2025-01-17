from typing import Final
from friend import Friend
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

# BOT SETUP
intents: Intents = Intents.default()
intents.message_content = True

# Create an instance of a bot with the new command prefix '!'
bot = commands.Bot(command_prefix="!", intents=intents)

cookies_file = open("cookies-youtube-com.txt", "r")

# YTDL OPTIONS
ytdl_format_options = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    "extractor-args": "youtube:player-client=web,default;po_token=" + os.getenv('PO_TOKEN'),
    "cookies": cookies_file.read(),
}

# USER DICTIONARY
user_dict = {
    323527384588353557: "scrounch",
    518899324177088513: "goontern",
    262065524890927105: "stinkfish",
    299329028421189632: "frozenravager",
    262409000929198080: "goonerobama"
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# Global variables
voice_client: VoiceClient = None
last_activity_time = None
goon_users = set()
is_gooning = False
queue = []  # Queue to store song URLs

# MAIN ENTRY POINT
def main() -> None:
    bot.run(token=TOKEN)
            
def trigger_buzzer(name):
    for friend in client_list:
        if friend.name == name:
            friend.send_message("trigger alarm")

def trigger_buzzers_for_all_devices():
    global client_list
    for friend in client_list:
        friend.send_message("trigger alarm")

    # principally violates DRY but O(n) instead of O(n^2) my beloved           

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
    if len(ctx.content.split()) == 1:
        if ctx.author.id not in goon_users:
                goon_users.add(ctx.author.id)
                await ctx.channel.send(
                    f"{ctx.author.mention} has joined the gooning squad! {len(goon_users)}/2"
                )

                if len(goon_users) == 2:
                    await ctx.channel.send("It's gooning time!")
                    trigger_buzzers_for_all_devices()
                    goon_users.clear()
    else:
        trigger_buzzer(ctx.content.split(" ", 1)[1])

def start_server(ip, port):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setblocking(False)
    server_sock.bind((ip, port))
    server_sock.listen()
    print(f"Server started at {ip}:{port}")
    return server_sock

def handshake(client_socket):
    try:
        client_socket.settimeout(5)
        data = client_socket.recv(1024).decode()
        client_socket.sendall(b"hello")
        print("Handshake successful!")
        return True, Friend(data, client_socket)
    except socket.timeout:
        print("Handshake timeout.")
    except Exception as e:
        print(f"Error during handshake: {e}")
    return False, None

async def manage_clients(server_sock, client_list):
    while True:
        ready_to_read, _, _ = select.select([server_sock], [], [], 0)
        if ready_to_read:
            try:
                client_socket, client_address = server_sock.accept()
                print(f"New connection from {client_address}")

                success, to_add = handshake(client_socket)

                if success:
                    client_list.append(to_add)
                else:
                    client_socket.close()
            except Exception as e:
                print(f"Error accepting connection: {e}")

        await asyncio.sleep(2)
        print_client_list()
        # prints all connected clients, not important if you can't/don't want to see terminal output

async def prune_client_list(client_list):
    while True:

        tasks = [friend.keep_alive(client_list) for friend in client_list]
        await asyncio.gather(*tasks)

        await asyncio.sleep(5)

def print_client_list():
    global client_list
    # os.system("clear")
    print("current friend list\n")
    for friend in client_list:
        print(friend)
    print("\n\n\n\n\n")

async def run_server(ip, port):
    global client_list
    server_sock = start_server(ip, port)

    manage_task = asyncio.create_task(manage_clients(server_sock, client_list))
    prune_task = asyncio.create_task(prune_client_list(client_list))

    await asyncio.gather(manage_task, prune_task)

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

async def main():
    await run_server("192.168.1.3", 42069)
