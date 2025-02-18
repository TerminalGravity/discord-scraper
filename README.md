# Discord Channel Scraper

A modern web application for scraping Discord channel messages with a React frontend and FastAPI backend.

## Features

- Scrape messages from any Discord channel you have access to
- Filter messages by start date
- View message content and attachments
- Modern, responsive UI with Material-UI
- Secure token handling
- Rate limit handling

## Prerequisites

- Node.js 16+ and npm
- Python 3.8+
- pip (Python package manager)

## Installation

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

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

## Running the Application

1. Start the backend server (from the backend directory):
```bash
uvicorn main:app --reload
```

2. Start the frontend development server (from the frontend directory):
```bash
npm run dev
```

3. Open your browser and navigate to the URL shown in the frontend terminal output (typically http://localhost:5173)

## Usage

1. Get your Discord user token (see Discord documentation)
2. Find the channel ID you want to scrape (right-click channel > Copy ID)
3. Enter the token and channel ID in the web interface
4. Select a start date
5. Set the message limit (default: 1000)
6. Click "Scrape Messages"

## Security Notes

- Never share your Discord user token
- The token is only stored in memory and is never saved
- The application runs locally on your machine
- Downloaded message data should be handled securely

## Development

- Backend API documentation is available at http://localhost:8000/docs
- The frontend is built with React, TypeScript, and Material-UI
- The backend uses FastAPI and aiohttp for efficient async operations 