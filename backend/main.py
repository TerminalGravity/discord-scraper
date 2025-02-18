from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import Session
import aiohttp
import json
import asyncio
import logging
import io
import zipfile
import os
from typing import List, Optional
from database import get_db, SavedCredential, SavedChannel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a directory for temporary files
TEMP_DIR = "temp_downloads"
os.makedirs(TEMP_DIR, exist_ok=True)

class ScrapeRequest(BaseModel):
    token: str
    channel_id: str
    start_date: str
    message_limit: int = 1000

    class Config:
        # Add schema validation logging
        @classmethod
        def __get_validators__(cls):
            validators = super().__get_validators__()
            for validator in validators:
                logger.info(f"Running validator: {validator.__name__}")
                yield validator

class MessageAuthor(BaseModel):
    id: str
    username: str

class Attachment(BaseModel):
    url: str
    filename: str

class Message(BaseModel):
    id: str
    content: str
    timestamp: str
    author: MessageAuthor
    attachments: List[Attachment]
    referenced_message: Optional[dict] = None

class ScrapeResponse(BaseModel):
    messages: List[Message]
    message_count: int
    download_urls: dict

class SaveCredentialRequest(BaseModel):
    token: str

class SaveChannelRequest(BaseModel):
    channel_id: str
    name: Optional[str] = None

async def download_attachment(session, url, filename):
    """Download an attachment from Discord with timeout and chunked download."""
    try:
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_connect=10, sock_read=10)
        async with session.get(url, timeout=timeout) as response:
            if response.status == 200:
                file_path = os.path.join(TEMP_DIR, filename)
                with open(file_path, "wb") as f:
                    # Download in chunks to handle large files
                    chunk_size = 1024 * 1024  # 1MB chunks
                    while True:
                        chunk = await response.content.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                return file_path
            else:
                logger.error(f"Failed to download {filename}: HTTP {response.status}")
                return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout downloading {filename}")
        return None
    except Exception as e:
        logger.error(f"Error downloading attachment {filename}: {e}")
        return None

@app.post("/api/scrape", response_model=ScrapeResponse)
async def scrape_messages(request: ScrapeRequest):
    try:
        logger.info(f"Received scrape request for channel: {request.channel_id}")
        logger.info(f"Start date: {request.start_date}")
        
        headers = {
            "Authorization": f"{request.token}",  # Log token format but not the actual token
            "Content-Type": "application/json"
        }
        logger.info(f"Authorization header format: {'Bot' if request.token.startswith('Bot') else 'User'} token")

        url = f"https://discord.com/api/v9/channels/{request.channel_id}/messages"
        params = {"limit": 100}
        all_messages = []
        
        try:
            # Log timestamp conversion
            start_timestamp = int(datetime.strptime(request.start_date, "%Y-%m-%d").timestamp() * 1000)
            logger.info(f"Converted start date {request.start_date} to timestamp {start_timestamp}")
        except ValueError as e:
            logger.error(f"Date conversion error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

        async with aiohttp.ClientSession() as session:
            while len(all_messages) < request.message_limit:
                try:
                    async with session.get(url, headers=headers, params=params) as response:
                        logger.info(f"Discord API response status: {response.status}")
                        
                        if response.status == 200:
                            new_messages = await response.json()
                            logger.info(f"Fetched {len(new_messages)} messages")
                            
                            if not new_messages:
                                break
                            
                            # Filter messages by date
                            filtered_messages = []
                            for msg in new_messages:
                                try:
                                    msg_timestamp = int(datetime.fromisoformat(msg["timestamp"]).timestamp() * 1000)
                                    if msg_timestamp >= start_timestamp:
                                        # Extract referenced message if it exists
                                        referenced_message = None
                                        if msg.get("referenced_message"):
                                            ref = msg["referenced_message"]
                                            # Get the full message content for cross-channel forwards
                                            referenced_content = ref.get("content", "")
                                            if not referenced_content and ref.get("channel_id") != request.channel_id:
                                                try:
                                                    ref_channel_url = f"https://discord.com/api/v9/channels/{ref['channel_id']}/messages/{ref['id']}"
                                                    async with session.get(ref_channel_url, headers=headers) as ref_response:
                                                        if ref_response.status == 200:
                                                            ref_data = await ref_response.json()
                                                            referenced_content = ref_data.get("content", "")
                                                            # Update attachments from the original message
                                                            ref["attachments"] = ref_data.get("attachments", [])
                                                except Exception as e:
                                                    logger.error(f"Error fetching referenced message {ref['id']}: {e}")
                                                    referenced_content = ref.get("content", "")

                                            referenced_message = {
                                                "id": ref["id"],
                                                "content": referenced_content,
                                                "timestamp": ref["timestamp"],
                                                "channel_id": ref.get("channel_id"),
                                                "author": {
                                                    "id": ref["author"]["id"],
                                                    "username": ref["author"]["username"]
                                                },
                                                "attachments": [
                                                    {
                                                        "url": att["url"],
                                                        "filename": att["filename"]
                                                    }
                                                    for att in ref.get("attachments", [])
                                                ]
                                            }

                                        message_data = {
                                            "id": msg["id"],
                                            "content": msg["content"],
                                            "timestamp": msg["timestamp"],
                                            "channel_id": msg.get("channel_id", request.channel_id),
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
                                            ],
                                            "referenced_message": referenced_message
                                        }
                                        filtered_messages.append(message_data)
                                    else:
                                        logger.info(f"Message {msg['id']} filtered out due to timestamp {msg_timestamp} < {start_timestamp}")
                                        break
                                except Exception as e:
                                    logger.error(f"Error processing message {msg.get('id', 'unknown')}: {e}")
                                    continue
                                    
                            if filtered_messages:
                                logger.info(f"Added {len(filtered_messages)} filtered messages")
                                all_messages.extend(filtered_messages)
                                params["before"] = new_messages[-1]["id"]
                            else:
                                logger.info("No more messages matching date filter")
                                break
                        else:
                            error_text = await response.text()
                            logger.error(f"Discord API error: {response.status}, {error_text}")
                            raise HTTPException(
                                status_code=response.status,
                                detail=f"Discord API error: {error_text}"
                            )
                except Exception as e:
                    logger.error(f"Request error: {e}")
                    raise

                # Rate limit handling
                await asyncio.sleep(0.5)
                logger.debug("Rate limit sleep complete")

        logger.info(f"Returning {len(all_messages)} messages")
        
        # Create a more detailed response that includes download URLs
        response_data = {
            "messages": all_messages[:request.message_limit],
            "message_count": len(all_messages),
            "download_urls": {
                "json": f"/api/download/json/{request.channel_id}",
                "attachments": f"/api/download/attachments/{request.channel_id}",
                "dataset": f"/api/download/dataset/{request.channel_id}"
            }
        }

        # Store the messages in memory for download endpoints
        app.state.channel_messages = {
            request.channel_id: all_messages[:request.message_limit]
        }

        return response_data

    except Exception as e:
        logger.error(f"Scraping error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/json/{channel_id}")
async def download_json(channel_id: str):
    """Download messages as JSON file."""
    try:
        if not hasattr(app.state, 'channel_messages') or channel_id not in app.state.channel_messages:
            raise HTTPException(status_code=404, detail="No data found for this channel")

        messages = app.state.channel_messages[channel_id]
        
        # Create a JSON string with proper formatting
        json_str = json.dumps({
            "channel_id": channel_id,
            "message_count": len(messages),
            "messages": messages
        }, indent=2)

        # Create in-memory bytes buffer
        json_bytes = json_str.encode('utf-8')
        
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="discord_messages_{channel_id}.json"'
            }
        )
    except Exception as e:
        logger.error(f"Error creating JSON download: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/attachments/{channel_id}")
async def download_attachments(channel_id: str):
    """Download all attachments as a zip file."""
    try:
        if not hasattr(app.state, 'channel_messages') or channel_id not in app.state.channel_messages:
            raise HTTPException(status_code=404, detail="No data found for this channel")

        messages = app.state.channel_messages[channel_id]
        
        # Create in-memory zip file
        zip_buffer = io.BytesIO()
        
        async with aiohttp.ClientSession() as session:
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add a metadata.json file
                metadata = {
                    "channel_id": channel_id,
                    "message_count": len(messages),
                    "download_date": datetime.now().isoformat()
                }
                zip_file.writestr("metadata.json", json.dumps(metadata, indent=2))

                # Download and add attachments
                for msg in messages:
                    for att in msg.get("attachments", []):
                        file_path = await download_attachment(session, att["url"], att["filename"])
                        if file_path:
                            # Create a directory structure: channel_id/message_id/filename
                            zip_path = f"{channel_id}/{msg['id']}/{att['filename']}"
                            zip_file.write(file_path, zip_path)
                            os.remove(file_path)  # Clean up the temporary file

        # Reset buffer position
        zip_buffer.seek(0)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="discord_attachments_{channel_id}.zip"'
            }
        )
    except Exception as e:
        logger.error(f"Error creating attachments zip: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/credentials/save")
async def save_credential(request: SaveCredentialRequest, db: Session = Depends(get_db)):
    """Save a Discord token."""
    try:
        # Check if token works before saving
        headers = {"Authorization": request.token, "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://discord.com/api/v9/users/@me", headers=headers) as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail="Invalid Discord token")

        # Save or update the token
        cred = db.query(SavedCredential).filter(SavedCredential.token == request.token).first()
        if not cred:
            cred = SavedCredential(token=request.token)
            db.add(cred)
        cred.last_used = datetime.utcnow()
        db.commit()
        return {"message": "Token saved successfully"}
    except Exception as e:
        logger.error(f"Error saving credential: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/credentials/latest")
async def get_latest_credential(db: Session = Depends(get_db)):
    """Get the most recently used token."""
    cred = db.query(SavedCredential).order_by(SavedCredential.last_used.desc()).first()
    if not cred:
        raise HTTPException(status_code=404, detail="No saved credentials found")
    return {"token": cred.token}

@app.post("/api/channels/save")
async def save_channel(request: SaveChannelRequest, db: Session = Depends(get_db)):
    """Save a Discord channel ID."""
    try:
        channel = db.query(SavedChannel).filter(SavedChannel.channel_id == request.channel_id).first()
        if not channel:
            channel = SavedChannel(channel_id=request.channel_id, name=request.name)
            db.add(channel)
        channel.last_used = datetime.utcnow()
        if request.name:
            channel.name = request.name
        db.commit()
        return {"message": "Channel saved successfully"}
    except Exception as e:
        logger.error(f"Error saving channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/channels")
async def get_channels(db: Session = Depends(get_db)):
    """Get all saved channel IDs."""
    channels = db.query(SavedChannel).order_by(SavedChannel.last_used.desc()).all()
    return {"channels": [{"id": c.channel_id, "name": c.name} for c in channels]}

@app.get("/api/download/dataset/{channel_id}")
async def download_complete_dataset(channel_id: str):
    """Download complete dataset including messages, attachments, and metadata."""
    try:
        if not hasattr(app.state, 'channel_messages') or channel_id not in app.state.channel_messages:
            raise HTTPException(status_code=404, detail="No data found for this channel")

        messages = app.state.channel_messages[channel_id]
        logger.info(f"Starting dataset download for channel {channel_id} with {len(messages)} messages")
        
        # Create a temporary directory for this download
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = os.path.join(TEMP_DIR, f"dataset_{channel_id}_{timestamp}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create the zip file on disk instead of in memory
        zip_path = os.path.join(temp_dir, f"discord_dataset_{channel_id}_{timestamp}.zip")
        
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minute total timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add dataset metadata
                metadata = {
                    "channel_id": channel_id,
                    "message_count": len(messages),
                    "download_date": datetime.now().isoformat(),
                    "first_message_date": messages[-1]["timestamp"] if messages else None,
                    "last_message_date": messages[0]["timestamp"] if messages else None,
                    "unique_authors": len(set(msg["author"]["id"] for msg in messages)),
                    "attachment_count": sum(len(msg["attachments"]) for msg in messages)
                }
                zip_file.writestr("metadata.json", json.dumps(metadata, indent=2))
                logger.info("Added metadata.json to dataset")

                # Add messages JSON with daily organization
                messages_by_date = {}
                for msg in messages:
                    date = msg["timestamp"].split("T")[0]
                    if date not in messages_by_date:
                        messages_by_date[date] = []
                    messages_by_date[date].append(msg)

                for date, daily_messages in messages_by_date.items():
                    zip_file.writestr(
                        f"messages/{date}.json",
                        json.dumps(daily_messages, indent=2)
                    )
                logger.info("Added daily message JSON files to dataset")

                # Add all messages in one file
                zip_file.writestr(
                    "messages/all_messages.json",
                    json.dumps(messages, indent=2)
                )
                logger.info("Added all_messages.json to dataset")

                # Download and add attachments with date-based organization
                total_attachments = sum(len(msg["attachments"]) for msg in messages)
                downloaded_attachments = 0
                
                for msg in messages:
                    msg_date = msg["timestamp"].split("T")[0]
                    for att in msg["attachments"]:
                        downloaded_attachments += 1
                        logger.info(f"Downloading attachment {downloaded_attachments}/{total_attachments}: {att['filename']}")
                        
                        file_path = await download_attachment(session, att["url"], att["filename"])
                        if file_path:
                            # Create a directory structure: attachments/date/message_id/filename
                            zip_path_in_archive = f"attachments/{msg_date}/{msg['id']}/{att['filename']}"
                            zip_file.write(file_path, zip_path_in_archive)
                            os.remove(file_path)  # Clean up the temporary file
                        else:
                            logger.warning(f"Failed to download attachment: {att['filename']}")

                logger.info("Finished downloading attachments")

                # Create a CSV summary of messages
                csv_buffer = io.StringIO()
                csv_buffer.write("Date,Time,Author,Content,Attachment Count\n")
                for msg in messages:
                    date, time = msg["timestamp"].split("T")
                    time = time.split(".")[0]
                    content = msg["content"].replace('"', '""')
                    csv_buffer.write(
                        f'{date},{time},{msg["author"]["username"]},'
                        f'"{content}",{len(msg["attachments"])}\n'
                    )
                zip_file.writestr("summary.csv", csv_buffer.getvalue())
                logger.info("Added summary.csv to dataset")

        logger.info("Dataset creation complete, sending response")

        # Stream the file from disk
        def iterfile():
            with open(zip_path, 'rb') as f:
                while chunk := f.read(8192):  # 8KB chunks
                    yield chunk
            # Cleanup after streaming is complete
            os.remove(zip_path)
            os.rmdir(temp_dir)
        
        return StreamingResponse(
            iterfile(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="discord_dataset_{channel_id}_{timestamp}.zip"'
            }
        )
    except Exception as e:
        # Cleanup on error
        if 'temp_dir' in locals():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Error creating dataset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
