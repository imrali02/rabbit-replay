from typing import Final
import os
import discord
from dotenv import load_dotenv
from discord import Intents, Client, Message, VoiceClient
import youtube_dl
import asyncio
import time

# STEP 0: LOAD OUR TOKEN FROM SOMEWHERE SAFE
load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')

# STEP 1: BOT SETUP
intents: Intents = Intents.default()
intents.message_content = True
client: Client = Client(intents=intents)

# STEP 2: YTDL OPTIONS
ytdl_format_options = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# Global variables
voice_client: VoiceClient = None
last_activity_time = None

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

# STEP 4: EVENT LISTENER
@client.event
async def on_message(message: Message) -> None:
    global voice_client, last_activity_time

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

if __name__ == '__main__':
    asyncio.ensure_future(check_idle_time())  # Start the idle timer
    main()
