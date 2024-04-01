from typing import Final
import os
from dotenv import load_dotenv
from discord import Intents, Client, Message, VoiceClient
import youtube_dl
import discord

# STEP 0: LOAD OUR TOKEN FROM SOMEWHERE SAFE
load_dotenv()

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

# Global variable to keep track of the voice client
voice_client: VoiceClient = None

# STEP 3: HANDLING THE STARTUP FOR OUR BOT
@client.event
async def on_ready() -> None:
    print(f'{client.user} is now running!')

# STEP 4: EVENT LISTENER
@client.event
async def on_message(message: Message) -> None:
    global voice_client

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

# STEP 5: MAIN ENTRY POINT
def main() -> None:
    client.run(os.getenv('DISCORD_TOKEN'))

if __name__ == '__main__':
    main()
