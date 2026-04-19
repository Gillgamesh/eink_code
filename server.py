import urllib.request
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURATION ---
PLAYLIST_URLS = [
    # 1. Your Lovelace Dashboard
    "http://hass-new.lan:10000/eink-test?viewport=2880x2160&zoom=2&crop_x=0&crop_y=112&crop_width=2880&crop_height=2160&theme=Graphite+E-ink+Light&lang=en&dithering=&dither_method=floyd-steinberg&palette=gray-4",
    
    # 2. Your Personal Website
    "http://hass-new.lan:10000/?viewport=2880x2160&zoom=2&lang=en&dithering=&dither_method=floyd-steinberg&palette=gray-4&url=https%3A%2F%2Fgilvirgill.com"
]

PORT = 8080
ROTATION_SECONDS = 30       # How long to show each rendered URL (e.g., 2 minutes)
CLIENT_REFRESH_SECONDS = 10  # How often the Avalue tablet blinks/refreshes
# ---------------------

# Global variables to hold the current state in RAM
current_image_data = b""
active_index = 0

def fetch_loop():
    """Background thread that pre-renders and caches the active image."""
    global current_image_data, active_index
    while True:
        target_url = PLAYLIST_URLS[active_index]
        print(f"\n[{time.strftime('%X')}] Rendering View {active_index + 1}/{len(PLAYLIST_URLS)} via HA Add-on...")
        
        try:
            req = urllib.request.Request(target_url)
            with urllib.request.urlopen(req) as response:
                current_image_data = response.read()
            print(f"[{time.strftime('%X')}] Success: Image cached in RAM. Waiting {ROTATION_SECONDS}s...")
        except Exception as e:
            print(f"[{time.strftime('%X')}] Error fetching from HA Add-on: {e}")
        
        # Wait before rotating to the next URL in the playlist
        time.sleep(ROTATION_SECONDS)
        active_index = (active_index + 1) % len(PLAYLIST_URLS)

class DashboardHandler(BaseHTTPRequestHandler):
    """Web server that instantly hands the cached image to the tablet."""
    
    # Suppress the spammy default HTTP logging so you only see rotation events
    def log_message(self, format, *args):
        pass 

    def do_GET(self):
        # Route 1: The tablet requests the root page
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            # The hard-refreshing HTML frame
            html = f"""<!DOCTYPE html>
            <html><head>
            <meta http-equiv="refresh" content="{CLIENT_REFRESH_SECONDS}">
            <style>body{{margin:0;display:flex;justify-content:center;align-items:center;height:100vh;overflow:hidden;background:#fff;}} img{{max-width:100%;max-height:100%;object-fit:contain;}}</style>
            </head><body><img src="/dashboard.png?t={time.time()}"></body></html>"""
            
            self.wfile.write(html.encode("utf-8"))

        # Route 2: The tablet requests the actual image
        elif self.path.startswith("/dashboard.png"):
            if current_image_data:
                self.send_response(200)
                self.send_header("Content-type", "image/png")
                self.end_headers()
                self.wfile.write(current_image_data)
            else:
                self.send_error(503, "Image not yet rendered. Please wait.")
        
        else:
            self.send_error(404)

if __name__ == "__main__":
    # 1. Start the background rendering loop
    fetch_thread = threading.Thread(target=fetch_loop, daemon=True)
    fetch_thread.start()

    # Wait a few seconds to ensure the first image renders before starting the web server
    time.sleep(3) 

    # 2. Start the web server
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"\n🚀 E-Ink Playlist Server running on port {PORT}...")
    server.serve_forever()
