# 🧐 Lucifer - Your Custom Voice Assistant for Windows 10

**Lucifer** is a feature-rich, fully offline voice assistant designed for Windows 10 systems. It integrates deep system automation, real-time voice command processing, and custom HTML-based utilities—especially a **custom clock/timer/alarm interface**, overcoming the limitations of Windows' built-in clock automation.

> ⚠️ **Note:** This is a **prototype build** intended for experimentation and personal use. Bugs and inconsistencies may exist.

---

### 🚀 Features

* 🎧 Voice-controlled with wake words: “Hey Lucifer”, “Hello Lucy”, etc.
* 🔐 System Controls:

  * Lock, sleep, restart, and shutdown with voice confirmation.
* 🔊 Audio Management:

  * Set specific volume, increase/decrease/mute.
* 💧 Battery Status Alerts:

  * Voice alerts for low battery (below 30%).
* ⏰ Advanced Time Features:

  * Real-time clock reading, date/day queries.
  * Set **alarms/timers** using natural language.
* 🗺️ Custom Clock App (HTML):

  * Bypasses system limitations for reliable timer/alarm display.
* 📂 App Launcher:

  * Open installed applications via voice (with fallback support).
* ♻️ Persistent Session Handling:

  * Kills older instances if new one is launched.
* 📆 Auto-Start on Boot (Registry Integration).
* 🎚️ Built-in COM handling for audio device control.
* ⛔️ Hotkey Exit Support (`Ctrl + Alt + Q`).

---

### 🛠️ Setup Instructions

1. **Dependencies** (Install via `pip`):

   ```bash
   pip install pyttsx3 speechrecognition pyaudio psutil keyboard comtypes python-dateutil
   ```
2. Ensure your microphone is functional and Brave browser is installed (or fallback to default browser).
3. Place your `CLOCK APP.html` and optional `WAKEBEEP.m4a` in the same directory.
4. Run the script:

   ```bash
   python lucifer.py
   ```

---

### 💡 Usage Tips

* Wake it up: say “Hey Lucifer” or “Hello Lucy”.
* Ask: “What’s the time?”, “Set timer for 15 minutes”, “Open Notepad”, “Shutdown computer”...
* Confirm actions by saying “Activate” when prompted.

---

### 📁 File Structure

```
Lucifer/
├── lucifer.py                # Main assistant script
├── CLOCK APP.html            # Custom clock/timer/alarm UI
├── WAKEBEEP.m4a              # Optional wake beep
└── voice_assistant.log       # Log file (auto-generated)
```

---

### ⚠️ Known Issues & Bugs

* ⚠️ Assistant may misinterpret wake words in noisy environments.
* ⚠️ Some apps may fail to launch if not registered in Windows StartApps.
* ⚠️ Clock app must remain open for timers/alarms to function properly.
* ⚠️ Audio device locking issues may occur with some drivers.

Please feel free to open issues if you encounter bugs or suggest improvements.

---

### 📄 License

This project is licensed under the **MIT License**. See `LICENSE` file for details.

---

### 🙋‍♂️ Author

Created by [Tarun Bali](https://www.linkedin.com/in/tarun-bali/)

---

### ⭐️ Give It a Star!

If you find this helpful, consider ⭐️ starring the repo to support future development!
