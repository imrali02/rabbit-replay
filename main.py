from typing import Final
import os
import discord
from dotenv import load_dotenv
from discord import Intents, Client, Message, VoiceClient
import youtube_dl
import asyncio
import time
import paho.mqtt.publish as publish

# LOAD OUR TOKEN FROM SOMEWHERE SAFE - testing git pull
load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')

# BOT SETUP
intents: Intents = Intents.default()
intents.message_content = True
client: Client = Client(intents=intents)

# YTDL OPTIONS
ytdl_format_options = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
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

# STEP 3: MAIN ENTRY POINT
def main() -> None:
    client.run(token=TOKEN)

# Function to check idle time and disconnect if necessary
async def check_idle_time():
    global voice_client, last_activity_time

    while True:
        await asyncio.sleep(300)  # Check every 5 minutes

        if voice_client and voice_client.is_connected():
            if last_activity_time and (time.time() - last_activity_time) > 300:
                await voice_client.disconnect()

# Function to publish message to MQTT broker
def trigger_buzzer(device_id):
    # send message with device_id to MQTT broker
    publish.single("goon", device_id, hostname="167.99.49.73", port=1883, auth = {'username':"goon_user",
         'password': "kurapikaisnowdrowning"})

# Trigger buzzers for all non-gooners
def trigger_buzzers_for_all_devices(goon_users):
    for user_id, device_id in user_dict.items():
        if user_id not in goon_users:
            trigger_buzzer(device_id)
            
# STEP 4: EVENT LISTENER
@client.event
async def on_message(message: Message) -> None:
    global voice_client, last_activity_time, goon_users

    if message.author == client.user:
        return

    if message.content.startswith('!play'):
        voice_channel = message.author.voice.channel
        if voice_channel:
            try:
                if voice_client and voice_client.is_connected():
                    await voice_client.move_to(voice_channel)
                else:
                    voice_client = await voice_channel.connect()

                url = message.content.split(' ', 1)[1]
                with ytdl:
                    info = ytdl.extract_info(url, download=False)
                    url2 = info['formats'][0]['url']
                voice_client.play(discord.FFmpegPCMAudio(url2))
            except Exception as e:
                print(e)
                await message.channel.send("An error occurred while trying to play the video.")
        else:
            await message.channel.send("You need to be in a voice channel to use this command.")

        # Update last activity time
        last_activity_time = time.time()

    elif message.content.startswith('!stop'):
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await message.channel.send("Playback stopped.")
        else:
            await message.channel.send("No video is currently playing.")

    elif message.content.startswith('!goon'):
        if message.author.id not in goon_users:
            goon_users.add(message.author.id)
            await message.channel.send(f"{message.author.mention} has joined the gooning squad! {len(goon_users)}/2")

            if len(goon_users) == 2:
                await message.channel.send("It's gooning time!")
                trigger_buzzers_for_all_devices(goon_users)
                goon_users.clear()

if __name__ == '__main__':
    asyncio.ensure_future(check_idle_time())  # Start the idle timer
    main()
