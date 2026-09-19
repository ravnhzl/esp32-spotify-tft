import requests
import serial
import time
import base64
import hashlib
import secrets
import webbrowser
import threading
import json
import os
import re
from io import BytesIO
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs

from PIL import Image


CLIENT_ID = "YOURSPOTIFYCLIENTID"
REDIRECT_URI = "http://127.0.0.1:8888/callback"

SERIAL_PORT = "COM5"
BAUD_RATE = 115200

TOKEN_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "spotify_token.json"
)

SCOPE = (
    "user-read-currently-playing "
    "user-read-playback-state "
    "user-modify-playback-state"
)

authorization_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global authorization_code

        query = parse_qs(urlparse(self.path).query)

        if "code" in query:
            authorization_code = query["code"][0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()

            self.wfile.write(
                b"""
                <html>
                <body>
                <h1>Spotify authorization successful!</h1>
                <p>You can close this window.</p>
                </body>
                </html>
                """
            )
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def generate_pkce():
    verifier = secrets.token_urlsafe(64)

    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(
            verifier.encode("utf-8")
        ).digest()
    ).decode("utf-8").rstrip("=")

    return verifier, challenge


def save_token(token_data):
    with open(TOKEN_FILE, "w", encoding="utf-8") as file:
        json.dump(token_data, file, indent=4)


def load_token():
    if not os.path.exists(TOKEN_FILE):
        return None

    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def refresh_access_token(refresh_token):
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        },
        timeout=10
    )

    if response.status_code != 200:
        print("Refresh failed.")
        return None

    token_data = response.json()

    # Spotify doesn't always send a new refresh token.
    if "refresh_token" not in token_data:
        token_data["refresh_token"] = refresh_token

    save_token(token_data)

    return token_data


def authorize_spotify():
    global authorization_code

    authorization_code = None

    verifier, challenge = generate_pkce()

    server = HTTPServer(
        ("127.0.0.1", 8888),
        CallbackHandler
    )

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge_method": "S256",
        "code_challenge": challenge
    }

    auth_url = (
        "https://accounts.spotify.com/authorize?"
        + urlencode(params)
    )

    print("Opening Spotify login...")
    webbrowser.open(auth_url)

    print("Waiting for authorization...")

    while authorization_code is None:
        server.handle_request()

    server.server_close()

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier
        },
        timeout=10
    )

    response.raise_for_status()

    token_data = response.json()
    save_token(token_data)

    return token_data


def get_access_token():
    token = load_token()

    if token is None:
        print("No saved Spotify authorization.")
        token = authorize_spotify()
        return token["access_token"]

    access_token = token.get("access_token")

    if access_token:
        response = requests.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=5
        )

        if response.status_code != 401:
            print("Using saved Spotify authorization.")
            return access_token

    refresh_token = token.get("refresh_token")

    if refresh_token:
        refreshed = refresh_access_token(refresh_token)

        if refreshed:
            return refreshed["access_token"]

    print("Starting Spotify login again...")
    token = authorize_spotify()

    return token["access_token"]


def get_current_song(access_token):
    response = requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=5
    )

    if response.status_code == 204:
        return None

    if response.status_code == 401:
        return "TOKEN_EXPIRED"

    if response.status_code != 200:
        print("Spotify API error:", response.status_code)
        return None

    data = response.json()

    if not data.get("item"):
        return None

    track = data["item"]

    artists = track.get("artists", [])
    artist = ", ".join(a["name"] for a in artists)

    images = track.get("album", {}).get("images", [])
    artwork_url = images[0].get("url") if images else None

    device = data.get("device", {})

    return {
        "song": track.get("name", "Unknown Song"),
        "artist": artist,
        "album": track.get("album", {}).get(
            "name",
            "Unknown Album"
        ),
        "progress": data.get("progress_ms", 0),
        "duration": track.get("duration_ms", 0),
        "playing": data.get("is_playing", False),
        "artwork_url": artwork_url,
        "volume": device.get("volume_percent", 50)
    }


def get_lyrics(song, artist):
    print(f"Looking for lyrics: {song} - {artist}")

    try:
        response = requests.get(
            "https://lrclib.net/api/get",
            params={
                "track_name": song,
                "artist_name": artist
            },
            timeout=5
        )

        if response.status_code != 200:
            print("Lyrics not found.")
            return None

        data = response.json()
        synced = data.get("syncedLyrics")

        if synced:
            print("Synchronized lyrics found.")
            return synced

        print("No synchronized lyrics available.")
        return None

    except Exception as e:
        print("Lyrics error:", e)
        return None


def parse_lyrics(synced_lyrics):
    lines = []

    if not synced_lyrics:
        return lines

    pattern = re.compile(
        r"\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)"
    )

    for line in synced_lyrics.splitlines():
        match = pattern.match(line)

        if not match:
            continue

        minutes = int(match.group(1))
        seconds = float(match.group(2))
        timestamp = minutes * 60 + seconds
        text = match.group(3).strip()

        if not text:
            continue

        lines.append((timestamp, text))

    return lines


def get_current_lyric(lyrics, progress_ms):
    if not lyrics:
        return ""

    current_time = progress_ms / 1000.0
    current = ""

    for timestamp, text in lyrics:
        if timestamp <= current_time:
            current = text
        else:
            break

    return current


def download_artwork(artwork_url):
    if not artwork_url:
        return None

    try:
        response = requests.get(
            artwork_url,
            timeout=10
        )

        if response.status_code != 200:
            return None

        image = Image.open(
            BytesIO(response.content)
        ).convert("RGB")

        image = image.resize(
            (100, 100),
            Image.Resampling.LANCZOS
        )

        pixels = []

        for y in range(100):
            for x in range(100):
                r, g, b = image.getpixel((x, y))

                rgb565 = (
                    ((r & 0xF8) << 8)
                    | ((g & 0xFC) << 3)
                    | (b >> 3)
                )

                pixels.append(rgb565)

        return pixels

    except Exception as e:
        print("Artwork error:", e)
        return None


def send_song_to_esp32(esp32, song_data):
    if song_data is None:
        esp32.write(b"NOTHING\n")
        return

    song = song_data["song"].replace("|", "/")
    artist = song_data["artist"].replace("|", "/")
    album = song_data["album"].replace("|", "/")

    message = (
        f"SONG|{song}|{artist}|{album}|"
        f"{song_data['progress']}|"
        f"{song_data['duration']}|"
        f"{1 if song_data['playing'] else 0}|"
        f"{song_data['volume']}\n"
    )

    esp32.write(message.encode("utf-8"))


def send_lyric(esp32, lyric):
    lyric = (
        lyric
        .replace("|", "/")
        .replace("\n", " ")
        .strip()
    )

    esp32.write(
        f"LYRIC|{lyric}\n".encode("utf-8")
    )


def send_artwork(esp32, artwork):
    if artwork is None:
        esp32.write(b"NOART\n")
        return

    print("Sending album artwork...")

    esp32.write(b"ARTSTART\n")
    time.sleep(0.05)

    # Convert RGB565 pixels into raw bytes.
    data = bytearray(len(artwork) * 2)

    for i, pixel in enumerate(artwork):
        data[i * 2] = (pixel >> 8) & 0xFF
        data[i * 2 + 1] = pixel & 0xFF

    esp32.write(data)
    esp32.flush()

    esp32.write(b"ARTEND\n")

    print("Album artwork sent.")


def spotify_command(access_token, command):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        if command == "PLAY":
            response = requests.put(
                "https://api.spotify.com/v1/me/player/play",
                headers=headers,
                timeout=5
            )

        elif command == "PAUSE":
            response = requests.put(
                "https://api.spotify.com/v1/me/player/pause",
                headers=headers,
                timeout=5
            )

        elif command == "NEXT":
            response = requests.post(
                "https://api.spotify.com/v1/me/player/next",
                headers=headers,
                timeout=5
            )

        elif command == "PREVIOUS":
            response = requests.post(
                "https://api.spotify.com/v1/me/player/previous",
                headers=headers,
                timeout=5
            )

        else:
            return

        print(f"Spotify {command}:", response.status_code)

    except Exception as e:
        print(f"Spotify {command} error:", e)


def set_volume(access_token, volume):
    volume = max(0, min(100, volume))

    try:
        response = requests.put(
            "https://api.spotify.com/v1/me/player/volume",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            params={
                "volume_percent": volume
            },
            timeout=5
        )

        print(
            "Volume:",
            volume,
            "response:",
            response.status_code
        )

    except Exception as e:
        print("Volume error:", e)


def listen_for_esp32(esp32, access_token):
    print("Listening for ESP32...")

    while True:
        try:
            line = (
                esp32.readline()
                .decode("utf-8", errors="ignore")
                .strip()
            )

            if not line:
                continue

            print("ESP32:", line)

            if line == "NEXT":
                spotify_command(access_token, "NEXT")

            elif line == "PREVIOUS":
                spotify_command(access_token, "PREVIOUS")

            elif line == "PLAY":
                song = get_current_song(access_token)

                if (
                    song
                    and song != "TOKEN_EXPIRED"
                    and song["playing"]
                ):
                    spotify_command(access_token, "PAUSE")
                else:
                    spotify_command(access_token, "PLAY")

            elif line.startswith("VOLUME|"):
                try:
                    volume = int(line.split("|")[1])
                    set_volume(access_token, volume)
                except Exception:
                    pass

        except Exception as e:
            print("ESP32 listener error:", e)
            time.sleep(0.1)


def main():
    print("ESP32 Spotify Player")

    access_token = get_access_token()

    print("Connecting to ESP32...")

    try:
        esp32 = serial.Serial(
            SERIAL_PORT,
            BAUD_RATE,
            timeout=0.1
        )
    except Exception as e:
        print("Could not connect to ESP32.")
        print(e)
        return

    time.sleep(2)
    print("ESP32 connected!")

    threading.Thread(
        target=listen_for_esp32,
        args=(esp32, access_token),
        daemon=True
    ).start()

    last_track = None
    lyrics = []
    last_lyric = None

    while True:
        try:
            song_data = get_current_song(access_token)

            if song_data == "TOKEN_EXPIRED":
                token = load_token()

                if token and token.get("refresh_token"):
                    refreshed = refresh_access_token(
                        token["refresh_token"]
                    )

                    if refreshed:
                        access_token = refreshed["access_token"]

                continue

            if song_data is None:
                if last_track != "NOTHING":
                    print("Nothing currently playing.")

                    send_song_to_esp32(
                        esp32,
                        None
                    )

                    send_lyric(esp32, "")

                    last_track = "NOTHING"
                    lyrics = []
                    last_lyric = None

            else:
                track_id = (
                    song_data["song"]
                    + "|"
                    + song_data["artist"]
                )

                if track_id != last_track:
                    print()
                    print("-----------------------------")
                    print("SONG:", song_data["song"])
                    print("ARTIST:", song_data["artist"])
                    print("ALBUM:", song_data["album"])
                    print("VOLUME:", song_data["volume"])
                    print("PLAYING:", song_data["playing"])
                    print("-----------------------------")

                    send_song_to_esp32(
                        esp32,
                        song_data
                    )

                    synced = get_lyrics(
                        song_data["song"],
                        song_data["artist"]
                    )

                    lyrics = parse_lyrics(synced)
                    last_lyric = None

                    print(
                        f"Loaded {len(lyrics)} lyric lines."
                    )

                    current_lyric = get_current_lyric(
                        lyrics,
                        song_data["progress"]
                    )

                    if current_lyric:
                        print("LYRIC:", current_lyric)

                        send_lyric(
                            esp32,
                            current_lyric
                        )

                        last_lyric = current_lyric
                    else:
                        send_lyric(esp32, "")

                    artwork = download_artwork(
                        song_data["artwork_url"]
                    )

                    send_artwork(
                        esp32,
                        artwork
                    )

                    last_track = track_id

                else:
                    # Same song, just update progress and lyrics.
                    send_song_to_esp32(
                        esp32,
                        song_data
                    )

                    current_lyric = get_current_lyric(
                        lyrics,
                        song_data["progress"]
                    )

                    if current_lyric != last_lyric:
                        print("LYRIC:", current_lyric)

                        send_lyric(
                            esp32,
                            current_lyric
                        )

                        last_lyric = current_lyric

            time.sleep(1)

        except KeyboardInterrupt:
            print("\nStopping...")
            esp32.close()
            break

        except Exception as e:
            print("Main loop error:", e)
            time.sleep(2)


if __name__ == "__main__":
    main()
