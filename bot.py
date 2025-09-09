import discord
import aiohttp
import asyncio
import os
from datetime import datetime

# === CONFIG ===
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_USERNAMES = os.getenv("TWITCH_USERNAMES", "")
usernames = [u.strip().lower() for u in TWITCH_USERNAMES.split(",") if u.strip()]


CHECK_INTERVAL = 60  # in seconds

intents = discord.Intents.default()
client = discord.Client(intents=intents)

access_token = None
user_ids = {}
for uname in usernames:
    try:
        ids = await get_user_ids(session, access_token, [uname])
        if uname in ids:
            user_ids[uname] = ids[uname]
        else:
            print(f"⚠ Username not found: {uname}")
    except Exception as e:
        print(f"⚠ Error fetching ID for {uname}: {e}")
if not user_ids:
    print("No valid Twitch usernames found—stopping.")
    return
live_status = {}  # username -> bool

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

async def get_user_ids(session, token, usernames):
    url = f"https://api.twitch.tv/helix/users?login={'&login='.join(usernames)}"
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {token}'
    }
    async with session.get(url, headers=headers) as resp:
        data = await resp.json()
        results = {}
        for user in data.get("data", []):
            results[user["login"].lower()] = user["id"]
        return results

async def check_streams(session, token, ids):
    url = f"https://api.twitch.tv/helix/streams?user_id=" + "&user_id=".join(ids)
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {token}'
    }
    async with session.get(url, headers=headers) as resp:
        data = await resp.json()
        return {stream["user_login"]: stream for stream in data.get("data", [])}

async def monitor_streams():
    global access_token, user_ids

    await client.wait_until_ready()
    channel = client.get_channel(DISCORD_CHANNEL_ID)

    async with aiohttp.ClientSession() as session:
        access_token = await get_twitch_token(session)
        user_ids = await get_user_ids(session, access_token, TWITCH_USERNAMES)

        if not user_ids:
            print("❌ Could not fetch user IDs.")
            return

        for username in TWITCH_USERNAMES:
            live_status[username] = False

        print(f"✅ Monitoring streamers: {', '.join(user_ids.keys())}")

        while not client.is_closed():
            try:
                streams = await check_streams(session, access_token, list(user_ids.values()))

                live_now = set(streams.keys())

                for username in TWITCH_USERNAMES:
                    was_live = live_status.get(username, False)
                    is_now_live = username in live_now

                    if is_now_live and not was_live:
                        stream = streams[username]
                        title = stream['title']
                        game = stream.get('game_name', 'Unknown')
                        url = f"https://twitch.tv/{username}"
                        message = (
                            f"🔴 **{username.upper()} is now LIVE!**\n"
                            f"**Title**: {title}\n"
                            f"**Game**: {game}\n"
                            f"🔗 {url}"
                        )
                        await channel.send(message)
                        print(f"[{datetime.now()}] {username} went live.")
                    elif not is_now_live and was_live:
                        print(f"[{datetime.now()}] {username} went offline.")

                    live_status[username] = is_now_live

            except Exception as e:
                print(f"⚠️ Error checking streams: {e}")

            await asyncio.sleep(CHECK_INTERVAL)

@client.event
async def on_ready():
    print(f"🤖 Logged in as {client.user}")
    client.loop.create_task(monitor_streams())

client.run(DISCORD_TOKEN)
