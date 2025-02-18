import marimo

__generated_with = "0.11.5"
app = marimo.App()


@app.cell
def imports():
    import aiohttp
    import json
    import os
    import asyncio
    from datetime import datetime
    import marimo as mo
    return aiohttp, asyncio, datetime, json, mo, os


@app.cell
def state(mo):
    messages = mo.state([])
    return messages


@app.cell
def ui_components(mo):
    token_input = mo.ui.text(label="User Token", placeholder="Paste your user token here")
    channel_id_input = mo.ui.text(label="Channel ID", placeholder="Enter target channel ID")
    start_date = mo.ui.date(label="Start Date")
    limit_input = mo.ui.number(1, 10000, label="Max messages to fetch", value=1000)
    scrape_btn = mo.ui.button(label="Start Scraping")
    return channel_id_input, limit_input, scrape_btn, start_date, token_input


@app.cell
def header(channel_id_input, limit_input, mo, scrape_btn, start_date, token_input):
    mo.md(
        f"""
        ## Discord Channel Scraper

        **Instructions:**
        1. Get your user token [using this guide](https://github.com/Tyrrrz/DiscordChatExporter/blob/master/.docs/Token-and-IDs.md)
        2. Find the channel ID (right-click channel > Copy ID)
        3. Select start date and enter details below
        4. Click Start to begin scraping
        """
    ).callout()

    mo.hstack([token_input, channel_id_input, start_date, limit_input], justify="start").center()
    scrape_btn.center()
    return


@app.cell
def functions(
    aiohttp,
    asyncio,
    channel_id_input,
    datetime,
    json,
    limit_input,
    messages,
    mo,
    start_date,
    token_input,
):
    async def fetch_messages():
        """Fetch messages from Discord API"""
        headers = {
            "Authorization": token_input.value,
            "Content-Type": "application/json"
        }

        url = f"https://discord.com/api/v9/channels/{channel_id_input.value}/messages"
        params = {"limit": 100}
        all_messages = []
        start_timestamp = int(datetime.strptime(start_date.value, "%Y-%m-%d").timestamp() * 1000)

        async with aiohttp.ClientSession() as session:
            while len(all_messages) < limit_input.value:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        new_messages = await response.json()
                        if not new_messages:
                            break
                            
                        # Filter messages by date
                        filtered_messages = []
                        for msg in new_messages:
                            msg_timestamp = int(datetime.fromisoformat(msg["timestamp"]).timestamp() * 1000)
                            if msg_timestamp >= start_timestamp:
                                # Extract relevant message data including attachments
                                message_data = {
                                    "id": msg["id"],
                                    "content": msg["content"],
                                    "timestamp": msg["timestamp"],
                                    "author": {
                                        "id": msg["author"]["id"],
                                        "username": msg["author"]["username"]
                                    },
                                    "attachments": [
                                        {
                                            "url": att["url"],
                                            "filename": att["filename"]
                                        }
                                        for att in msg.get("attachments", [])
                                    ]
                                }
                                filtered_messages.append(message_data)
                            else:
                                # Stop if we've gone past our start date
                                break
                                
                        if filtered_messages:
                            all_messages.extend(filtered_messages)
                            params["before"] = new_messages[-1]["id"]
                        else:
                            break
                    else:
                        mo.ui.alert(f"Error: {response.status}", type="error")
                        break

                # Rate limit handling
                await asyncio.sleep(0.5)

        messages.value = all_messages[:limit_input.value]

    def save_data():
        """Save messages to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        messages_file = f"discord_messages_{timestamp}.json"
        
        with open(messages_file, "w") as f:
            json.dump(messages.value, f, indent=2)

        return messages_file
    
    return fetch_messages, save_data


@app.cell
def handle_scraping(
    channel_id_input,
    fetch_messages,
    messages,
    mo,
    save_data,
    scrape_btn,
    token_input,
):
    async def _handle_scraping():
        if not token_input.value or not channel_id_input.value:
            mo.ui.alert("Missing token or channel ID!", type="error")
        else:
            with mo.status.spinner("Scraping messages..."):
                await fetch_messages()

            msg_count = len(messages.value)

            if msg_count > 0:
                messages_file = save_data()
                mo.md(
                    f"""
                    ## Results ✅
                    - **Messages scraped:** {msg_count}
                    - **Saved file:** `{messages_file}`
                    """
                ).callout(kind="success")

                mo.download(messages_file, label="Download Messages JSON")
            else:
                mo.ui.alert("No messages found!", type="warning")

    if scrape_btn.value:
        mo.run_async(_handle_scraping())
    return


@app.cell
def security_reminder(mo):
    mo.md(
        """
        🔒 **Security Note:** 
        - This notebook will NOT save your token
        - Delete downloaded files after use
        - Never share the .json files containing message data
        """
    ).callout(kind="warn")
    return


if __name__ == "__main__":
    app.run()
