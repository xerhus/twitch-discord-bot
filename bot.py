import os
import discord
import aiohttp
import asyncio

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_USERNAMES = os.getenv("TWITCH_USERNAMES", "")  # comma-separated

# Clean and prepare list of usernames
STREAMERS = [u.strip().lower() for u in TWITCH_USERNAMES.split(",") if u.strip()]

intents = discord.Intents.default()
client = discord.Client(intents=intents)

async def get_twitch_token(session):
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    async with session.post(url, params=params) as resp:
        data = await resp.json()
        return data.get("access_token")

async def get_user_id(session, access_token, username):
    url = "https://api.twitch.tv/helix/users"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {access_token}",
    }
    params = {"login": username}
    async with session.get(url, headers=headers, params=params) as resp:
        data = await resp.json()
        users = data.get("data", [])
        if users:
            return users[0]["id"]
        else:
            print(f"⚠ Username not found on Twitch: {username}")
            return None

async def check_streams(client, channel, user_ids, session, access_token):
    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {access_token}",
    }

    live_now = set()
    while True:
        params = []
        for uid in user_ids:
            params.append(("user_id", uid))

        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()
            streams = data.get("data", [])
            live_now.clear()
            for stream in streams:
                live_now.add(stream["user_login"].lower())

        for username in STREAMERS:
            if username in live_now:
                await channel.send(f"🔴 **{username}** is now LIVE on Twitch! https://twitch.tv/{username}")
        
        await asyncio.sleep(60)  # Check every 60 seconds

@client.event
async def on_ready():
    print(f"🤖 Logged in as {client.user}")
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if channel is None:
        print(f"❌ Could not find Discord channel with ID {DISCORD_CHANNEL_ID}")
        await client.close()
        return

    async with aiohttp.ClientSession() as session:
        access_token = await get_twitch_token(session)
        if not access_token:
            print("❌ Could not get Twitch access token")
            await client.close()
            return

        user_ids = []
        for username in STREAMERS:
            uid = await get_user_id(session, access_token, username)
            if uid:
                user_ids.append(uid)

        if not user_ids:
            print("❌ No valid Twitch user IDs found. Stopping bot.")
            await client.close()
            return
        
        print(f"✅ Monitoring streamers: {', '.join(STREAMERS)}")
        await check_streams(client, channel, user_ids, session, access_token)

client.run(DISCORD_TOKEN)
