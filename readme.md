# Gemini Live Assistant 🤖🎙️

A lightweight, real-time voice and screen assistant powered by Google's **Gemini 2.0 Flash (Live API)**.

This tool runs in the background, captures your screen and microphone when triggered, and provides low-latency audio responses. It features a non-intrusive transparent overlay and system tray integration.


## ✨ Features



* **Real-time Interaction:** Low-latency voice conversation with Gemini.
* **Screen Awareness:** The assistant "sees" your screen to provide context-aware help.
* **Toggle:** Controlled via **Mouse Button 4** (Side button) to ensure privacy.
* **Visual Feedback:** A transparent animated overlay (GIF) appears when the assistant is listening.
* **Background Operation:** Minimized to the System Tray to save screen space.


## 🛠️ Prerequisites



* Python 3.10+
* A Google Cloud Project with the Gemini API enabled.
* A valid [Gemini API Key](https://aistudio.google.com/).


## 📦 Installation & Setup


### 1. Clone the repository

```bash
git clone [https://github.com/your-username/gemini-live-assistant.git](https://github.com/your-username/gemini-live-assistant.git) \
cd gemini-live-assistant \
```


### 2. Install Dependencies

```bash
pip install -r requirements.txt 
```


### 3. Configure API Key



1. Rename the file .env.example to .env.
2. Open .env and paste your API key:
```toml
GEMINI_API_KEY=Your_actual_api_key_starts_with_AIza... 
```


### 4. Assets Structure

Ensure your project folder looks like this:

/gemini-live-assistant \
  ├── assets/ \
  │    ├── loading.gif   (Transparent background recommended) \
  │    └── logo.png      (System tray icon) \
  ├── main.py \
  ├── .env \
  └── ... \



## 🚀 Usage



1. Run the script: `python main.py`
2. The application starts in the system tray (look for the icon near your clock).
3. **Press Mouse Button 4** (Side Button) to toggle the assistant ON/OFF.
    * **ON:** Overlay appears, assistant listens & sees screen.
    * **OFF:** Overlay disappears, assistant pauses.
4. **To Quit:** Right-click the System Tray icon and select **Quit**.


## 📦 Build Executable (.exe)

To create a standalone Windows executable that launches on startup:



1. **Install PyInstaller:** 
```bash
pip install pyinstaller 
```

2. **Build the .exe:**
```bash
pyinstaller --noconsole --onefile --icon=assets/logo.png --name="GeminiAssistant" main.py \
```

3. **Deploy:**
    * Move dist/GeminiAssistant.exe to a permanent folder (e.g., Documents).
    * **Important:** Copy the assets/ folder and the .env file into that same folder alongside the .exe.
4. **Auto-Start on Windows:**
    * Create a shortcut of GeminiAssistant.exe.
    * Press Win + R, type shell:startup, and press Enter.
    * Move the shortcut into the opened folder.


## ⚙️ Customization

You can tweak settings in main.py (top section):



* ICON_SIZE: Adjust the overlay size.
* MARGIN: Change the distance from the screen edge.
* MODEL: Switch Gemini models.


## 📄 License

MIT License.