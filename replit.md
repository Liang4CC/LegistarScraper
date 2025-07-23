# replit.md

## Overview

This is a Flask-based web application that scrapes meeting data from the Cupertino city website (cupertino.legistar.com). The application allows users to download meeting agendas, minutes, and attachments by specifying a single date, date range, or providing a direct meeting URL. It features a modern web interface with progress tracking for scraping operations and a file browser for managing downloaded content.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application follows a traditional Flask web application architecture with a modular design:

- **Frontend**: Server-side rendered HTML templates using Jinja2, Bootstrap for UI components, and vanilla JavaScript for interactivity
- **Backend**: Flask framework handling HTTP requests, routing, and business logic
- **Scraping Module**: Separate Python module using requests and BeautifulSoup for web scraping functionality
- **Session Management**: Flask sessions for tracking user state and scraping progress
- **File System**: Local file storage for downloaded meeting documents

## Key Components

### 1. Flask Application (`app.py`)
- Main application entry point with route handlers
- Progress tracking system using global dictionaries
- ProgressTracker class for managing scraping operation status
- Session-based user interaction management

### 2. Scraper Module (`scraper_module.py`)
- ScraperInterface class for interacting with Cupertino's Legistar system
- Methods for fetching meeting data by date or URL
- HTML parsing and content extraction functionality
- File sanitization utilities

### 3. Web Interface Templates
- **Base Template**: Common layout with Bootstrap dark theme and navigation
- **Index**: Landing page with feature overview
- **Scrape**: Form interface for initiating scraping operations with date range support
- **Progress**: Real-time progress tracking display with ZIP download option
- **Browse**: File system browser for downloaded content with ZIP download functionality
- **View Markdown**: Document viewer with basic markdown rendering

### 4. Static Assets
- Custom CSS for styling enhancements
- JavaScript for client-side functionality (form validation, progress updates, utilities)

## Data Flow

1. **User Input**: Users specify either a single date, date range, or direct URL for meeting data
2. **Scraping Initiation**: Flask routes handle form submission and create background scraping tasks
3. **Progress Tracking**: Real-time updates sent to frontend via AJAX/polling mechanism
4. **Content Extraction**: Scraper module fetches and parses HTML from Legistar website
5. **File Storage**: Downloaded documents stored in local file system with organized folder structure
6. **Result Display**: Users can browse and download scraped content through web interface

## External Dependencies

### Python Libraries
- **Flask**: Web framework for HTTP handling and templating
- **requests**: HTTP client for web scraping
- **BeautifulSoup**: HTML parsing and content extraction
- **lxml**: XML/HTML parser backend for BeautifulSoup

### Frontend Dependencies
- **Bootstrap**: CSS framework with dark theme variant
- **Feather Icons**: Icon library for UI elements
- **Vanilla JavaScript**: Client-side functionality without additional frameworks

### Target Website
- **Cupertino Legistar**: Official city meeting portal (cupertino.legistar.com)
- Specific endpoints for calendar, department details, and meeting information

## Deployment Strategy

The application is designed for Replit deployment with the following characteristics:

- **Development Mode**: Flask debug mode enabled for development
- **Port Configuration**: Configured to run on port 5000 with host binding to 0.0.0.0
- **Environment Variables**: Uses environment variables for sensitive configuration (session secrets)
- **File Storage**: Relies on local file system storage (suitable for single-instance deployment)
- **No Database**: Uses in-memory storage and file system, no persistent database required

### Deployment Considerations
- The application uses global variables for progress tracking, which limits it to single-process deployment
- File storage is local, making it suitable for development but would need modification for production scaling
- Session management relies on Flask's default session handling
- No authentication system implemented - suitable for internal or trusted use cases

### Potential Enhancements for Production
- Add database support for progress tracking and user management
- Implement proper background job queue (Redis/Celery)
- Add user authentication and authorization
- Use cloud storage for downloaded files
- Add proper logging and monitoring