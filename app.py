import os
import threading
import time
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
import logging

# Import the scraper functionality
from scraper_module import ScraperInterface

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Global variables for tracking scraping progress
scraping_progress = {}
scraping_results = {}

class ProgressTracker:
    def __init__(self, task_id):
        self.task_id = task_id
        self.progress = 0
        self.status = "Starting..."
        self.error = None
        self.completed = False
        
    def update(self, progress, status):
        self.progress = progress
        self.status = status
        scraping_progress[self.task_id] = {
            'progress': self.progress,
            'status': self.status,
            'error': self.error,
            'completed': self.completed
        }
        
    def complete(self, result=None):
        self.completed = True
        self.progress = 100
        self.status = "Completed successfully"
        scraping_progress[self.task_id] = {
            'progress': self.progress,
            'status': self.status,
            'error': self.error,
            'completed': self.completed
        }
        if result:
            scraping_results[self.task_id] = result
            
    def error_occurred(self, error_msg):
        self.error = error_msg
        self.status = f"Error: {error_msg}"
        self.completed = True
        scraping_progress[self.task_id] = {
            'progress': self.progress,
            'status': self.status,
            'error': self.error,
            'completed': self.completed
        }

def background_scraper_task(task_id, scraper_params):
    """Background task to run the scraper"""
    tracker = ProgressTracker(task_id)
    
    try:
        tracker.update(10, "Initializing scraper...")
        scraper = ScraperInterface()
        
        if scraper_params['mode'] == 'date':
            date_mode = scraper_params.get('date_mode', 'single')
            
            if date_mode == 'single':
                tracker.update(20, f"Fetching meetings for date {scraper_params['date']}...")
                meetings = scraper.fetch_meetings_for_date(scraper_params['date'])
                
                if not meetings:
                    tracker.error_occurred(f"No meetings found for {scraper_params['date']}")
                    return
                    
                if scraper_params.get('meeting_index') is not None:
                    meeting_idx = scraper_params['meeting_index']
                    if meeting_idx >= len(meetings):
                        tracker.error_occurred(f"Meeting index {meeting_idx + 1} not found")
                        return
                        
                    date, time_text, url = meetings[meeting_idx]
                    tracker.update(40, f"Processing meeting on {date} at {time_text}...")
                    result = scraper.process_meeting(url, scraper_params['output_folder'], scraper_params)
                    tracker.complete(result)
                else:
                    # Return list of meetings for selection
                    tracker.complete({'meetings': meetings, 'mode': 'select_meeting'})
                    
            elif date_mode == 'range':
                tracker.update(20, f"Fetching meetings from {scraper_params['start_date']} to {scraper_params['end_date']}...")
                try:
                    meetings = scraper.fetch_meetings_for_date_range(scraper_params['start_date'], scraper_params['end_date'])
                    
                    if not meetings:
                        tracker.error_occurred(f"No meetings found between {scraper_params['start_date']} and {scraper_params['end_date']}")
                        return
                    
                    # Return list of meetings for selection
                    tracker.complete({'meetings': meetings, 'mode': 'select_meeting', 'date_range': True})
                except ValueError as e:
                    tracker.error_occurred(str(e))
                    return
                
        elif scraper_params['mode'] == 'url':
            tracker.update(30, "Processing meeting from URL...")
            result = scraper.process_meeting(scraper_params['url'], scraper_params['output_folder'], scraper_params)
            tracker.complete(result)
            
    except Exception as e:
        logging.error(f"Scraper task error: {str(e)}")
        tracker.error_occurred(str(e))

@app.route('/')
def index():
    """Main page with scraper options"""
    return render_template('index.html')

@app.route('/scrape', methods=['GET', 'POST'])
def scrape():
    """Scraping configuration and execution"""
    if request.method == 'POST':
        # Generate unique task ID
        task_id = f"task_{int(time.time())}"
        
        # Get form data
        mode = request.form.get('mode')
        output_folder = request.form.get('output_folder', 'OUT_MEETING_FOLDER')
        selection = request.form.get('selection', '').split() if request.form.get('selection') else None
        remove_output = 'remove_output' in request.form
        split_supplemental = 'split_supplemental' in request.form
        
        scraper_params = {
            'mode': mode,
            'output_folder': output_folder,
            'selection': selection,
            'remove_output': remove_output,
            'split_supplemental': split_supplemental,
            'verbose': True
        }
        
        if mode == 'date':
            date_mode = request.form.get('date_mode', 'single')
            scraper_params['date_mode'] = date_mode
            
            if date_mode == 'single':
                date = request.form.get('date')
                if not date:
                    flash('Please provide a date', 'error')
                    return redirect(url_for('scrape'))
                scraper_params['date'] = date
                
                # Check if meeting index is provided
                meeting_index = request.form.get('meeting_index')
                if meeting_index:
                    try:
                        scraper_params['meeting_index'] = int(meeting_index) - 1
                    except ValueError:
                        flash('Invalid meeting index', 'error')
                        return redirect(url_for('scrape'))
            
            elif date_mode == 'range':
                start_date = request.form.get('start_date')
                end_date = request.form.get('end_date')
                if not start_date or not end_date:
                    flash('Please provide both start and end dates', 'error')
                    return redirect(url_for('scrape'))
                scraper_params['start_date'] = start_date
                scraper_params['end_date'] = end_date
                    
        elif mode == 'url':
            url = request.form.get('url')
            if not url:
                flash('Please provide a meeting URL', 'error')
                return redirect(url_for('scrape'))
            scraper_params['url'] = url
        else:
            flash('Invalid scraping mode', 'error')
            return redirect(url_for('scrape'))
        
        # Start background task
        thread = threading.Thread(target=background_scraper_task, args=(task_id, scraper_params))
        thread.daemon = True
        thread.start()
        
        # Store task ID in session
        session['current_task_id'] = task_id
        
        return redirect(url_for('progress'))
    
    return render_template('scrape.html')

@app.route('/progress')
def progress():
    """Progress tracking page"""
    task_id = session.get('current_task_id')
    if not task_id:
        flash('No active scraping task', 'warning')
        return redirect(url_for('index'))
    
    return render_template('progress.html', task_id=task_id)

@app.route('/api/progress/<task_id>')
def api_progress(task_id):
    """API endpoint for progress updates"""
    progress_data = scraping_progress.get(task_id, {
        'progress': 0,
        'status': 'Task not found',
        'error': 'Task ID not found',
        'completed': True
    })
    
    # Include results if completed and available
    if progress_data.get('completed') and task_id in scraping_results:
        progress_data['result'] = scraping_results[task_id]
    
    return jsonify(progress_data)

@app.route('/browse')
def browse():
    """File browser for downloaded documents"""
    folder_path = request.args.get('path', 'OUT_MEETING_FOLDER')
    folder = Path(folder_path)
    
    items = []
    error_msg = None
    
    try:
        if folder.exists() and folder.is_dir():
            for item in sorted(folder.iterdir()):
                if item.name.startswith('.'):
                    continue
                    
                item_info = {
                    'name': item.name,
                    'path': str(item),
                    'is_dir': item.is_dir(),
                    'size': item.stat().st_size if item.is_file() else 0,
                    'modified': datetime.fromtimestamp(item.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                }
                items.append(item_info)
        else:
            error_msg = f"Folder '{folder_path}' does not exist"
    except Exception as e:
        error_msg = f"Error accessing folder: {str(e)}"
    
    # Get parent directory for navigation
    parent_path = str(folder.parent) if folder.parent != folder else None
    
    return render_template('browse.html', 
                         items=items, 
                         current_path=folder_path,
                         parent_path=parent_path,
                         error=error_msg)

@app.route('/download')
def download():
    """Download file endpoint"""
    file_path = request.args.get('path')
    if not file_path:
        flash('No file specified', 'error')
        return redirect(url_for('browse'))
    
    file = Path(file_path)
    if not file.exists() or not file.is_file():
        flash('File not found', 'error')
        return redirect(url_for('browse'))
    
    try:
        return send_file(file, as_attachment=True)
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('browse'))

@app.route('/download_folder_zip')
def download_folder_zip():
    """Download folder as zip file"""
    folder_path = request.args.get('path', 'OUT_MEETING_FOLDER')
    folder = Path(folder_path)
    
    if not folder.exists() or not folder.is_dir():
        flash('Folder not found', 'error')
        return redirect(url_for('browse'))
    
    try:
        import zipfile
        import tempfile
        import os
        from datetime import datetime
        
        # Create a temporary zip file
        temp_dir = tempfile.mkdtemp()
        zip_filename = f"{folder.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = Path(temp_dir) / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder):
                for file in files:
                    file_path = Path(root) / file
                    # Create relative path for zip archive
                    arcname = file_path.relative_to(folder.parent)
                    zipf.write(file_path, arcname)
        
        def remove_temp_file():
            """Clean up temporary file after download"""
            try:
                os.unlink(zip_path)
                os.rmdir(temp_dir)
            except:
                pass
        
        # Schedule cleanup after response
        import atexit
        atexit.register(remove_temp_file)
        
        return send_file(zip_path, as_attachment=True, download_name=zip_filename)
        
    except Exception as e:
        flash(f'Error creating zip file: {str(e)}', 'error')
        return redirect(url_for('browse'))

@app.route('/view_markdown')
def view_markdown():
    """View markdown files in browser"""
    file_path = request.args.get('path')
    if not file_path:
        flash('No file specified', 'error')
        return redirect(url_for('browse'))
    
    file = Path(file_path)
    if not file.exists() or not file.is_file() or file.suffix.lower() != '.md':
        flash('Markdown file not found', 'error')
        return redirect(url_for('browse'))
    
    try:
        content = file.read_text(encoding='utf-8')
        return render_template('view_markdown.html', content=content, filename=file.name)
    except Exception as e:
        flash(f'Error reading file: {str(e)}', 'error')
        return redirect(url_for('browse'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
