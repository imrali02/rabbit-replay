from typing import Final
from friend import Friend
from bot_helper import send_command_all, send_command_list, send_command_single
import os
from dotenv import load_dotenv
import discord
from discord import Intents, VoiceClient, app_commands
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
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

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
inactive_seconds = 0  # Counter for inactivity time
        
@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user}')
    try:
        await tree.sync()
        logging.info("Command tree synced")
    except Exception as e:
        logging.error(f"Failed to sync command tree: {e}")

# goon commands
@tree.command(name="goon", description="Join the gooning squad.")
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

@tree.command(name="goon_target", description="Send goons after a target.")
async def goon_target(interaction: discord.Interaction, target: str):
    await interaction.response.defer()
    await interaction.followup.send(f"sending the goons after {target}")
    result = send_command_single(ip, port, target)
    await interaction.followup.send(result)

@tree.command(name="goon_list", description="Ask server for goon targets list.")
async def goon_list(interaction: discord.Interaction):
    await interaction.response.defer()
    result = send_command_list(ip, port)
    await interaction.followup.send(result)

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


