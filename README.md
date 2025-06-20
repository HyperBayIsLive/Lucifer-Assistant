# 🔊 Lucifer - A Custom Voice Assistant for Windows 10

**Lucifer** is a powerful, offline voice assistant built specifically for Windows 10. It brings deep system-level automation, real-time voice command processing, and a fully customizable HTML-based clock utility—solving limitations of the native Windows clock.

> ⚠️ **Note:** This is a **prototype build** created for personal and experimental use. Some bugs or inconsistencies may occur.

---

## 🚀 Features

* 🎧 **Voice Activation:** Wake words include “Hey Lucifer”, “Hello Lucy”, etc.
* 🔐 **System Control:** Lock, sleep, restart, and shutdown via voice with confirmation.
* 🔊 **Volume Management:** Mute, set, or adjust volume precisely.
* 🔋 **Battery Monitoring:** Alerts when battery is below 30%.
* ⏰ **Timers & Alarms:** Natural language support for setting time-based reminders.
* 🌐 **Custom Clock App:** Built-in HTML interface bypasses Windows clock automation restrictions.
* 📂 **Application Launcher:** Launch any app by name, even with fallback prompts.
* ♻️ **Smart Session Handling:** Detects and terminates older running instances.
* 🖥️ **Auto-Start Capability:** Adds itself to system startup using the registry.
* ⚙️ **Audio via COM:** Uses low-level COM interfaces for precise volume control.
* ⌨️ **Global Hotkey Exit:** Press `Ctrl + Alt + Q` to exit immediately.

---

## 🛠️ Setup Instructions

1. **Install Dependencies**:

   ```bash
   pip install pyttsx3 speechrecognition pyaudio psutil keyboard comtypes python-dateutil
   ```
2. Ensure a working microphone and Brave browser (recommended) are installed.
3. Place `CLOCK APP.html` and optionally `WAKEBEEP.m4a` in the same directory.
4. Run the assistant:

   ```bash
   python lucifer.py
   ```

---

## 💡 Usage Tips

* Start by saying: “Hey Lucifer” or “Hello Lucy”
* Example queries:

  * “What’s the time?”
  * “Set timer for 20 minutes”
  * “Open Notepad”
  * “Shutdown computer”
* Say **“Activate”** to confirm critical actions like shutdown or restart.

---

## 📁 File Structure

```
Lucifer/
├── lucifer.py                # Main assistant script
├── CLOCK APP.html            # Custom clock/timer/alarm UI
├── WAKEBEEP.m4a              # Optional wake beep sound
└── voice_assistant.log       # Log file (auto-generated)
```

---

## 🐞 Known Issues & Bugs

* 🔄 Wake word detection may be affected by background noise.
* ❌ Some applications may not open if unlisted in Windows StartApps.
* 🕒 Timers and alarms require the clock app window to remain open.
* 🎙️ On some systems, audio device locking may produce glitches.

> Encounter an issue or have ideas to improve it? [Open an issue](https://github.com/your-repo/issues).

---

## 📄 License

This project is licensed under the **MIT License**. See the `LICENSE` file for full details.

---

## 👨‍💻 Author

Created by [Tarun Bali](https://www.linkedin.com/in/tarun-bali/)

---

## ⭐️ Support the Project

If you find **Lucifer** useful or interesting, consider giving it a ⭐️ to help it reach more developers!
