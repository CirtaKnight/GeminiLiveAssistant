"""
Gemini Live Assistant (Overlay & Audio)
---------------------------------------
Author: [Your Name/GitHub Username]
Date: 2024
Description:
    A real-time voice and screen assistant using Google Gemini Live API.
    Features a transparent overlay GIF and system tray integration.
    Toggled via Mouse Button 4 (X1).
"""

import sys
import os
import io
import asyncio
import base64
import threading
import traceback
import warnings

# GUI & Graphics
import tkinter as tk
from PIL import Image, ImageTk, ImageSequence, ImageDraw
import pystray
from pystray import MenuItem as item

# Audio & Input
import pyaudio
from pynput import mouse

# Screen Capture
import mss
import mss.tools

# AI & Config
from google import genai
from google.genai import types
from dotenv import load_dotenv

# --- PATH CONFIGURATION (Script & Exe compatible) ---
if getattr(sys, 'frozen', False):
    # Running as compiled .exe
    APP_PATH = os.path.dirname(sys.executable)
else:
    # Running as .py script
    APP_PATH = os.path.dirname(os.path.abspath(__file__))

# Assets paths
ASSETS_DIR = os.path.join(APP_PATH, "assets")
GIF_PATH = os.path.join(ASSETS_DIR, "loading.gif")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
ENV_PATH = os.path.join(APP_PATH, ".env")

# Load environment variables
load_dotenv(dotenv_path=ENV_PATH)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- GLOBAL SETTINGS ---
# Audio
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# API
MODEL = "models/gemini-2.0-flash-exp"
API_KEY = os.getenv("GEMINI_API_KEY")

# UI
ICON_SIZE = 100
MARGIN = 30  # Distance from screen edge


# ==========================================
# 1. SYSTEM TRAY INTEGRATION
# ==========================================
def run_tray_icon():
    """Runs the system tray icon in a separate thread."""

    def quit_app(icon, item):
        """Callback to exit the application properly."""
        print("[System] Exiting application...")
        icon.stop()
        os._exit(0) # Force exit to kill daemon threads

    try:
        if os.path.exists(LOGO_PATH):
            image = Image.open(LOGO_PATH)
        else:
            raise FileNotFoundError
    except Exception:
        # Fallback: Create a green square icon if file missing
        image = Image.new('RGB', (64, 64), color=(0, 255, 0))
        d = ImageDraw.Draw(image)
        d.text((10, 10), "AI", fill=(0, 0, 0))

    menu = (item('Quit', quit_app),)
    icon = pystray.Icon("GeminiAssistant", image, "Gemini Assistant", menu)
    icon.run()


# ==========================================
# 2. OVERLAY MANAGER (Tkinter)
# ==========================================
class OverlayThread(threading.Thread):
    """
    Manages the transparent GIF overlay.
    Uses a separate thread to avoid blocking the asyncio loop.
    """
    def __init__(self, gif_path, icon_size):
        super().__init__()
        self.gif_path = gif_path
        self.icon_size = icon_size
        self.daemon = True # Thread dies when main program exits

        self.root = None
        self.label = None
        self.frames = []
        self.current_frame_idx = 0

        self.transparent_color = '#000000' # Black becomes transparent
        self.should_be_visible = True
        self.is_window_hidden = False

    def set_visibility(self, visible):
        """Toggles the visibility flag."""
        self.should_be_visible = visible

    def load_gif(self):
        """Loads and processes GIF frames for transparency."""
        try:
            if not os.path.exists(self.gif_path):
                print(f"[Warning] GIF not found at: {self.gif_path}")
                return []

            gif_source = Image.open(self.gif_path)
            processed_frames = []

            for frame in ImageSequence.Iterator(gif_source):
                frame = frame.convert("RGBA")
                # Resize
                frame = frame.resize((self.icon_size, self.icon_size), Image.Resampling.LANCZOS)

                # Apply black background for transparency key
                bg = Image.new("RGBA", frame.size, (0, 0, 0, 255))
                bg.paste(frame, (0, 0), frame)

                processed_frames.append(ImageTk.PhotoImage(bg))
            return processed_frames
        except Exception as e:
            print(f"[Error] Could not load GIF: {e}")
            return []

    def update_animation(self):
        """Main loop to update GIF frames and window visibility."""
        # Handle Show/Hide logic
        if self.should_be_visible and self.is_window_hidden:
            self.root.deiconify()
            self.is_window_hidden = False
        elif not self.should_be_visible and not self.is_window_hidden:
            self.root.withdraw()
            self.is_window_hidden = True

        # Update Frame
        if self.should_be_visible and self.frames:
            frame = self.frames[self.current_frame_idx]
            self.label.configure(image=frame)
            self.current_frame_idx = (self.current_frame_idx + 1) % len(self.frames)

        # Schedule next update (50ms = 20fps)
        self.root.after(50, self.update_animation)

    def run(self):
        """Initializes the Tkinter window."""
        self.root = tk.Tk()

        # Windows-specific attributes for transparency and overlay
        self.root.overrideredirect(True)      # Remove borders/title bar
        self.root.wm_attributes("-topmost", True) # Always on top
        self.root.wm_attributes("-disabled", True) # Click-through
        self.root.config(bg=self.transparent_color)
        self.root.wm_attributes("-transparentcolor", self.transparent_color)

        self.frames = self.load_gif()
        if not self.frames:
            print("No frames loaded for overlay.")
        else:
            self.label = tk.Label(self.root, bg=self.transparent_color, bd=0)
            self.label.pack()

            # Position logic (Bottom Right with margin)
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()

            x_pos = screen_width - self.icon_size - MARGIN
            y_pos = screen_height - self.icon_size - MARGIN

            self.root.geometry(f"+{x_pos}+{y_pos}")

            self.update_animation()
            self.root.mainloop()


# ==========================================
# 3. CORE LOGIC (Audio, Screen, AI)
# ==========================================
class GeminiLiveAssistant:
    def __init__(self, overlay):
        self.overlay = overlay
        self.audio_in_queue = asyncio.Queue()
        self.out_queue = asyncio.Queue(maxsize=5)
        self.session = None
        self.is_streaming = True

        # Initialize Audio
        self.pya = pyaudio.PyAudio()

        # Initialize Gemini Client
        self.client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=API_KEY,
        )
        self.config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                )
            ),
        )

    def _capture_screen(self):
        """Captures a single frame from the primary monitor."""
        with mss.mss() as sct:
            # Select monitor (Primary or Secondary)
            try:
                monitor = sct.monitors[1]
            except IndexError:
                monitor = sct.monitors[0]

            sct_img = sct.grab(monitor)

            # Convert raw bytes to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img.thumbnail([1024, 1024]) # Resize to optimize bandwidth

            # Convert to JPEG bytes
            image_io = io.BytesIO()
            img.save(image_io, format="jpeg", quality=80)
            image_io.seek(0)

            return {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(image_io.read()).decode()
            }

    async def screen_loop(self):
        """Continuously captures screen when streaming is active."""
        while True:
            if self.is_streaming:
                try:
                    frame = await asyncio.to_thread(self._capture_screen)
                    if frame:
                        await self.out_queue.put(frame)
                        await asyncio.sleep(1.0) # 1 FPS for screen analysis
                except Exception as e:
                    print(f"[Error] Screen capture: {e}")
                    await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(0.2)

    async def mic_loop(self):
        """Captures microphone audio and puts it in the queue."""
        mic_info = self.pya.get_default_input_device_info()
        audio_stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )

        kwargs = {"exception_on_overflow": False}

        while True:
            data = await asyncio.to_thread(audio_stream.read, CHUNK_SIZE, **kwargs)
            if self.is_streaming:
                await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def send_loop(self):
        """Sends collected data (Audio/Video) to Gemini."""
        while True:
            msg = await self.out_queue.get()
            try:
                await self.session.send(input=msg)
            except Exception:
                pass

    async def receive_loop(self):
        """Receives audio responses from Gemini."""
        while True:
            try:
                turn = self.session.receive()
                async for response in turn:
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                        continue
                    if text := response.text:
                        print(text, end="") # Optional: print text to console

                # Clear queue if stopped to avoid delayed speech
                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()
            except Exception:
                pass

    async def speaker_loop(self):
        """Plays received audio."""
        stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    def on_mouse_click(self, x, y, button, pressed):
        """Handles mouse click events for toggling the assistant."""
        if not pressed:
            return

        # TOGGLE BUTTON: Mouse 4 (X1)
        if button == mouse.Button.x1:
            self.is_streaming = not self.is_streaming
            self.overlay.set_visibility(self.is_streaming)

            status = "ONLINE (Listening) 🟢" if self.is_streaming else "PAUSED 🔴"
            print(f"\n[Status] {status}")

    async def run(self):
        """Main entry point for the Asyncio loop."""
        # Start Mouse Listener
        listener = mouse.Listener(on_click=self.on_mouse_click)
        listener.start()

        print("--- Gemini Live Assistant Started ---")
        print("Control: Toggle with [MOUSE BUTTON 4] (Side button)")
        print("Exit: Right-click the system tray icon")
        print("-------------------------------------")

        try:
            async with (
                self.client.aio.live.connect(model=MODEL, config=self.config) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                # Launch all async tasks
                tg.create_task(self.send_loop())
                tg.create_task(self.mic_loop())
                tg.create_task(self.screen_loop())
                tg.create_task(self.receive_loop())
                tg.create_task(self.speaker_loop())

                # Keep alive loop
                while True:
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            traceback.print_exception(EG)
        finally:
            listener.stop()
            if self.pya:
                self.pya.terminate()


# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: GEMINI_API_KEY not found in .env file.")
        print("Please create a .env file with your key.")
        # We don't exit here immediately to allow tray icon to show error if needed,
        # but logically we can't connect.
        os._exit(1)

    # 1. Start Overlay Thread
    overlay_thread = OverlayThread(gif_path=GIF_PATH, icon_size=ICON_SIZE)
    overlay_thread.start()

    # 2. Start System Tray Thread
    tray_thread = threading.Thread(target=run_tray_icon)
    tray_thread.start()

    # 3. Start Main Async Loop
    app = GeminiLiveAssistant(overlay=overlay_thread)
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        os._exit(0)