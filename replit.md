# Auto Poster - Social Media Automation Platform

## Overview
This is a social media auto-poster application that uses AI to generate and schedule posts across social media platforms. The application features a Flask backend with a PostgreSQL database and supports automated posting with AI-generated content.

## Tech Stack
- **Backend**: Flask (Python 3.11)
- **Database**: PostgreSQL (via Replit's managed database)
- **AI**: OpenAI API for content generation
- **Social Media**: Twitter/X API via Tweepy
- **Scheduling**: APScheduler & schedule libraries
- **Frontend**: HTML/CSS static files

## Project Structure
```
.
├── backend/
│   ├── database/
│   │   ├── models.py        # Database models and queries
│   │   └── __init__.py
│   ├── routes/
│   │   └── register.py
│   ├── scheduler/
│   │   ├── job_scheduler.py # Scheduling logic
│   │   └── __init__.py
│   ├── services/
│   │   ├── ai_generator.py  # AI content generation
│   │   ├── post_generator.py
│   │   └── x_api_service.py # Twitter/X API integration
│   └── utils/
│       └── logger.py
├── main.py                   # Flask application entry point
├── db.py                     # Database connection
├── config.py                 # Configuration management
├── schema.sql               # Database schema
├── index.html               # Frontend homepage
├── style.css                # Styles
└── requirements.txt         # Python dependencies

## Recent Changes (October 17, 2025)
1. **Database Migration**: Converted from MySQL to PostgreSQL
   - Updated `db.py` to use `psycopg2` instead of `mysql-connector-python`
   - Updated all database models to use PostgreSQL-compatible syntax
   - Replaced MySQL-specific functions (`NOW()` → `CURRENT_TIMESTAMP`, `CURDATE()` → `CURRENT_DATE`)
   - Changed cursor factory from `dictionary=True` to `psycopg2.extras.RealDictCursor`

2. **Complete Frontend Rebuild**:
   - Created modern admin dashboard with sidebar navigation
   - Implemented full CRUD interfaces for all resources (Niches, Posts, Schedules, Accounts)
   - Added interactive forms with validation
   - Built responsive data tables for viewing records
   - Integrated JavaScript app (`app.js`) with all backend API endpoints
   - Designed professional UI with dark theme and gradient accents

3. **API Endpoints Added**:
   - `GET/POST /api/niches` - Manage content niches
   - `GET/POST /api/posts` - Create and view posts
   - `GET /api/posts/scheduled` - View scheduled posts
   - `GET/POST /api/schedules` - Configure posting schedules
   - `GET/POST /api/accounts` - Manage platform accounts

4. **Flask Server Enhancement**: 
   - Added complete REST API for frontend integration
   - Configured static file serving for CSS and JavaScript
   - Added route to serve `index.html` at root
   - Implemented proper routing for all API endpoints

5. **Replit Environment Setup**:
   - Installed Python 3.11 and all required dependencies
   - Created PostgreSQL database schema with all necessary tables
   - Configured Flask workflow to run on port 5000
   - Set up deployment configuration for VM (always-on server)

6. **Environment Configuration**:
   - Created `.env.example` file with required API keys
   - Updated `.gitignore` for Python project best practices

## Database Schema
The application uses the following tables:
- **niches**: Content categories/topics
- **hashtags**: Associated hashtags for niches
- **platform_accounts**: Social media account credentials
- **posts**: Generated posts with scheduling info
- **schedule**: Posting schedule configuration per niche

## API Endpoints
- `GET /` - Homepage
- `GET /run-assign-posts` - Manually trigger post assignment to time slots
- `GET /run-due-posts` - Manually process due posts
- `GET /start-scheduler` - Start the background scheduler

## Required Environment Variables
```
OPENAI_URL=https://api.openai.com/v1
OPENAI_API_KEY=your_openai_api_key_here
X_API_KEY=your_x_api_key_here
X_API_SECRET=your_x_api_secret_here
X_ACCESS_TOKEN=your_x_access_token_here
X_ACCESS_SECRET=your_x_access_secret_here
```

Database variables are automatically provided by Replit:
- `DATABASE_URL`
- `PGHOST`
- `PGDATABASE`
- `PGUSER`
- `PGPASSWORD`

## How to Run
The Flask server runs automatically via the configured workflow:
```bash
python main.py
```

The server will start on `http://0.0.0.0:5000`

## Deployment
- **Deployment Type**: VM (always-on)
- **Command**: `python main.py`
- The application is configured for production deployment with Replit's managed infrastructure

## Features
1. **AI Content Generation**: Uses OpenAI to generate social media posts
2. **Automated Scheduling**: Posts are scheduled based on configurable time slots
3. **Multi-Platform Support**: Designed to support multiple social media platforms
4. **Approval Workflow**: Optional approval required before posting
5. **Background Scheduler**: Runs continuously to process and post content

## Notes
- The application was migrated from MySQL to PostgreSQL for Replit compatibility
- The scheduler runs in a background thread to keep Flask responsive
- Posts can be scheduled with or without manual approval based on niche settings
