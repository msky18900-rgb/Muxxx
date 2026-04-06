import os
import requests
import asyncio
from pyrogram import Client, filters

# Setup from GitHub Repository Secrets
app = Client("my_bot", 
             api_id=os.getenv("API_ID"), 
             api_hash=os.getenv("API_HASH"), 
             session_string=os.getenv("STRING_SESSION"))

MUX_ID = os.getenv("MUX_TOKEN_ID")
MUX_SECRET = os.getenv("MUX_TOKEN_SECRET")

video_queue = asyncio.Queue()

async def mux_uploader():
    """Processes videos one by one from the queue."""
    while True:
        message = await video_queue.get()
        try:
            status_msg = await message.reply("📥 **Step 1: Downloading from Telegram...**")
            file_path = await message.download()

            await status_msg.edit("🚀 **Step 2: Pushing to Mux (Direct Upload)...**")
            # Create Direct Upload slot on Mux
            r = requests.post(
                "https://api.mux.com/video/v1/uploads",
                auth=(MUX_ID, MUX_SECRET),
                json={
                    "new_asset_settings": {
                        "playback_policy": ["public"],
                        "video_quality": "basic" 
                    },
                    "cors_origin": "*"
                }
            ).json()
            
            upload_url = r["data"]["url"]
            upload_id = r["data"]["id"]

            # Actual file upload to Mux
            with open(file_path, "rb") as f:
                requests.put(upload_url, data=f)

            # Cleanup local GitHub storage immediately to save space
            os.remove(file_path)

            await status_msg.edit("⚙️ **Step 3: Generating your Player...**")
            
            # Wait for Mux to finalize the Playback ID
            playback_id = None
            while not playback_id:
                asset_poll = requests.get(f"https://api.mux.com/video/v1/uploads/{upload_id}", auth=(MUX_ID, MUX_SECRET)).json()
                asset_id = asset_poll["data"].get("asset_id")
                if asset_id:
                    asset_info = requests.get(f"https://api.mux.com/video/v1/assets/{asset_id}", auth=(MUX_ID, MUX_SECRET)).json()
                    playback_id = asset_info["data"]["playback_ids"][0]["id"]
                await asyncio.sleep(5)

            # The official Mux Player URL
            player_url = f"https://player.mux.com/{playback_id}"
            
            await status_msg.edit(
                f"✅ **Lecture Ready!**\n\n"
                f"📺 **[OPEN PLAYER]({player_url})**\n\n"
                f"💡 **Data Saver:** Click ⚙️ in the player and select **240p** or **360p**."
            )

        except Exception as e:
            await message.reply(f"❌ **Error:** {str(e)}")
        finally:
            video_queue.task_done()

@app.on_message(filters.video & filters.me)
async def add_to_queue(client, message):
    await video_queue.put(message)
    await message.reply(f"📝 Added to queue. Position: {video_queue.qsize()}")

async def main():
    async with app:
        asyncio.create_task(mux_uploader())
        print("Bot is live. Forward a video to yourself.")
        await asyncio.Event().wait()

app.run(main())
