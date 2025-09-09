import discord
import aiohttp
import asyncio
import os
from datetime import datetime

# === CONFIG FROM ENVIRONMENT VARIABLES ===
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_USERNAME = os.getenv("TWITCH_USERNAME").lower()  # e.g. 'xqc'

CHECK_INTERVAL = 60  # seconds

# === DISCORD CLIENT SETUP ===
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# === GLOBAL STATE ===
access_token = None
is_live = False
user_id = None

# === TWITCH API HELPERS ===

async def get_twitch_token(session):
    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    async with session.post(url, params=params) as resp:
        data = await resp.json()
        return data['access_token']

async def get_user_id(session, token, username):
    url = f'https://api.twitch.tv/helix/users?login={username}'
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {token}'
    }
    async with session.get(url, headers=headers) as resp:
        data = await resp.json()
        if data['data']:
            return data['data'][0]['id']
        return None

async def check_stream(session, token, user_id):
    url = f'https://api.twitch.tv/helix/streams?user_id={user_id}'
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {token}'
    }
    async with session.get(url, headers=headers) as resp:
        data = await resp.json()
        if data['data']:
            return True, data['data'][0]
        return False, None

# === MAIN MONITOR LOOP ===

async def monitor_stream():
    global access_token, is_live, user_id

    await client.wait_until_ready()
    channel = client.get_channel(DISCORD_CHANNEL_ID)

    async with aiohttp.ClientSession() as session:
        access_token = await get_twitch_token(session)
        user_id = await get_user_id(session, access_token, TWITCH_USERNAME)

        if not user_id:
            print(f"❌ Twitch user not found: {TWITCH_USERNAME}")
            return

        print(f"✅ Monitoring Twitch user: {TWITCH_USERNAME} (ID: {user_id})")

        while not client.is_closed():
            try:
                live, stream_data = await check_stream(session, access_token, user_id)

                if live and not is_live:
                    is_live = True
                    title = stream_data['title']
                    game = stream_data.get('game_name', 'Unknown')
                    url = f"https://twitch.tv/{TWITCH_USERNAME}"

                    message = f"🔴 **{TWITCH_USERNAME.upper()} is now LIVE!**\n" \
                              f"**Title**: {title}\n" \
                              f"**Game**: {game}\n" \
                              f"🔗 {url}"

                    await channel.send(message)
                    print(f"[{datetime.now()}] {TWITCH_USERNAME} went live.")

                elif not live and is_live:
                    is_live = False
                    print(f"[{datetime.now()}] {TWITCH_USERNAME} is offline.")

            except Exception as e:
                print(f"⚠️ Error checking stream: {e}")

            await asyncio.sleep(CHECK_INTERVAL)

# === DISCORD BOT ENTRYPOINT ===

@client.event
async def on_ready():
    print(f"🤖 Logged in as {client.user}")
    client.loop.create_task(monitor_stream())

# === START BOT ===

client.run(DISCORD_TOKEN)
