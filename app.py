import os
import threading
import uuid
import time
from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
import yt_dlp

import shutil
import subprocess
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = shutil.which('ffmpeg')

app = Flask(__name__, static_folder='static', template_folder='templates')

def check_ffmpeg():
    return FFMPEG_PATH is not None

HAS_FFMPEG = check_ffmpeg()
if not HAS_FFMPEG:
    print("AVISO: FFMPEG não encontrado. Instale via 'pip install imageio-ffmpeg' ou manualmente no sistema.")
else:
    print(f"FFMPEG pronto em: {FFMPEG_PATH}")

# Configuration
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
STATIC_IMG_FOLDER = os.path.join(os.getcwd(), 'static', 'img')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_IMG_FOLDER, exist_ok=True)

# Annex the logo if it exists in the brain directory
LOGO_SRC = r'C:\Users\ed\.gemini\antigravity\brain\b33a73ce-bde0-4e7e-9a1e-851acafca3f6\reclip_logo_1776166343268.png'
LOGO_DEST = os.path.join(STATIC_IMG_FOLDER, 'logo.png')
if os.path.exists(LOGO_SRC) and not os.path.exists(LOGO_DEST):
    try:
        shutil.copy(LOGO_SRC, LOG_DEST)
    except Exception as e:
        print(f"Não foi possível anexar o logo: {e}")

# Job tracking
jobs = {}

class DownloadLogger:
    def debug(self, msg):
        pass
    def warning(self, msg):
        print(f"WARNING: {msg}")
    def error(self, msg):
        print(f"ERROR: {msg}")

def progress_hook(d, job_id):
    try:
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%').replace('%', '').strip()
            jobs[job_id]['progress'] = p
            jobs[job_id]['speed'] = d.get('_speed_str', '0KiB/s')
            jobs[job_id]['eta'] = d.get('_eta_str', '00:00')
            jobs[job_id]['status'] = 'Baixando'
        elif d['status'] == 'finished':
            jobs[job_id]['progress'] = '100'
            jobs[job_id]['status'] = 'Processando'
    except Exception as e:
        print(f"Erro no hook de progresso: {e}")

def run_download(url, job_id, options):
    try:
        jobs[job_id]['status'] = 'Iniciando'
        
        # If the format is just a video ID, we should append +bestaudio to it
        fmt = options.get('format', 'best')
        needs_merge = False
        if fmt != 'best' and not fmt.endswith('+bestaudio'):
            fmt = f"{fmt}+bestaudio/best"
            needs_merge = True

        if needs_merge and not HAS_FFMPEG:
             jobs[job_id]['status'] = 'Erro'
             jobs[job_id]['error'] = 'FFMPEG não instalado. Necessário para baixar em alta resolução (1080p+).'
             return

        ydl_opts = {
            'format': fmt,
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'%(title)s_{job_id}.%(ext)s'),
            'logger': DownloadLogger(),
            'progress_hooks': [lambda d: progress_hook(d, job_id)],
            'nocheckcertificate': True,
            'quiet': False,
            'merge_output_format': 'mp4', # Ensure we get a standard format
            'ffmpeg_location': FFMPEG_PATH
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Use the actual file path from the download result
            filename = ydl.prepare_filename(info)
            # If merged, the extension might have changed to .mp4 as requested
            if not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                if os.path.exists(base + '.mp4'):
                    filename = base + '.mp4'
                elif os.path.exists(base + '.mkv'):
                    filename = base + '.mkv'

            jobs[job_id]['filename'] = filename
            jobs[job_id]['status'] = 'Concluído'
            jobs[job_id]['title'] = info.get('title', 'Vídeo')
    except Exception as e:
        jobs[job_id]['status'] = 'Erro'
        jobs[job_id]['error'] = str(e)
        print(f"Erro no download: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def get_info():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            seen_resolutions = set()
            
            # Sort formats by resolution/quality
            all_formats = info.get('formats', [])
            
            for f in all_formats:
                res = f.get('resolution')
                ext = f.get('ext')
                vcodec = f.get('vcodec')
                
                # We want high quality video formats. 
                # On many sites (YT), these are video only (DASH)
                if vcodec != 'none':
                    res_key = f"{res}_{ext}"
                    if res_key not in seen_resolutions:
                        formats.append({
                            'id': f['format_id'],
                            'ext': ext,
                            'resolution': res or 'N/A',
                            'filesize': f.get('filesize_approx') or f.get('filesize'),
                            'note': f.get('format_note', '') + (' (Sem áudio nativo)' if f.get('acodec') == 'none' else ''),
                            'has_audio': f.get('acodec') != 'none'
                        })
                        seen_resolutions.add(res_key)
            
            return jsonify({
                'url': url,
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),
                'uploader': info.get('uploader'),
                'formats': formats[::-1][:12] # Top formats
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    fmt = data.get('format', 'best')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'status': 'Queued',
        'progress': '0',
        'speed': '0',
        'eta': '00:00'
    }
    
    thread = threading.Thread(target=run_download, args=(url, job_id, {'format': fmt}))
    thread.start()
    
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>')
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)

@app.route('/get_file/<job_id>')
def get_file(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Tarefa não encontrada ou o servidor foi reiniciado.'}), 404
        
    if job['status'] != 'Concluído':
        return jsonify({'error': 'O arquivo ainda não está pronto para download.'}), 400
    
    if not os.path.exists(job['filename']):
        return jsonify({'error': 'O arquivo não foi encontrado no servidor.'}), 404
    
    return send_file(job['filename'], as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8899, debug=True)
