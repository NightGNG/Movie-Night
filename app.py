# ============================================================
# Астерал ГПТ — MOVIE NIGHT (For Render.com - Python 3.11)
# ============================================================

import os
import re
import time
import secrets
import json
import requests
import subprocess
import threading
import sys
from flask import Flask, render_template_string, request, send_file, abort, url_for, jsonify

# Fix for Python 3.14 - monkey patch audioop if missing
try:
    import audioop
except ImportError:
    import importlib
    import sys
    # Create a dummy audioop module
    class DummyAudioop:
        def __getattr__(self, name):
            def dummy(*args, **kwargs):
                return b''
            return dummy
    sys.modules['audioop'] = DummyAudioop()

import discord
from discord.ext import commands
from discord import app_commands

# ---------- CONFIG ----------
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "YOUR_DISCORD_BOT_TOKEN_HERE")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "4a7eecacdddd3be9331b6b7cc86faa61")
DISCORD_INVITE_URL = "https://discord.gg/mYBj8QEyeC"
DOWNLOAD_FOLDER = "movie_downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Global state
download_links: dict = {}

# ---------- FLASK APP ----------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# ---------- CORS HEADERS (Manual - no flask-cors needed) ----------
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ---------- HTML TEMPLATE ----------
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎬 Movie Night</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0a0015 0%, #1a0a2e 30%, #2d1b4e 70%, #0a0015 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #fff;
        }
        .container {
            max-width: 600px;
            padding: 40px;
            text-align: center;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 30px;
            border: 1px solid rgba(255, 215, 0, 0.1);
            backdrop-filter: blur(10px);
        }
        .logo {
            font-size: 72px;
            font-weight: 900;
            background: linear-gradient(135deg, #ff6b6b, #ffd93d, #6bcb77, #4d96ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .subtitle {
            font-size: 18px;
            color: #b8a5d4;
            margin: 10px 0 30px;
        }
        .discord-banner {
            background: linear-gradient(135deg, #5865F2, #404EED);
            border-radius: 15px;
            padding: 20px 30px;
            margin: 20px 0;
            box-shadow: 0 10px 40px rgba(88, 101, 242, 0.3);
        }
        .discord-banner a {
            color: #fff;
            text-decoration: none;
            font-size: 20px;
            font-weight: 600;
        }
        .status {
            color: #6bcb77;
            margin: 20px 0;
        }
        .footer {
            color: rgba(255, 255, 255, 0.2);
            font-size: 12px;
            margin-top: 30px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🎬 MOVIE NIGHT</div>
        <div class="subtitle">✦ The Cosmic Cinema ✦</div>
        
        <div class="discord-banner">
            <a href="{{ discord_invite }}" target="_blank">💬 Join our Discord Server</a>
        </div>
        
        <div class="status">✅ Bot is ONLINE and ready!</div>
        <p style="color: #b8a5d4;">Use <code style="background:rgba(255,255,255,0.1);padding:4px 8px;border-radius:4px;">/movie</code> in Discord</p>
        
        <div class="footer">⚡ Астерал ГПТ • Movie Night • Powered by Render</div>
    </div>
</body>
</html>
"""

# ---------- HELPER FUNCTIONS ----------
def tmdb_search(query):
    """Search TMDB"""
    url = f"https://api.themoviedb.org/3/search/movie"
    params = {'api_key': TMDB_API_KEY, 'query': query, 'language': 'en-US'}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('results', [])
    except:
        pass
    return []

def download_movie_file(title, year=None):
    """Download a movie using yt-dlp"""
    safe_title = re.sub(r'[^\w\s-]', '', title).strip()
    safe_title = re.sub(r'[-\s]+', '_', safe_title)
    filename = f"{safe_title}_{int(time.time())}.mp4"
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    sources = []
    if year:
        sources.append(f"ytsearch:{title} {year} full movie")
    sources.append(f"ytsearch:full movie {title}")
    sources.append(f"ytsearch:{title} movie full hd")
    
    ydl_opts = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", filepath,
        "--quiet",
        "--no-warnings",
        "--ignore-errors"
    ]
    
    for source in sources:
        try:
            print(f"Trying to download: {source}")
            cmd = ydl_opts + [source]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                print(f"✅ Downloaded: {filepath}")
                return filepath
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    return None

# ---------- FLASK ROUTES ----------
@app.route('/')
def index():
    return render_template_string(INDEX_TEMPLATE, discord_invite=DISCORD_INVITE_URL)

@app.route('/api/create_download', methods=['POST'])
def create_download():
    try:
        data = request.get_json()
        title = data.get('title')
        year = data.get('year')
        
        if not title:
            return jsonify({'error': 'Movie title required'}), 400
        
        print(f"📥 Downloading: {title} ({year})")
        filepath = download_movie_file(title, year)
        
        if not filepath:
            return jsonify({'error': f'Could not download "{title}"'}), 404
        
        link_id = secrets.token_urlsafe(16)
        expiry_time = time.time() + 60
        
        download_links[link_id] = {
            'filepath': filepath,
            'expiry': expiry_time,
            'filename': os.path.basename(filepath),
            'title': title,
            'year': year or '2024'
        }
        
        host_url = request.host_url.rstrip('/')
        download_url = f"{host_url}/download/{link_id}"
        
        return jsonify({
            'download_url': download_url,
            'expires_in': 60,
            'title': title,
            'year': year
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<link_id>')
def serve_download(link_id):
    if link_id not in download_links:
        return abort(404, "Link expired or invalid")
    
    data = download_links[link_id]
    if time.time() > data['expiry']:
        if data.get('filepath') and os.path.exists(data['filepath']):
            os.remove(data['filepath'])
        del download_links[link_id]
        return abort(410, "Download link expired (60 seconds)")
    
    filepath = data.get('filepath')
    filename = data['filename']
    del download_links[link_id]
    
    if filepath and os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename, mimetype='video/mp4')
    else:
        return abort(404, "File not found")

# ---------- DISCORD BOT ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} has connected to Discord!")
    print(f"🎬 MOVIE NIGHT BOT IS ALIVE!")
    try:
        await bot.tree.sync()
        print("✅ Commands synced!")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

@bot.tree.command(name="movie", description="🎬 Get a movie download link")
@app_commands.describe(query="Movie name")
async def movie_command(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    # Search for movie
    results = tmdb_search(query)
    
    if not results:
        await interaction.followup.send(f"❌ Could not find '{query}' on TMDB.")
        return
    
    movie = results[0]
    title = movie.get('title')
    year = movie.get('release_date', '')[:4]
    poster_path = movie.get('poster_path')
    
    await interaction.followup.send(f"🎬 **Movie Night** is downloading: **{title}** ({year})...\n*This may take a few minutes*")
    
    # Get host URL
    host_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5000')
    
    # Create download link
    try:
        response = requests.post(f"{host_url}/api/create_download", 
                                json={'title': title, 'year': year}, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            download_url = result.get('download_url')
            
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""
            
            embed = discord.Embed(
                title=f"🎬 MOVIE NIGHT",
                description=f"## ***{title}***\n**Thank you for using Movie Night Bot!** 🙏",
                color=discord.Color.gold()
            )
            
            if poster_url:
                embed.set_thumbnail(url=poster_url)
            
            embed.add_field(
                name="📥 DOWNLOAD LINK",
                value=f"[**Download {title}**]({download_url})\n*Auto-downloads when you click!*",
                inline=False
            )
            embed.add_field(name="📅 Year", value=year or "N/A", inline=True)
            embed.add_field(name="⏰ Expires", value="60 seconds", inline=True)
            embed.add_field(name="💬 Join Us", value="[Join Discord](https://discord.gg/mYBj8QEyeC)", inline=False)
            embed.set_footer(text="🎬 Movie Night • Click the link and it auto-downloads!")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ Could not download **{title}**. Try again later.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="night", description="🎬 MOVIE NIGHT - Get a movie download link")
@app_commands.describe(query="Movie name")
async def night_command(interaction: discord.Interaction, query: str):
    await movie_command(interaction, query)

@bot.tree.command(name="movies", description="🎬 Get a movie download link")
@app_commands.describe(query="Movie name")
async def movies_command(interaction: discord.Interaction, query: str):
    await movie_command(interaction, query)

# ---------- RUN ----------
def run_bot():
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"❌ Bot error: {e}")

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║  🎬 MOVIE NIGHT — DEPLOYED ON RENDER                       ║
    ║  🤖 Discord bot running in background                      ║
    ║  🌐 Web server running                                     ║
    ║  📥 Downloads movies using yt-dlp                         ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Start Discord bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("🤖 Discord bot starting in background...")
    
    # Run Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
