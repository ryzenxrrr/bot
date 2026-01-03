import discord
import requests
import asyncio
import re
import time
import os

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

CHECK_INTERVAL = 30  # 30 seconds

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

account_status = {}
username_pattern = re.compile(r"^[a-zA-Z0-9._]{1,30}$")

def format_time(seconds):
    minutes, _ = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts = []
    if days: parts.append(f"{days} day(s)")
    if hours: parts.append(f"{hours} hour(s)")
    if minutes: parts.append(f"{minutes} minute(s)")
    return " ".join(parts) if parts else "a few seconds"

def check_account(username):
    url = "https://www.instagram.com/api/v1/users/web_profile_info/"
    params = {"username": username}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instagram.com/",
        "X-IG-App-ID": "936619743392459"
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 404:
            return {"status": "suspended", "followers": None}
        if r.status_code != 200:
            return {"status": "error", "followers": None}
        data = r.json()
        if data.get("status") != "ok":
            return {"status": "error", "followers": None}
        user = data["data"]["user"]
        followers = user["edge_followed_by"]["count"]
        is_private = user["is_private"]
        # If the username matches and we get a user object, it's active
        return {"status": "active", "followers": followers}
    except Exception:
        return {"status": "error", "followers": None}



@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    client.loop.create_task(monitor_accounts())

async def monitor_accounts():
    channel = client.get_channel(CHANNEL_ID)

    while True:
        for username in list(account_status.keys()):
            # 1️⃣ Previous status
            previous_status = account_status[username]["current_status"]

            # 2️⃣ Check Instagram
            result = check_account(username)
            current_status = result["status"]
            followers = result["followers"]

            # 3️⃣ Update stored status
            account_status[username]["current_status"] = current_status

            # 4️⃣ Recovery condition
            if (
                (previous_status == "unknown" or previous_status == "suspended")
                and current_status == "active"
            ):
                elapsed = int(time.time() - account_status[username]["added_at"])

                await channel.send(
                    f"✅ Instagram Account Recovered!\n"
                    f"@{username}\n"
                    f"⏱ Time taken: {format_time(elapsed)}\n"
                    f"👥 Followers: {followers or 'Unknown'}\n"
                    f"🔗 https://instagram.com/{username}"
                )

                # Remove account from monitoring after notification
                del account_status[username]
                continue  # Skip further processing for this account


        await asyncio.sleep(CHECK_INTERVAL)


@client.event
async def on_message(message):
    if message.author.bot:
        return

    # ✅ STEP 1: ALWAYS define content FIRST
    content = message.content.strip().lower()

    # -------- STATUS COMMAND --------
    if content.startswith("!status"):
        parts = content.split()

        # !status
        if len(parts) == 1:
            if not account_status:
                await message.channel.send("📊 No accounts are being monitored.")
                return

            msg = ["📊 Instagram Account Status\n"]
            for u, data in account_status.items():
                status = "✅ Active" if data["current_status"] == "active" else "❌ Suspended"
                followers = data.get("followers", "Unknown")
                msg.append(f'@{u} → {status} | Followers: {followers}')

            await message.channel.send("\n".join(msg))
            return

        # !status @username
        if len(parts) == 2:
            username = parts[1].lstrip("@")

            if username not in account_status:
                await message.channel.send(f"❌ @{username} is not being monitored.")
                return

            data = account_status[username]
            if data["current_status"] == "active":
                status = "✅ Active"
            elif data["current_status"] == "unknown" or data["current_status"] == "suspended":
                status = "❌ Suspended"
            else:
                 status = "⚠️ Unknown"


            await message.channel.send(
                f"📊 Status for @{username}\n"
                f"Status: {status} | Followers: {data.get('followers', 'Unknown')}\n"
            )
            return

        await message.channel.send("❌ Use ⁠ !status ⁠ or ⁠ !status @username ⁠")
        return

    # -------- MONITOR USERNAME --------
    if content.startswith("@"):
        content = content[1:]

    if username_pattern.match(content):
        if content in account_status:
            await message.channel.send(f"ℹ️ @{content} is already being monitored.")
        else:
            result = check_account(content)

            account_status[content] = {
                "initial_status": result["status"],
                "current_status": result["status"],
                "followers": result["followers"],
                "added_at": time.time()
            }

            await message.channel.send(
                f"👀 Now monitoring @{content}\n⏱ Timer started"
            )

client.run(TOKEN)