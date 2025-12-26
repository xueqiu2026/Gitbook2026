import os
import glob
import sys
import time
from pathlib import Path
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import subprocess
import threading
import json
from datetime import datetime

# Simple in-memory task store
# { task_id: { status: 'running'|'completed'|'failed', progress: ..., result: ... } }
tasks = {}

app = FastAPI()

# Setup templates
# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Setup Library Directory
LIBRARY_DIR = Path(__file__).parent / "library"
LIBRARY_DIR.mkdir(exist_ok=True)

def migrate_root_files():
    """Move .md files from root to library"""
    root_dir = Path(__file__).parent
    count = 0
    for f in glob.glob(str(root_dir / "*.md")):
        # Skip README.md and other specific files if needed, but user wants clean root
        if "README" in f or "CHANGELOG" in f:
             continue
             
        src = Path(f)
        dst = LIBRARY_DIR / src.name
        if not dst.exists():
            try:
                src.rename(dst)
                count += 1
            except Exception as e:
                print(f"Failed to move {src.name}: {e}")
    if count > 0:
        print(f"📦 Migrated {count} files to library/")

# Run migration on startup
migrate_root_files()

class DownloadRequest(BaseModel):
    url: str
    filename: str = ""
    strategy: str = "auto"
    use_selenium: bool = False
    filter_include: str = ""
    filter_exclude: str = ""

def run_download_task(task_id: str, req: DownloadRequest):
    """Background task to run the download process"""
    tasks[task_id]['status'] = 'running'
    tasks[task_id]['log'] = []
    
    # Construct command
    cmd = [sys.executable, "main.py", req.url]
    
    if req.filename:
        # Verify it results in a safe filename inside library
        safe_name = Path(req.filename).name
        output_path = LIBRARY_DIR / safe_name
        cmd.extend(["-o", str(output_path)])
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"download_{timestamp}.md"
        output_path = LIBRARY_DIR / filename
        cmd.extend(["-o", str(output_path)])
        
    if req.strategy != "auto":
        cmd.extend(["--strategy", req.strategy])
    
    if req.use_selenium:
        cmd.append("--use-selenium")

    # Pass filters (map include -> section-path)
    if req.filter_include:
        cmd.extend(["--section", req.filter_include])
        
    # Exclude not supported in main.py yet?
    # We need to add it to main.py args first.
    # For now, let's assume we will add --exclude support.
    if req.filter_exclude:
        cmd.extend(["--exclude", req.filter_exclude])
        
    # Run process
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding='utf-8',
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        # Stream output to log
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
                
            # Check for JSON-SINK message
            if line.startswith("JSON-SINK:"):
                try:
                    json_str = line[10:].strip()
                    data = json.loads(json_str)
                    # Update task progress data
                    if 'type' in data and data['type'] == 'progress':
                         tasks[task_id]['progress'] = data['data']
                    elif 'type' in data and data['type'] == 'log':
                         # Structured log?
                         pass
                except Exception as e:
                    print(f"Error parsing JSON sink: {e}")
            else:
                tasks[task_id]['log'].append(line)
            
        process.wait()
        
        if process.returncode == 0:
            tasks[task_id]['status'] = 'completed'
            # Try to migrate any stray files just in case
            try:
                migrate_root_files()
            except:
                pass
        else:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = f"Process exited with code {process.returncode}"
            
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)

@app.post("/api/download")
async def start_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    task_id = f"task_{int(time.time()*1000)}"
    tasks[task_id] = {
        "status": "pending",
        "request": req.dict(),
        "start_time": datetime.now().isoformat()
    }
    background_tasks.add_task(run_download_task, task_id, req)
    return {"task_id": task_id, "status": "pending"}

@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str):
    return tasks.get(task_id, {"status": "not_found"})

@app.get("/api/history")
async def get_history():
    """Get list of downloaded files with metadata from LIBRARY folder"""
    files = []
    # Scan library directory
    md_files = list(LIBRARY_DIR.glob("*.md"))
    print(f"DEBUG: Scanning {LIBRARY_DIR}, found {len(md_files)} .md files")
    
    for f in md_files:
        try:
            stat = f.stat()
            # Try to read first few lines for metadata
            content_preview = f.read_text(encoding='utf-8', errors='ignore')[:500]
            
            # Simple metadata extraction
            title = f.name
            source = "Unknown"
            
            # Heuristic: Find first H1
            for line in content_preview.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            
            # Heuristic: Find Source line
            import re
            match = re.search(r'\*\*Source:\*\* (https?://\S+)', content_preview)
            if match:
                source = match.group(1)

            files.append({
                "filename": f.name,
                "title": title,
                "source": source,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime
            })
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    # Sort files: recently modified first
    files.sort(key=lambda x: x['modified'], reverse=True)
    return {"files": files}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main reader page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/files")
async def list_files():
    """List all markdown files in the current directory"""
    files = glob.glob("*.md")
    # Sort files: recently modified first
    files.sort(key=os.path.getmtime, reverse=True)
    return {"files": files}

@app.get("/api/content/{filename}")
async def get_content(filename: str):
    """Get content of a markdown file from LIBRARY"""
    if ".." in filename or "/" in filename or "\\" in filename:
        return {"error": "Invalid filename"}
    
    file_path = LIBRARY_DIR / filename
    if not file_path.exists():
        return {"error": "File not found"}
        
    try:
        content = file_path.read_text(encoding='utf-8')
        return {"filename": filename, "content": content}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/download_pdf/{filename}")
async def download_pdf_endpoint(filename: str):
    """Convert a markdown file to PDF and return it"""
    try:
        from fastapi.responses import StreamingResponse
        import markdown
        from xhtml2pdf import pisa
        import io

        if ".." in filename or "/" in filename or "\\" in filename:
            return {"error": "Invalid filename"}
        
        file_path = LIBRARY_DIR / filename
        if not file_path.exists():
            return {"error": "File not found"}
            
        md_content = file_path.read_text(encoding='utf-8')
        
        # Convert MD to HTML
        html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
        
        # Add basic styling for PDF
        full_html = f"""
        <html>
        <head>
            <style>
                @page {{ size: A4; margin: 2cm; }}
                body {{ font-family: sans-serif; font-size: 10pt; line-height: 1.5; }}
                h1, h2, h3 {{ color: #333; }}
                code {{ background-color: #f0f0f0; padding: 2px; }}
                pre {{ background-color: #f5f5f5; padding: 10px; border: 1px solid #ddd; word-wrap: break-word; white-space: pre-wrap; }}
                img {{ max-width: 100%; height: auto; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 1em; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        # Generate PDF
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        
        if pisa_status.err:
            return {"error": "PDF generation failed"}
            
        pdf_buffer.seek(0)
        
        return StreamingResponse(
            pdf_buffer, 
            media_type="application/pdf", 
            headers={"Content-Disposition": f"attachment; filename={filename.replace('.md', '.pdf')}"}
        )

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 GitBook Local Viewer running at http://localhost:8000")
    print("Press Ctrl+C to stop\n")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
