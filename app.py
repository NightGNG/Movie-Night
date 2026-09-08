# ============================================================
# Астерал ГПТ — MOVIE NIGHT WEB + DISCORD BOT
# Complete deployable application for Railway.app
# Web interface + Discord bot + Movie search + Direct downloads
# ============================================================

import os
import sys
import json
import re
import time
import uuid
import secrets
import hashlib
import asyncio
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from flask import Flask, render_template_string, request, jsonify, send_file, abort, redirect, url_for, session
from flask_cors import CORS
import aiohttp
import yt_dlp
import discord
from discord.ext import commands
from discord import app_commands
import nest_asyncio

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# ---------- CONFIG ----------
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "YOUR_DISCORD_BOT_TOKEN_HERE")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "4a7eecacdddd3be9331b6b7cc86faa61")
TMDB_READ_TOKEN = os.environ.get("TMDB_READ_TOKEN", "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI0YTdlZWNhY2RkZGQzYmU5MzMxYjZiN2NjODZmYWE2MSIsIm5iZiI6MTc4ODA1MDA4MC43MjEsInN1YiI6IjZhOTM3YWEwYjA0ZjBhM2JkZDRmNmRmMCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.ne0Vw1dXMcGi5SYh4puAR1cpLtglc6oPT3JmpbUFT6A")
DISCORD_INVITE_URL = "https://discord.gg/mYBj8QEyeC"

# File storage
DOWNLOAD_FOLDER = "movie_downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Global state
download_links: Dict[str, dict] = {}
movie_cache: Dict[str, dict] = {}
bot_instance = None

# ---------- FLASK WEB APP ----------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
CORS(app)

# ---------- HTML TEMPLATES ----------
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎬 Movie Night - The Cosmic Cinema</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0a0015 0%, #1a0a2e 30%, #2d1b4e 70%, #0a0015 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
            color: #fff;
        }
        .stars {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
            background: radial-gradient(2px 2px at 20px 30px, #eee, transparent),
                        radial-gradient(2px 2px at 40px 70px, rgba(255,255,255,0.8), transparent),
                        radial-gradient(2px 2px at 50px 160px, #ddd, transparent),
                        radial-gradient(2px 2px at 90px 40px, rgba(255,255,255,0.6), transparent),
                        radial-gradient(2px 2px at 130px 80px, #fff, transparent),
                        radial-gradient(2px 2px at 160px 30px, rgba(255,255,255,0.8), transparent);
            background-size: 200px 200px;
            background-repeat: repeat;
            opacity: 0.3;
            z-index: 0;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            position: relative;
            z-index: 1;
        }
        .header {
            text-align: center;
            padding: 40px 0;
            border-bottom: 2px solid rgba(255, 215, 0, 0.2);
            margin-bottom: 40px;
        }
        .logo {
            font-size: 64px;
            font-weight: 900;
            background: linear-gradient(135deg, #ff6b6b, #ffd93d, #6bcb77, #4d96ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-shadow: 0 0 60px rgba(255, 107, 107, 0.3);
            letter-spacing: 6px;
        }
        .subtitle {
            font-size: 20px;
            color: #b8a5d4;
            margin-top: 10px;
            letter-spacing: 4px;
        }
        .discord-banner {
            background: linear-gradient(135deg, #5865F2, #404EED);
            border-radius: 15px;
            padding: 20px 30px;
            margin: 20px auto;
            max-width: 500px;
            text-align: center;
            box-shadow: 0 10px 40px rgba(88, 101, 242, 0.3);
            transition: transform 0.3s ease;
        }
        .discord-banner:hover {
            transform: scale(1.02);
        }
        .discord-banner a {
            color: #fff;
            text-decoration: none;
            font-size: 20px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }
        .discord-banner a:hover {
            text-shadow: 0 0 20px rgba(255,255,255,0.3);
        }
        .search-section {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 30px;
            margin: 30px 0;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
        }
        .search-box {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            justify-content: center;
        }
        .search-box input {
            flex: 1;
            min-width: 250px;
            padding: 15px 25px;
            border-radius: 50px;
            border: 2px solid rgba(255, 215, 0, 0.3);
            background: rgba(0, 0, 0, 0.4);
            color: #fff;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        .search-box input:focus {
            outline: none;
            border-color: #ffd93d;
            box-shadow: 0 0 30px rgba(255, 215, 0, 0.1);
        }
        .search-box input::placeholder {
            color: #888;
        }
        .search-box button {
            padding: 15px 40px;
            border-radius: 50px;
            border: none;
            background: linear-gradient(135deg, #ffd93d, #f6a700);
            color: #1a0a2e;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .search-box button:hover {
            transform: scale(1.05);
            box-shadow: 0 0 40px rgba(255, 215, 0, 0.3);
        }
        .movies-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 25px;
            margin-top: 40px;
        }
        .movie-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            overflow: hidden;
            transition: all 0.4s ease;
            border: 1px solid rgba(255, 255, 255, 0.05);
            cursor: pointer;
        }
        .movie-card:hover {
            transform: translateY(-10px);
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
            border-color: rgba(255, 215, 0, 0.3);
        }
        .movie-poster {
            width: 100%;
            aspect-ratio: 2/3;
            background: linear-gradient(145deg, #2d1b4e, #1a0a2e);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 60px;
            background-size: cover;
            background-position: center;
        }
        .movie-info {
            padding: 15px;
        }
        .movie-title {
            font-size: 16px;
            font-weight: 600;
            color: #ffd93d;
            margin-bottom: 5px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .movie-year {
            font-size: 14px;
            color: #b8a5d4;
        }
        .movie-rating {
            font-size: 13px;
            color: #ffd93d;
            margin-top: 5px;
        }
        .loading {
            text-align: center;
            padding: 60px;
            font-size: 18px;
            color: #b8a5d4;
        }
        .loading::after {
            content: '...';
            animation: dots 1.5s steps(4, end) infinite;
        }
        @keyframes dots {
            0%, 20% { content: ''; }
            40% { content: '.'; }
            60% { content: '..'; }
            80%, 100% { content: '...'; }
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        .modal.active {
            display: flex;
        }
        .modal-content {
            background: linear-gradient(145deg, #1a0a2e, #2d1b4e);
            border-radius: 25px;
            max-width: 500px;
            width: 100%;
            padding: 40px;
            border: 1px solid rgba(255, 215, 0, 0.2);
            box-shadow: 0 30px 100px rgba(0, 0, 0, 0.8);
            position: relative;
            animation: modalIn 0.4s ease;
        }
        @keyframes modalIn {
            from { transform: scale(0.9); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        .modal-close {
            position: absolute;
            top: 15px;
            right: 20px;
            font-size: 30px;
            cursor: pointer;
            color: #888;
            transition: color 0.3s;
            background: none;
            border: none;
        }
        .modal-close:hover {
            color: #fff;
        }
        .modal-poster {
            width: 100%;
            aspect-ratio: 2/3;
            border-radius: 12px;
            margin-bottom: 20px;
            background-size: cover;
            background-position: center;
            background: linear-gradient(145deg, #2d1b4e, #1a0a2e);
        }
        .modal-title {
            font-size: 28px;
            font-weight: 700;
            color: #ffd93d;
            margin-bottom: 10px;
        }
        .modal-overview {
            color: #b8a5d4;
            line-height: 1.6;
            margin: 15px 0;
            font-size: 14px;
            max-height: 150px;
            overflow-y: auto;
        }
        .modal-download-btn {
            width: 100%;
            padding: 18px;
            border: none;
            border-radius: 12px;
            background: linear-gradient(135deg, #ffd93d, #f6a700);
            color: #1a0a2e;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 15px;
        }
        .modal-download-btn:hover {
            transform: scale(1.02);
            box-shadow: 0 0 40px rgba(255, 215, 0, 0.3);
        }
        .modal-download-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .footer {
            text-align: center;
            padding: 40px 0;
            margin-top: 40px;
            border-top: 2px solid rgba(255, 255, 255, 0.05);
            color: rgba(255, 255, 255, 0.2);
            font-size: 12px;
            letter-spacing: 2px;
        }
        @media (max-width: 600px) {
            .logo { font-size: 40px; }
            .search-box input { min-width: 100%; }
            .movies-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
            .modal-content { padding: 20px; }
        }
    </style>
</head>
<body>
    <div class="stars"></div>
    <div class="container">
        <div class="header">
            <div class="logo">🎬 MOVIE NIGHT</div>
            <div class="subtitle">✦ The Cosmic Cinema ✦</div>
            
            <div class="discord-banner">
                <a href="{{ discord_invite }}" target="_blank">
                    <span>💬</span> Join our Discord Server
                    <span style="font-size:14px; opacity:0.7;">→</span>
                </a>
            </div>
        </div>

        <div class="search-section">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="Search for a movie or TV show..." onkeypress="if(event.key==='Enter') searchMovies()">
                <button onclick="searchMovies()">🔍 Search</button>
            </div>
            <div style="margin-top: 15px; text-align: center; color: #666; font-size: 13px;">
                Try: Inception, The Matrix, Breaking Bad, or paste a Netflix/IMDb link
            </div>
        </div>

        <div id="results">
            <div class="loading">Search for movies to get started</div>
        </div>

        <div class="footer">
            ⚡ Астерал ГПТ • Movie Night • The Universe's Cinema • Deployed on Railway
        </div>
    </div>

    <!-- Movie Modal -->
    <div class="modal" id="movieModal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal()">✕</button>
            <div class="modal-poster" id="modalPoster"></div>
            <div class="modal-title" id="modalTitle"></div>
            <div style="color: #b8a5d4; margin-bottom: 10px;" id="modalYear"></div>
            <div class="modal-overview" id="modalOverview"></div>
            <div style="color: #ffd93d; margin: 10px 0;" id="modalRating"></div>
            <button class="modal-download-btn" id="downloadBtn" onclick="downloadMovie()">
                🎬 Download Movie
            </button>
            <div id="downloadStatus" style="text-align:center; margin-top:10px; color:#b8a5d4; font-size:14px;"></div>
        </div>
    </div>

    <script>
        let currentMovie = null;
        let searchTimeout = null;

        function searchMovies() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) return;

            document.getElementById('results').innerHTML = '<div class="loading">Searching the cosmos...</div>';

            fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query })
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('results').innerHTML = `<div style="text-align:center;color:#ff6b6b;padding:40px;">❌ ${data.error}</div>`;
                    return;
                }
                renderMovies(data.results);
            })
            .catch(err => {
                document.getElementById('results').innerHTML = `<div style="text-align:center;color:#ff6b6b;padding:40px;">❌ Error: ${err.message}</div>`;
            });
        }

        function renderMovies(movies) {
            if (!movies || movies.length === 0) {
                document.getElementById('results').innerHTML = '<div style="text-align:center;color:#b8a5d4;padding:40px;">No movies found. Try a different search.</div>';
                return;
            }

            let html = '<div class="movies-grid">';
            movies.forEach(movie => {
                const poster = movie.poster_path ? `https://image.tmdb.org/t/p/w500${movie.poster_path}` : '';
                const title = movie.title || movie.name || 'Unknown';
                const year = movie.release_date ? movie.release_date.substring(0,4) : (movie.first_air_date ? movie.first_air_date.substring(0,4) : 'N/A');
                const rating = movie.vote_average ? movie.vote_average.toFixed(1) : 'N/A';
                
                html += `
                    <div class="movie-card" onclick="openModal('${movie.id}', '${movie.media_type || 'movie'}')">
                        <div class="movie-poster" style="${poster ? `background-image: url('${poster}');` : ''}">
                            ${!poster ? '🎥' : ''}
                        </div>
                        <div class="movie-info">
                            <div class="movie-title">${title}</div>
                            <div class="movie-year">${year}</div>
                            <div class="movie-rating">⭐ ${rating}/10</div>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            document.getElementById('results').innerHTML = html;
        }

        function openModal(id, type) {
            currentMovie = { id, type };
            document.getElementById('movieModal').classList.add('active');
            document.getElementById('downloadBtn').disabled = true;
            document.getElementById('downloadBtn').textContent = '⏳ Loading...';
            document.getElementById('downloadStatus').textContent = '';

            fetch('/api/movie_details', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id, type: type })
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('downloadStatus').textContent = '❌ ' + data.error;
                    document.getElementById('downloadBtn').disabled = true;
                    return;
                }
                
                currentMovie.details = data;
                const poster = data.poster_path ? `https://image.tmdb.org/t/p/w500${data.poster_path}` : '';
                document.getElementById('modalPoster').style.backgroundImage = poster ? `url('${poster}')` : 'linear-gradient(145deg, #2d1b4e, #1a0a2e)';
                document.getElementById('modalTitle').textContent = data.title || data.name || 'Unknown';
                document.getElementById('modalYear').textContent = data.release_date ? data.release_date.substring(0,4) : (data.first_air_date ? data.first_air_date.substring(0,4) : 'N/A');
                document.getElementById('modalOverview').textContent = data.overview || 'No overview available.';
                document.getElementById('modalRating').textContent = `⭐ ${data.vote_average ? data.vote_average.toFixed(1) : 'N/A'}/10 • ${data.vote_count || 0} votes`;
                document.getElementById('downloadBtn').disabled = false;
                document.getElementById('downloadBtn').textContent = '🎬 Download Movie';
            })
            .catch(err => {
                document.getElementById('downloadStatus').textContent = '❌ Error loading details';
                document.getElementById('downloadBtn').disabled = true;
            });
        }

        function closeModal() {
            document.getElementById('movieModal').classList.remove('active');
            currentMovie = null;
        }

        function downloadMovie() {
            if (!currentMovie || !currentMovie.details) return;
            
            const btn = document.getElementById('downloadBtn');
            btn.disabled = true;
            btn.textContent = '⏳ Preparing download...';
            document.getElementById('downloadStatus').textContent = '🔍 Searching for the movie...';

            const title = currentMovie.details.title || currentMovie.details.name;
            const year = currentMovie.details.release_date ? currentMovie.details.release_date.substring(0,4) : (currentMovie.details.first_air_date ? currentMovie.details.first_air_date.substring(0,4) : '');

            fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: title, year: year })
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('downloadStatus').textContent = '❌ ' + data.error;
                    btn.disabled = false;
                    btn.textContent = '🎬 Try Again';
                    return;
                }
                
                document.getElementById('downloadStatus').textContent = '✅ Download ready! Click the link below:';
                document.getElementById('downloadStatus').innerHTML = `
                    <a href="${data.download_url}" target="_blank" style="color:#ffd93d;font-size:18px;font-weight:bold;text-decoration:underline;">
                        📥 Click here to download ${title}
                    </a>
                    <br><span style="font-size:12px;color:#888;">⚠️ Link expires in 60 seconds!</span>
                `;
                btn.textContent = '✅ Download Started';
                btn.disabled = true;
            })
            .catch(err => {
                document.getElementById('downloadStatus').textContent = '❌ Error: ' + err.message;
                btn.disabled = false;
                btn.textContent = '🎬 Try Again';
            });
        }

        // Close modal on outside click
        document.getElementById('movieModal').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });
    </script>
</body>
</html>
"""

# ---------- FLASK ROUTES ----------
@app.route('/')
def index():
    return render_template_string(INDEX_TEMPLATE, discord_invite=DISCORD_INVITE_URL)

@app.route('/api/search', methods=['POST'])
async def search_movies():
    """Search for movies/TV shows via TMDB"""
    data = request.get_json()
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Please enter a search query'}), 400
    
    # Check if it's a URL
    if query.startswith('http'):
        # Try to extract Netflix ID
        netflix_match = re.search(r'netflix\.com/(?:watch|title)/(\d+)', query)
        if netflix_match:
            netflix_id = netflix_match.group(1)
            # Search using the Netflix ID
            query = f"netflix {netflix_id}"
    
    # Search both movies and TV
    results = []
    
    # Search movies
    movie_results = await tmdb_search(query, 'movie')
    if movie_results:
        results.extend(movie_results[:5])
    
    # Search TV
    tv_results = await tmdb_search(query, 'tv')
    if tv_results:
        results.extend(tv_results[:5])
    
    # If no results, try a more general search
    if not results:
        general_results = await tmdb_search(query, 'multi')
        if general_results:
            results = general_results[:10]
    
    if not results:
        return jsonify({'error': 'No results found. Try a different search.'}), 404
    
    return jsonify({'results': results})

@app.route('/api/movie_details', methods=['POST'])
async def get_movie_details():
    """Get detailed movie/TV info"""
    data = request.get_json()
    movie_id = data.get('id')
    media_type = data.get('type', 'movie')
    
    if not movie_id:
        return jsonify({'error': 'Movie ID required'}), 400
    
    async with aiohttp.ClientSession() as session:
        url = f"https://api.themoviedb.org/3/{media_type}/{movie_id}"
        params = {
            'api_key': TMDB_API_KEY,
            'language': 'en-US',
            'append_to_response': 'videos,credits'
        }
        
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return jsonify(data)
            else:
                return jsonify({'error': 'Could not fetch movie details'}), 404

@app.route('/api/download', methods=['POST'])
async def download_movie():
    """Download a movie and return a direct download link"""
    data = request.get_json()
    title = data.get('title')
    year = data.get('year')
    
    if not title:
        return jsonify({'error': 'Movie title required'}), 400
    
    # Download the movie
    filepath = await download_movie_file(title, year)
    
    if not filepath:
        return jsonify({'error': f'Could not download "{title}". The content might not be available.'}), 404
    
    # Generate download link
    link_id = secrets.token_urlsafe(16)
    expiry_time = time.time() + 60
    
    download_links[link_id] = {
        'filepath': filepath,
        'expiry': expiry_time,
        'filename': os.path.basename(filepath)
    }
    
    # Get the actual host URL
    host_url = request.host_url.rstrip('/')
    download_url = f"{host_url}/download/{link_id}"
    
    return jsonify({
        'download_url': download_url,
        'expires_in': 60,
        'filename': os.path.basename(filepath)
    })

@app.route('/download/<link_id>')
def serve_download(link_id):
    """Serve the downloaded file"""
    if link_id not in download_links:
        return abort(404, "Link expired or invalid")
    
    link_data = download_links[link_id]
    
    # Check expiry
    if time.time() > link_data['expiry']:
        if os.path.exists(link_data['filepath']):
            os.remove(link_data['filepath'])
        del download_links[link_id]
        return abort(410, "Download link expired (60 seconds)")
    
    return send_file(
        link_data['filepath'],
        as_attachment=True,
        download_name=link_data['filename'],
        mimetype='video/mp4'
    )

# ---------- HELPER FUNCTIONS ----------
async def tmdb_search(query: str, media_type: str = 'movie'):
    """Search TMDB"""
    url = f"https://api.themoviedb.org/3/search/{media_type}"
    params = {
        'api_key': TMDB_API_KEY,
        'query': query,
        'language': 'en-US',
        'page': 1
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                results = data.get('results', [])
                # Add media type
                for result in results:
                    result['media_type'] = media_type
                return results
    return []

async def download_movie_file(title: str, year: Optional[str] = None) -> Optional[str]:
    """Download a movie using yt-dlp"""
    safe_title = re.sub(r'[^\w\s-]', '', title).strip()
    safe_title = re.sub(r'[-\s]+', '_', safe_title)
    filename = f"{safe_title}_{int(time.time())}.mp4"
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    sources = [
        f"ytsearch:full movie {title}",
        f"ytsearch:{title} movie full hd",
        f"ytsearch:{title} film complet",
    ]
    
    if year:
        sources.insert(0, f"ytsearch:{title} {year} full movie")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': filepath,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'extract_flat': False,
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls'],
            }
        }
    }
    
    for source in sources:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([source])
                
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    return filepath
        except Exception as e:
            print(f"[ERROR] Download failed for {source}: {e}")
            continue
    
    return None

# ---------- DISCORD BOT ----------
class MovieBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.tree = app_commands.CommandTree(self)
    
    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Discord commands synced")

bot = MovieBot()

@bot.tree.command(name="movie", description="🎬 Get a DIRECT MOVIE DOWNLOAD LINK (expires in 60 seconds)")
@app_commands.describe(query="Movie name, Netflix link, or IMDb link")
async def movie_command(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    # Search for the movie
    movie_data = None
    
    # Check if it's a URL
    if query.startswith('http'):
        netflix_match = re.search(r'netflix\.com/(?:watch|title)/(\d+)', query)
        if netflix_match:
            search_result = await tmdb_search(f"netflix {netflix_match.group(1)}", 'movie')
            if search_result:
                movie_data = search_result[0]
        else:
            imdb_match = re.search(r'imdb\.com/title/(tt\d+)', query)
            if imdb_match:
                async with aiohttp.ClientSession() as session:
                    url = f"https://api.themoviedb.org/3/find/{imdb_match.group(1)}"
                    params = {'api_key': TMDB_API_KEY, 'external_source': 'imdb_id'}
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('movie_results'):
                                movie_data = data['movie_results'][0]
    else:
        # Search by name
        movie_data = await tmdb_search(query, 'movie')
        if not movie_data:
            movie_data = await tmdb_search(query, 'tv')
        if movie_data:
            movie_data = movie_data[0]
    
    if not movie_data:
        await interaction.followup.send(f"❌ Could not find '{query}' on TMDB.")
        return
    
    title = movie_data.get('title') or movie_data.get('name')
    year = movie_data.get('release_date', '')[:4] or movie_data.get('first_air_date', '')[:4]
    poster_path = movie_data.get('poster_path')
    
    await interaction.followup.send(f"🎬 **Movie Night** is downloading: **{title}** ({year})...")
    
    # Download the movie
    filepath = await download_movie_file(title, year)
    
    if not filepath:
        await interaction.followup.send(f"❌ Could not download **{title}**. The content might not be available.")
        return
    
    # Generate download link
    link_id = secrets.token_urlsafe(16)
    expiry_time = time.time() + 60
    
    # Get the host URL
    host_url = os.environ.get("RAILWAY_STATIC_URL", "http://localhost:5000")
    if not host_url.startswith('http'):
        host_url = f"https://{host_url}"
    
    download_links[link_id] = {
        'filepath': filepath,
        'expiry': expiry_time,
        'filename': os.path.basename(filepath)
    }
    
    download_url = f"{host_url}/download/{link_id}"
    expiry_readable = datetime.fromtimestamp(expiry_time).strftime('%H:%M:%S')
    
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""
    
    embed = discord.Embed(
        title=f"🎬 **MOVIE NIGHT**",
        description=f"## ***{title}***\n✅ **Download is ready!**",
        color=discord.Color.gold()
    )
    
    if poster_url:
        embed.set_thumbnail(url=poster_url)
    
    embed.add_field(
        name="📥 **DIRECT DOWNLOAD LINK**",
        value=f"[**Click here to download {title}**]({download_url})",
        inline=False
    )
    embed.add_field(
        name="🔗 **Raw URL**",
        value=f"`{download_url}`",
        inline=False
    )
    embed.add_field(name="⏰ **Expires**", value=f"At **{expiry_readable}** (60 seconds)", inline=True)
    embed.add_field(name="📁 **File Size**", value=f"{os.path.getsize(filepath) / (1024*1024):.2f} MB", inline=True)
    embed.add_field(name="📅 **Year**", value=year or "N/A", inline=True)
    embed.add_field(name="💬 **Join Us**", value=f"[Join our Discord!]({DISCORD_INVITE_URL})", inline=False)
    embed.set_footer(text="🎬 Movie Night • The Cosmic Cinema • Brought to you by Астерал ГПТ")
    
    async def cleanup_after_expiry():
        await asyncio.sleep(61)
        if link_id in download_links:
            if os.path.exists(download_links[link_id]['filepath']):
                os.remove(download_links[link_id]['filepath'])
            del download_links[link_id]
    
    asyncio.create_task(cleanup_after_expiry())
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="night", description="🎬 MOVIE NIGHT - Get a DIRECT download link")
@app_commands.describe(query="Movie name or link")
async def night_command(interaction: discord.Interaction, query: str):
    await movie_command(interaction, query)

@bot.tree.command(name="movies", description="🎬 MOVIE NIGHT - Get a DIRECT download link")
@app_commands.describe(query="Movie name or link")
async def movies_command(interaction: discord.Interaction, query: str):
    await movie_command(interaction, query)

@bot.event
async def on_ready():
    print(f"✅ Discord bot {bot.user} is ready!")
    await bot.tree.sync()
    print("✅ Commands synced!")

# ---------- RUN BOTH WEB APP AND DISCORD BOT ----------
def run_discord_bot():
    """Run the Discord bot in a separate thread"""
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"❌ Discord bot error: {e}")

def run_flask_app():
    """Run the Flask web app"""
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ---------- MAIN ----------
if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║  🎬 MOVIE NIGHT — THE COSMIC CINEMA                         ║
    ║  🌐 Web Interface: http://localhost:5000                    ║
    ║  🤖 Discord Bot: Active                                     ║
    ║  📥 Direct Downloads with 60-second expiry                  ║
    ║  🔗 Join Discord: https://discord.gg/mYBj8QEyeC            ║
    ║  🚀 Deploy on Railway: railway.app                         ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Start Discord bot in a separate thread
    if DISCORD_BOT_TOKEN and DISCORD_BOT_TOKEN != "YOUR_DISCORD_BOT_TOKEN_HERE":
        discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
        discord_thread.start()
    else:
        print("⚠️ Discord bot token not set. Bot will not start.")
        print("   Set DISCORD_BOT_TOKEN environment variable.")
    
    # Run Flask app (this blocks)
    run_flask_app()