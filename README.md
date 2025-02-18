# Discord Channel Scraper

A modern web application for scraping Discord channel messages with a React frontend and FastAPI backend.

## Features

- Scrape messages from any Discord channel you have access to
- Filter messages by start date
- Download options:
  - JSON export of messages
  - ZIP archive of attachments
  - Complete dataset with daily JSON files, CSV summary, and attachments
- Modern, responsive UI with Material-UI
- Save and manage Discord tokens and channel IDs
- Rate limit handling and progress tracking
- Docker support for easy deployment

## Prerequisites

### Option 1: Running with Docker (Recommended)
- Docker Desktop
- Docker Compose

### Option 2: Running Locally
- Node.js 16+ and npm
- Python 3.8+
- pip (Python package manager)

## Running with Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd discord-scraper
```

2. Start the application:
```bash
docker-compose up --build
```

3. Access the application:
   - Frontend: http://localhost:5173
   - Backend API docs: http://localhost:8000/docs

To stop the application:
```bash
docker-compose down
```

## Running Locally

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Start the backend server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the frontend development server:
```bash
npm run dev
```

## Usage

1. Get your Discord user token:
   - Open Discord in your browser
   - Press F12 to open Developer Tools
   - Go to Network tab
   - Click on any request to discord.com
   - Find the "Authorization" header in the request headers
   - Copy the token value

2. Find the channel ID:
   - Enable Developer Mode in Discord (Settings > App Settings > Advanced > Developer Mode)
   - Right-click on the channel > Copy ID

3. Using the application:
   - Enter your Discord token
   - Enter the channel ID
   - Select a start date for message scraping
   - Set the message limit (default: 1000)
   - Click "Scrape Messages"
   - Use the download options to export data:
     - JSON: Download messages in JSON format
     - Attachments: Download all attachments in a ZIP file
     - Complete Dataset: Download everything (JSON, CSV, attachments)

## Security Notes

- Never share your Discord user token
- The token is only stored locally in the SQLite database
- The application runs locally on your machine
- Downloaded message data should be handled securely

## Development

- Backend API documentation is available at http://localhost:8000/docs
- The frontend is built with React, TypeScript, and Material-UI
- The backend uses FastAPI and aiohttp for efficient async operations
- Data is stored in a SQLite database (located in `backend/data/`)

## Troubleshooting

### Common Issues

1. Frontend not starting:
   - Check if ports 5173 and 8000 are available
   - Ensure Docker has necessary permissions
   - Check Docker logs: `docker-compose logs frontend`

2. Download issues:
   - Large datasets may take time to generate
   - Check backend logs: `docker-compose logs backend`
   - Ensure enough disk space for temporary files

3. Network errors:
   - Verify Discord token is valid
   - Check your internet connection
   - Ensure Docker network is properly configured

### Getting Help

If you encounter issues:
1. Check the Docker logs: `docker-compose logs`
2. Verify all prerequisites are installed
3. Ensure no other services are using required ports
4. Try rebuilding the containers: `docker-compose up --build` 