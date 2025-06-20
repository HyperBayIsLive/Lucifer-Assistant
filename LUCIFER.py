import os
os.environ['COMTSYMS_CACHE'] = os.path.expanduser("~/.comtypes-cache")
import sys
import time
import json
import ctypes
import logging
import threading
import re
from datetime import datetime, timedelta
from pathlib import Path

import keyboard
import psutil
import pyttsx3
import speech_recognition as sr
from speech_recognition import Recognizer, AudioFile
import subprocess
import webbrowser
import urllib.parse
import winreg
import urllib.request
import tempfile

# Attempt to import dateutil for robust time parsing
try:
    from dateutil import parser as dateutil_parser
except ImportError:
    dateutil_parser = None

# Initialize logging early so that COM initialization errors can be logged properly
LOG_FILE = Path(os.path.dirname(os.path.abspath(__file__))) / "voice_assistant.log"
logging.basicConfig(
    filename=str(LOG_FILE),
    filemode='a',
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s"
)
logger = logging.getLogger(__name__)

# Define COM interfaces and constants for volume control
try:
    import comtypes
    from comtypes import GUID, COMMETHOD, HRESULT, IUnknown, CLSCTX_ALL

    # Add explicit COM cache handling
    from comtypes.client import _find_gen_dir
    comtypes.client.gen_dir = _find_gen_dir()
    os.makedirs(comtypes.client.gen_dir, exist_ok=True)
except ImportError:
    comtypes = None
except Exception as e:
    logger.exception("COM types initialization failed")
    comtypes = None
    import ctypes

import ctypes

def release_audio_device():
    try:
        ctypes.windll.winmm.waveOutReset(0)  # Reset the audio device
        logger.info("Audio device released forcefully.")
    except Exception as e:
        logger.warning("Failed to reset audio device: %s", e)

if comtypes:
    class IMMDevice(IUnknown):
        _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [
            COMMETHOD(
                [],
                HRESULT,
                "Activate",
                (['in'], GUID, "iid"),
                (['in'], ctypes.c_ulong, "dwClsCtx"),
                (['in'], ctypes.c_void_p, "pActivationParams"),
                (['out'], ctypes.POINTER(ctypes.c_void_p), "ppInterface")
            ),
        ]
    
    class IMMDeviceEnumerator(IUnknown):
        _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
        _methods_ = [
            COMMETHOD(
                [],
                HRESULT,
                "EnumAudioEndpoints",
                (['in'], ctypes.c_int, "dataFlow"),
                (['in'], ctypes.c_int, "dwStateMask"),
                (['out'], ctypes.POINTER(ctypes.POINTER(IUnknown)), "ppDevices")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetDefaultAudioEndpoint",
                (['in'], ctypes.c_int, "dataFlow"),
                (['in'], ctypes.c_int, "role"),
                (['out'], ctypes.POINTER(ctypes.POINTER(IMMDevice)), "ppEndpoint")
            ),
        ]
    
    class IAudioEndpointVolume(IUnknown):
        _iid_ = GUID("{5CDF2C82-841E-4546-9722-0CF74078229A}")
        _methods_ = [
            COMMETHOD(
                [],
                HRESULT,
                "RegisterControlChangeNotify",
                (['in'], ctypes.POINTER(IUnknown), "pNotify")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "UnregisterControlChangeNotify",
                (['in'], ctypes.POINTER(IUnknown), "pNotify")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetChannelCount",
                (['out'], ctypes.POINTER(ctypes.c_uint), "pnChannelCount")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "SetMasterVolumeLevel",
                (['in'], ctypes.c_float, "fLevelDB"),
                (['in'], ctypes.c_void_p, "pguidEventContext")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "SetMasterVolumeLevelScalar",
                (['in'], ctypes.c_float, "fLevel"),
                (['in'], ctypes.c_void_p, "pguidEventContext")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetMasterVolumeLevel",
                (['out'], ctypes.POINTER(ctypes.c_float), "pfLevelDB")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetMasterVolumeLevelScalar",
                (['out'], ctypes.POINTER(ctypes.c_float), "pfLevel")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "SetChannelVolumeLevel",
                (['in'], ctypes.c_uint, "nChannel"),
                (['in'], ctypes.c_float, "fLevelDB"),
                (['in'], ctypes.c_void_p, "pguidEventContext")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "SetChannelVolumeLevelScalar",
                (['in'], ctypes.c_uint, "nChannel"),
                (['in'], ctypes.c_float, "fLevel"),
                (['in'], ctypes.c_void_p, "pguidEventContext")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetChannelVolumeLevel",
                (['in'], ctypes.c_uint, "nChannel"),
                (['out'], ctypes.POINTER(ctypes.c_float), "pfLevelDB")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetChannelVolumeLevelScalar",
                (['in'], ctypes.c_uint, "nChannel"),
                (['out'], ctypes.POINTER(ctypes.c_float), "pfLevel")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "SetMute",
                (['in'], ctypes.c_int, "bMute"),
                (['in'], ctypes.c_void_p, "pguidEventContext")
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetMute",
                (['out'], ctypes.POINTER(ctypes.c_int), "pbMute")
            ),
        ]
    
    CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")

CONFIG_FILE = Path(os.path.expanduser("~")) / ".voice_assistant_config.json"

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.exception("Failed to load config")
            print("Failed to load config:", e)
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        logger.exception("Failed to save config")
        print("Failed to save config:", e)

if os.name == 'nt':
    tts_engine = pyttsx3.init('sapi5')
else:
    tts_engine = pyttsx3.init()
tts_engine.setProperty('volume', 1.0)
tts_lock = threading.Lock()
mic_lock = threading.Lock()  # Lock to prevent concurrent microphone access
is_muted = False
exit_event = threading.Event()  # Global event to signal program exit

# Global list to track clock app processes (used for alarms/timers)
clock_app_procs = []

def gracefully_close_window(pid):
    """Attempt to gracefully close the window associated with the given process id."""
    try:
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        WM_CLOSE = 0x0010
        found_hwnd = []

        def enum_windows_proc(hwnd, lParam):
            pid_buffer = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_buffer))
            if pid_buffer.value == lParam:
                found_hwnd.append(hwnd)
            return True

        EnumWindows = user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        EnumWindows(EnumWindowsProc(enum_windows_proc), pid)
        if found_hwnd:
            for hwnd in found_hwnd:
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            return True
        else:
            return False
    except Exception as e:
        logger.exception("Error in gracefully_close_window")
        return False

def close_clock_app():
    global clock_app_procs
    logger.info("Attempting to close clock app processes: %s", [p.pid for p in clock_app_procs])
    if clock_app_procs:
        for proc in clock_app_procs:
            try:
                logger.debug("Checking process PID %d: alive=%s", proc.pid, proc.poll() is None)
                if proc.poll() is None:
                    logger.info("Attempting to close PID %d", proc.pid)
                    if gracefully_close_window(proc.pid):
                        logger.info("Sent close signal to PID %d", proc.pid)
                        timeout = 5
                        start_time = time.time()
                        while time.time() - start_time < timeout:
                            if proc.poll() is not None:
                                logger.info("PID %d closed successfully", proc.pid)
                                break
                            time.sleep(0.2)
                        else:
                            logger.warning("Timeout waiting for PID %d to close", proc.pid)
                    else:
                        logger.warning("No window found for PID %d", proc.pid)
            except Exception as e:
                logger.exception("Error closing process PID %d", proc.pid)
        clock_app_procs = []
    else:
        logger.info("No clock app processes to close")

def vocalise(message):
    logger.info(f"Response: {message}")
    try:
        with tts_lock:
            logger.info("Acquired TTS lock")
            release_audio_device()  # Force release the audio device
            logger.info("Audio device released forcefully.")
            time.sleep(0.2)  # Small delay to ensure the device is released
            global tts_engine
            try:
                logger.info("Attempting to speak using TTS engine")
                tts_engine.say(message)
                tts_engine.runAndWait()
                logger.info("TTS engine spoke successfully")
            except Exception as e:
                logger.warning("TTS engine error, reinitializing...")
                tts_engine = pyttsx3.init('sapi5' if os.name == 'nt' else None)
                tts_engine.setProperty('volume', 1.0)
                tts_engine.say(message)
                tts_engine.runAndWait()
                logger.info("TTS engine reinitialized and spoke successfully")
    except Exception as e:
        logger.exception("TTS failure")
    print(f"[Voice]: {message}")

def find_brave_path():
    possible_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.join(os.path.expanduser("~"), r"AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe")
    ]
    return next((path for path in possible_paths if os.path.exists(path)), None)

def lock_computer():
    vocalise("Locking computer")
    try:
        if os.name == 'nt':
            ctypes.windll.user32.LockWorkStation()
        else:
            keyboard.press_and_release('win+l')
    except Exception as e:
        logger.exception("Error locking computer")
        print("Error locking computer:", e)

def sleep_computer():
    vocalise("Putting computer to sleep")
    try:
        if os.name == 'nt':
            ctypes.windll.powrprof.SetSuspendState(0, 0, 0)
            lock_computer()
        else:
            os.system('systemctl suspend')
    except Exception as e:
        logger.exception("Error putting computer to sleep")
        print("Error putting computer to sleep:", e)

def shutdown_computer():
    vocalise("Shutting down computer in 60 seconds")
    try:
        if os.name == 'nt':
            os.system("shutdown /s /t 60")
        else:
            os.system("shutdown -h +1")
    except Exception as e:
        logger.exception("Error shutting down computer")
        print("Error shutting down computer:", e)

def restart_computer():
    vocalise("Restarting computer in 60 seconds")
    try:
        if os.name == 'nt':
            os.system("shutdown /r /t 60")
        else:
            os.system("shutdown -r +1")
    except Exception as e:
        logger.exception("Error restarting computer")
        print("Error restarting computer:", e)

def confirm_action(recognizer, action, action_text):
    vocalise(f"{action_text} command received, awaiting confirmation.")
    try:
        with mic_lock:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=2.0)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
        confirmation = recognize_audio(recognizer, audio).upper().strip()
        if "ACTIVATE" in confirmation:
            vocalise(f"Confirmation received. {action_text} in 60 seconds")
            action()
            exit_event.set()
            return True
        else:
            vocalise(f"{action_text} cancelled.")
            return False
    except sr.WaitTimeoutError:
        vocalise(f"{action_text} confirmation timed out. {action_text} cancelled.")
        return False
    except sr.UnknownValueError:
        vocalise(f"Did not understand confirmation. {action_text} cancelled.")
        return False
    except Exception as e:
        logger.exception(f"Error during {action_text} confirmation")
        vocalise(f"{action_text} cancelled due to error.")
        return False

def battery_status():
    battery = psutil.sensors_battery()
    if battery is None:
        vocalise("Battery information is not available.")
        return
    message = f"Battery level is {battery.percent}%."
    if battery.power_plugged:
        message += " The laptop is plugged in."
    elif battery.percent <= 30:
        message += " Charge the laptop before discharge."
    vocalise(message)

last_battery_alert = 0
def check_battery_alert():
    global last_battery_alert
    battery = psutil.sensors_battery()
    if battery and not battery.power_plugged and battery.percent <= 30:
        if time.time() - last_battery_alert > 300:
            vocalise(f"Battery level is {battery.percent}%. Charge the laptop before discharge.")
            last_battery_alert = time.time()

def tell_current_time():
    current_time = datetime.now().strftime("%I:%M:%S %p")
    vocalise(f"The current time is {current_time}.")

def tell_only_day():
    day = datetime.now().strftime("%A")
    vocalise(f"Today is {day}.")

def tell_only_date():
    date_str = datetime.now().strftime("%B %d, %Y")
    vocalise(f"Today's date is {date_str}.")

def tell_day_and_date(day_first=True):
    day = datetime.now().strftime("%A")
    date_str = datetime.now().strftime("%B %d, %Y")
    if day_first:
        vocalise(f"Today is {day}, {date_str}.")
    else:
        vocalise(f"Today's date is {date_str} and the day is {day}.")

def set_volume(percent):
    try:
        import comtypes
        from comtypes import CLSCTX_INPROC_SERVER
        from ctypes import POINTER, cast
        from comtypes.client import CreateObject
    except Exception as e:
        logger.exception("COM components for volume control not available")
        vocalise("Volume control is not available on this system.")
        return
    try:
        comtypes.CoInitialize()
        mmde = comtypes.CoCreateInstance(
            CLSID_MMDeviceEnumerator,
            IMMDeviceEnumerator,
            CLSCTX_INPROC_SERVER
        )
        device = mmde.GetDefaultAudioEndpoint(0, 0)
        endpoint_ptr = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_INPROC_SERVER, None)
        endpoint = cast(endpoint_ptr, POINTER(IAudioEndpointVolume))
        percent = max(0, min(100, percent))
        logger.debug("Setting system volume to %d percent", percent)
        endpoint.SetMasterVolumeLevelScalar(percent / 100.0, None)
        logger.info("Volume set to %d percent", percent)
        vocalise(f"Volume set to {percent} percent.")
    except Exception as e:
        logger.exception("Error setting system volume")
        vocalise("Failed to set volume.")
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass

def get_volume():
    try:
        import comtypes
        from comtypes import CLSCTX_INPROC_SERVER
        from ctypes import POINTER, cast
        from comtypes.client import CreateObject
    except Exception as e:
        logger.exception("COM components for volume control not available")
        return None
    try:
        comtypes.CoInitialize()
        mmde = comtypes.CoCreateInstance(
            CLSID_MMDeviceEnumerator,
            IMMDeviceEnumerator,
            CLSCTX_INPROC_SERVER
        )
        device = mmde.GetDefaultAudioEndpoint(0, 0)
        endpoint_ptr = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_INPROC_SERVER, None)
        endpoint = cast(endpoint_ptr, POINTER(IAudioEndpointVolume))
        vol_scalar = endpoint.GetMasterVolumeLevelScalar()
        vol_percentage = round(vol_scalar * 100)
        logger.info("Retrieved system volume: %d percent", vol_percentage)
        return vol_percentage
    except Exception as e:
        logger.exception("Error getting system volume")
        return None
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass

def volume_up():
    if os.name != 'nt':
        vocalise("Volume control not supported on this OS.")
        return
    try:
        curr = get_volume()
        if curr is None:
            vocalise("Failed to retrieve volume.")
            return
        new_volume = min(100, curr + 10)
        set_volume(new_volume)
    except Exception as e:
        logger.exception("Error increasing volume")
        vocalise("Failed to increase volume.")

def volume_down():
    if os.name != 'nt':
        vocalise("Volume control not supported on this OS.")
        return
    try:
        curr = get_volume()
        if curr is None:
            vocalise("Failed to retrieve volume.")
            return
        new_volume = max(0, curr - 10)
        set_volume(new_volume)
    except Exception as e:
        logger.exception("Error decreasing volume")
        vocalise("Failed to decrease volume.")

def toggle_mute_volume():
    if os.name != 'nt':
        vocalise("Volume control not supported on this OS.")
        return
    try:
        import comtypes
        from comtypes import CLSCTX_INPROC_SERVER
        from ctypes import POINTER, cast
        from comtypes.client import CreateObject
        comtypes.CoInitialize()
        mmde = comtypes.CoCreateInstance(
            CLSID_MMDeviceEnumerator,
            IMMDeviceEnumerator,
            CLSCTX_INPROC_SERVER
        )
        device = mmde.GetDefaultAudioEndpoint(0, 0)
        endpoint_ptr = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_INPROC_SERVER, None)
        endpoint = cast(endpoint_ptr, POINTER(IAudioEndpointVolume))
        current_mute = endpoint.GetMute()
        new_mute = 0 if current_mute == 1 else 1
        endpoint.SetMute(new_mute, None)
        logger.info("Toggled mute from %d to %d", current_mute, new_mute)
        global is_muted
        is_muted = bool(new_mute)
        if new_mute:
            vocalise("Volume muted.")
        else:
            vocalise("Volume unmuted.")
    except Exception as e:
        logger.exception("Error toggling mute")
        vocalise("Failed to toggle mute.")
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass

# Updated exit_phrases: Removed commands that turn off speech recognition
exit_phrases = {
    "LUCIFER EXIT": "Exiting program",
    "LUCY EXIT": "Exiting program",
    "EXIT PROGRAM": "Exiting program",
    "GOOD BYE LUCIFER": "Goodbye sir",
    "GOOD BYE LUCY": "Goodbye sir",
    "BYE BYE LUCIFER": "Goodbye sir",
    "BYE LUCIFER": "Goodbye sir",
    "BYE LUCY": "Goodbye sir",
    "EXIT THE PROGRAM": "Exiting program",
    "GOODBYE LUCIFER": "Goodbye sir"
}

custom_commands = {
    "HELLO": "Hello sir, how can I assist you?",
    "HOW ARE YOU": "I am fully operational, thank you sir.",
    "HOW R U": "I am fully operational, thank you sir.",
    "HOW R YOU": "I am fully operational, thank you sir.",
    "WHAT CAN YOU DO": ("I can lock your computer, put it to sleep, shutdown after confirmation, "
                        "restart upon confirmation, tell you the time, provide battery status, control volume, "
                        "and manage alarms and timers via the clock app."),
    "ARE YOU GAY": "AWWW HELL NAWWW I AM STRAIGHT AS FUCK..... BRUH",
    "R U GAY": "AWWW HELL NAWWW I AM STRAIGHT AS FUCK..... BRUH",
    "ARE U GAY": "AWWW HELL NAWWW I AM STRAIGHT AS FUCK..... BRUH",
    "R YOU GAY": "AWWW HELL NAWWW I AM STRAIGHT AS FUCK..... BRUH"
}

shutdown_phrases = [
    "SHUTDOWN COMPUTER", "SHUTDOWN THE COMPUTER", "SHUTDOWN LAPTOP", "SHUTDOWN THE LAPTOP", "SHUTDOWN THE PC",
    "SHUT DOWN COMPUTER", "SHUT DOWN THE COMPUTER", "SHUT DOWN LAPTOP", "SHUT DOWN THE LAPTOP", "SHUT DOWN THE PC",
    "POWER OFF COMPUTER", "POWER OFF THE COMPUTER", "POWER OFF LAPTOP", "POWER OFF THE LAPTOP", "POWER OFF THE PC",
    "TURN OFF COMPUTER", "TURN OFF THE COMPUTER", "TURN OFF LAPTOP", "TURN OFF THE LAPTOP",
    "TURN OFF THE PC", "TURN OFF THE SYSTEM", "TURN OFF PC"
]

restart_phrases = [
    "RESTART COMPUTER", "RESTART LAPTOP", "RESTART PC",
    "RESTART THE COMPUTER", "RESTART THE LAPTOP", "RESTART THE PC"
]

sleep_phrases = [
    "SLEEP COMPUTER", "SLEEP LAPTOP", "SLEEP PC",
    "SLEEP THE COMPUTER", "SLEEP THE LAPTOP", "SLEEP THE PC",
    "PUT COMPUTER TO SLEEP", "PUT THE LAPTOP TO SLEEP", "PUT THE PC TO SLEEP", "SLEEP MODE"
]

lock_phrases = [
    "LOCK COMPUTER", "LOCK LAPTOP", "LOCK PC",
    "LOCK THE COMPUTER", "LOCK THE LAPTOP", "LOCK THE PC", "INITIATE LOCK", "SYSTEM LOCK"
]

wake_words = ["HELLO LUCIFER", "HEY LUCIFER", "HEY LUCY", "LUCIFER", "LUCY"]

def check_for_wake(text):
    # Use regex to ensure the wake word is at the beginning.
    pattern = r'^(?:' + '|'.join(re.escape(word) for word in wake_words) + r')\b'
    match = re.match(pattern, text, flags=re.IGNORECASE)
    if match:
        command_candidate = text[match.end():].strip()
        return True, command_candidate
    return False, ""

# New functionality: Properly close apps using PowerShell remains unchanged
def close_app_by_name(app_name):
    # Use PowerShell to close the app
    subprocess.run(["powershell", "-Command", f"Stop-Process -Name {app_name} -Force"], shell=True)
    # Example usage (do not call here): close_app_by_name("notepad")

app_list_cache = None

def load_app_list():
    global app_list_cache
    if os.name != 'nt':
        return {}
    try:
        result = subprocess.check_output(
            ["powershell", "-Command", "Get-StartApps | ConvertTo-Json"],
            stderr=subprocess.DEVNULL
        )
        apps = json.loads(result)
        if isinstance(apps, dict):
            apps = [apps]
        app_dict = {}
        for app in apps:
            name = app.get("Name", "").lower()
            appid = app.get("AppID", "")
            if name and appid:
                app_dict[name] = appid
        app_list_cache = app_dict
        return app_dict
    except Exception as e:
        logger.exception("Failed to load app list using Get-StartApps")
        return {}

def open_app(app_name, recognizer=None):
    if os.name != 'nt':
        vocalise("Open app functionality is not supported on this OS.")
        return
    global app_list_cache
    app_name = app_name.strip()
    app_name_lower = app_name.lower()
    if app_name_lower.startswith("open "):
        app_name_lower = app_name_lower[5:].strip()
    if app_name_lower.endswith(" again"):
        app_name_lower = app_name_lower[:-6].strip()
    if app_name_lower == "clock app":
        try:
            if not open_clock_app(mode="clock"):
                raise Exception("Clock app launch failed")
        except Exception as e:
            logger.exception("Failed to open clock app")
            vocalise("Failed to open clock app.")
        return
    if app_list_cache is None:
        load_app_list()
    appid = app_list_cache.get(app_name_lower) if app_list_cache else None
    if not appid:
        vocalise(f"App {app_name} not found. Please say the app name again.")
        if recognizer:
            try:
                with mic_lock:
                    with sr.Microphone() as source:
                        audio = recognizer.listen(source, timeout=6, phrase_time_limit=6)
                extra_app = recognize_audio(recognizer, audio).upper().strip()
                if extra_app.startswith("OPEN "):
                    extra_app = extra_app[5:].strip()
                app_name_lower = extra_app.lower()
                if app_list_cache is None:
                    load_app_list()
                appid = app_list_cache.get(app_name_lower) if app_list_cache else None
                if not appid:
                    vocalise(f"App {extra_app} not found.")
                    return
            except Exception as e:
                logger.exception("Additional app input error")
                vocalise("Failed to receive valid app input.")
                return
    try:
        command = f'shell:AppsFolder\\{appid}'
        subprocess.Popen(["powershell", "-Command", f"Start-Process '{command}'"])
        vocalise(f"Opening {app_name}.")
    except Exception as e:
        logger.exception(f"Failed to open app {app_name}")
        vocalise(f"Failed to open {app_name}.")

def parse_duration(text):
    pattern = r'(\d+)\s*(HOUR|HOURS|MINUTE|MINUTES|SECOND|SECONDS)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if not matches:
        return None
    total_seconds = 0
    for value, unit in matches:
        value = int(value)
        unit = unit.lower()
        if "hour" in unit:
            total_seconds += value * 3600
        elif "minute" in unit:
            total_seconds += value * 60
        elif "second" in unit:
            total_seconds += value
    if total_seconds <= 0:
        return None
    return timedelta(seconds=total_seconds)

def parse_time(text):
    # First try using dateutil_parser if available for robust parsing
    if dateutil_parser is not None:
        try:
            dt = dateutil_parser.parse(text, fuzzy=True)
            now = datetime.now()
            # If the parsed time is in the past, assume it's for the next day
            if dt < now:
                dt += timedelta(days=1)
            return dt, dt.strftime("%I:%M %p")
        except Exception as e:
            logger.exception("dateutil_parser failed in parse_time")
    # Fallback to regex-based parsing with additional validation
    pattern = r'\b(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?\b'
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None, None
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    # Validate the extracted time components
    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        return None, None
    ampm = match.group(3)
    now = datetime.now()
    if ampm:
        ampm = ampm.upper()
        if ampm == "PM" and hour != 12:
            hour += 12
        if ampm == "AM" and hour == 12:
            hour = 0
        ring_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if ring_time <= now:
            ring_time += timedelta(days=1)
    else:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate_12 = candidate + timedelta(hours=12)
            if candidate_12 > now:
                candidate = candidate_12
            else:
                candidate = candidate + timedelta(days=1)
        ring_time = candidate
    return ring_time, ring_time.strftime("%I:%M %p")

def timer_thread(ring_time, mode, duration_value, time_str, duration_description):
    try:
        success = open_clock_app(
            mode=mode.lower(),
            duration=int(duration_value.total_seconds()) if isinstance(duration_value, timedelta) else duration_value,
            ring_time=ring_time.strftime("%I:%M:%S %p"),
            keep_open=True
        )
        if success:
            if duration_description:
                vocalise(f"{mode.capitalize()} set for {duration_description} and it will ring at {time_str}.")
            else:
                vocalise(f"{mode.capitalize()} set to ring at {time_str}.")
        return
    except Exception as e:
        logger.exception("Timer thread error")
        vocalise("Failed to set " + mode.lower())

def set_timer(command, recognizer):
    now = datetime.now()
    duration_val = parse_duration(command)
    if duration_val:
        ring_time = now + duration_val
        time_str = ring_time.strftime("%I:%M %p")
        try:
            threading.Thread(
                target=timer_thread,
                args=(ring_time, "TIMER", duration_val, time_str, str(duration_val)),
                daemon=True
            ).start()
        except Exception as e:
            logger.exception("Failed to start timer thread for TIMER")
            vocalise("Error setting timer.")
        return
    ring_time, time_str = parse_time(command)
    if ring_time:
        diff = ring_time - now
        duration_str = str(diff).split('.')[0]
        try:
            threading.Thread(
                target=timer_thread,
                args=(ring_time, "TIMER", diff, time_str, duration_str),
                daemon=True
            ).start()
        except Exception as e:
            logger.exception("Failed to start timer thread for TIMER (parse_time branch)")
            vocalise("Error setting timer.")
        return
    vocalise("Timer command not recognized. Please specify a duration or a time.")
    try:
        with mic_lock:
            with sr.Microphone() as source:
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=6)
        extra_command = recognize_audio(recognizer, audio).upper().strip()
        if extra_command:
            duration_val = parse_duration(extra_command)
            if duration_val:
                ring_time = now + duration_val
                time_str = ring_time.strftime("%I:%M %p")
                try:
                    threading.Thread(
                        target=timer_thread,
                        args=(ring_time, "TIMER", duration_val, time_str, str(duration_val)),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.exception("Failed to start timer thread for TIMER (extra duration branch)")
                    vocalise("Error setting timer.")
                return
            ring_time, time_str = parse_time(extra_command)
            if ring_time:
                diff = ring_time - now
                duration_str = str(diff).split('.')[0]
                try:
                    threading.Thread(
                        target=timer_thread,
                        args=(ring_time, "TIMER", diff, time_str, duration_str),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.exception("Failed to start timer thread for TIMER (extra time branch)")
                    vocalise("Error setting timer.")
                return
        vocalise("Timer command cancelled. Switching back to wake word mode.")
    except Exception as e:
        logger.exception("Additional timer input error")
        vocalise("Error processing timer command. Switching back to wake word mode.")

def set_alarm(command, recognizer):
    now = datetime.now()
    duration_val = parse_duration(command)
    if duration_val:
        ring_time = now + duration_val
        time_str = ring_time.strftime("%I:%M %p")
        try:
            threading.Thread(
                target=timer_thread,
                args=(ring_time, "ALARM", duration_val, time_str, str(duration_val)),
                daemon=True
            ).start()
        except Exception as e:
            logger.exception("Failed to start alarm thread for ALARM")
            vocalise("Error setting alarm.")
        return
    ring_time, time_str = parse_time(command)
    if ring_time:
        diff = ring_time - now
        duration_str = str(diff).split('.')[0]
        try:
            threading.Thread(
                target=timer_thread,
                args=(ring_time, "ALARM", diff, time_str, duration_str),
                daemon=True
            ).start()
        except Exception as e:
            logger.exception("Failed to start alarm thread for ALARM (parse_time branch)")
            vocalise("Error setting alarm.")
        return
    vocalise("Alarm command not recognized. Please specify a duration or a time.")
    try:
        with mic_lock:
            with sr.Microphone() as source:
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=6)
        extra_command = recognize_audio(recognizer, audio).upper().strip()
        if extra_command:
            duration_val = parse_duration(extra_command)
            if duration_val:
                ring_time = now + duration_val
                time_str = ring_time.strftime("%I:%M %p")
                try:
                    threading.Thread(
                        target=timer_thread,
                        args=(ring_time, "ALARM", duration_val, time_str, str(duration_val)),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.exception("Failed to start alarm thread for ALARM (extra duration branch)")
                    vocalise("Error setting alarm.")
                return
            ring_time, time_str = parse_time(extra_command)
            if ring_time:
                diff = ring_time - now
                duration_str = str(diff).split('.')[0]
                try:
                    threading.Thread(
                        target=timer_thread,
                        args=(ring_time, "ALARM", diff, time_str, duration_str),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.exception("Failed to start alarm thread for ALARM (extra time branch)")
                    vocalise("Error setting alarm.")
                return
        vocalise("Alarm command cancelled. Switching back to wake word mode.")
    except Exception as e:
        logger.exception("Additional alarm input error")
        vocalise("Error processing alarm command. Switching back to wake word mode.")

def open_clock_app(mode=None, duration=None, ring_time=None, keep_open=False):
    try:
        logger.info(f"Attempting to open clock app with params: mode={mode}, duration={duration}, ring_time={ring_time}")
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CLOCK APP.html")
        
        if not os.path.exists(html_path):
            logger.error("Clock app HTML file not found at path: %s", html_path)
            raise FileNotFoundError("Clock app HTML file not found")
    
        params = {}
        if mode:
            params["mode"] = mode.lower()
        if duration:
            params["duration"] = duration if isinstance(duration, str) else str(duration)
        if ring_time:
            params["time"] = ring_time
            
        encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        file_uri = urllib.parse.urlunparse((
            'file',
            '',
            urllib.request.pathname2url(html_path),
            '',
            encoded_params,
            ''
        )).replace('file:///', 'file:///')
        
        logger.debug("Final file URI: %s", file_uri)
    
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice") as key:
                prog_id = winreg.QueryValueEx(key, 'ProgId')[0]
            logger.debug("Retrieved ProgID: %s", prog_id)
        except Exception as e:
            logger.warning("Failed to retrieve ProgID from registry: %s", str(e))
            prog_id = None
    
        browser_path = None
        if prog_id:
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
                    fr"{prog_id}\shell\open\command") as key:
                    browser_cmd, _ = winreg.QueryValueEx(key, '')
                    browser_path = browser_cmd.split('"')[1] if '"' in browser_cmd else browser_cmd.split()[0]
                logger.info("Detected browser path: %s", browser_path)
            except Exception as e:
                logger.warning("Failed to get browser path from registry: %s", str(e))
    
        if browser_path:
            args = [browser_path, file_uri]
            logger.info("Launching browser with command: %s", " ".join(args))
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # Launch the browser as a fully independent process
            proc = subprocess.Popen(
                args,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
                startupinfo=startupinfo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )
            logger.info("Launched browser process PID: %d", proc.pid)
            global clock_app_procs
            clock_app_procs.append(proc)
            logger.debug("Current clock app processes: %s", [p.pid for p in clock_app_procs])
        else:
            logger.warning("Using fallback webbrowser.open")
            webbrowser.open(file_uri, new=2, autoraise=False)
            
        return True
    except Exception as e:
        logger.exception("Critical error in open_clock_app")
        return False

def process_segment(segment, recognizer):
    global is_muted
    segment = segment.strip().upper()
    logger.info(f"Processing command: {segment}")
    
    if "CLOSE CLOCK APP" in segment:
        logger.info("Received CLOSE CLOCK APP command")
        try:
            close_clock_app()
            vocalise("Clock app closed.")
        except Exception as e:
            logger.exception("Failed to close clock app")
            vocalise("Failed to close clock app.")
        return True

    if "TIMER" in segment:
        logger.debug("Attempting to set timer")
        try:
            set_timer(segment, recognizer)
        except Exception as e:
            logger.exception("Timer setup failed")
        return True
    if "ALARM" in segment:
        logger.debug("Attempting to set alarm")
        try:
            set_alarm(segment, recognizer)
        except Exception as e:
            logger.exception("Alarm setup failed")
        return True

    if segment.startswith("OPEN "):
        app_to_open = segment[5:].strip()
        if app_to_open.upper().startswith("CLOCK APP"):
            try:
                if not open_clock_app(mode="clock"):
                    raise Exception("Clock app launch failed")
            except Exception as e:
                logger.exception("Failed to open clock app")
                vocalise("Failed to open clock app.")
            return True
        else:
            if app_to_open.upper().endswith(" AGAIN"):
                app_to_open = app_to_open[:-6].strip()
            open_app(app_to_open, recognizer)
            return True

    if "TELL ONLY THE DAY" in segment or "DAY ONLY" in segment or "ONLY DAY" in segment:
        tell_only_day()
        return True
    if "TELL ONLY THE DATE" in segment or "DATE ONLY" in segment or "ONLY DATE" in segment:
        tell_only_date()
        return True
    if any(phrase in segment for phrase in ["WHAT'S TODAY'S DAY", "WHAT IS TODAY'S DAY", "WHAT'S THE DAY TODAY", "DAY?", "WHAT'S THE DAY", "WHAT DAY IS TODAY", "DAY", "TELL THE DAY"]):
        tell_day_and_date(day_first=True)
        return True
    if any(phrase in segment for phrase in ["WHAT'S TODAY'S DATE", "WHAT IS TODAY'S DATE", "DATE?", "WHAT'S THE DATE", "WHAT DATE IS TODAY", "DATE", "TELL THE DATE"]):
        tell_day_and_date(day_first=False)
        return True

    toggle_mute_commands = ["MUTE", "SHUT UP", "SHUTUP", "STOP THAT", "UNMUTE", "TURN ON SOUND", "MUTE SOUND", "MUTE SOUNDS", "MUTE THE MUSIC", "MUTE THE AUDIO", "MUTE THE NOISE", "MUTE THE SOUNDS", "MUTE AUDIO", "MUTE NOISE"]
    for cmd in toggle_mute_commands:
        if cmd in segment:
            toggle_mute_volume()
            return True

    if "VOLUME UP" in segment or "INCREASE VOLUME" in segment or ("TURN UP" in segment and "VOLUME" in segment) or ("VOLUME" in segment and "LOWER" in segment):
        volume_up()
        return True

    if "VOLUME DOWN" in segment or "DECREASE VOLUME" in segment or ("TURN DOWN" in segment and "VOLUME" in segment) or ("VOLUME" in segment and "RAISE" in segment):
        volume_down()
        return True

    if ("MAX VOLUME" in segment or "FULL VOLUME" in segment or "MAXIMUM VOLUME" in segment or
       (segment.startswith("SET VOLUME") and ("MAX" in segment or "FULL" in segment or "MAXIMUM" in segment))):
        set_volume(100)
        is_muted = False
        return True

    if ("SET VOLUME" in segment or "VOLUME SET" in segment or "PUT VOLUME " in segment or ("VOLUME" in segment and "SET" in segment)):
        match = re.search(r"(\d+)", segment)
        if match:
            percent = int(match.group(1))
            set_volume(percent)
            return True
        else:
            vocalise("Please specify volume percentage")
            try:
                with mic_lock:
                    with sr.Microphone() as source:
                        response_audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                response_text = recognize_audio(recognizer, response_audio).upper().strip()
                match = re.search(r"(\d+)", response_text)
                if match:
                    percent = int(match.group(1))
                    set_volume(percent)
                    return True
            except Exception as e:
                logger.exception("Volume percentage input error")
                vocalise("No volume percentage provided. Command cancelled.")
                return True

    for key, response in exit_phrases.items():
        if key in segment:
            vocalise(response)
            time.sleep(1)
            exit_event.set()
            return True

    command_checks = [
        (shutdown_phrases, lambda: confirm_action(recognizer, shutdown_computer, "Shutdown")),
        (restart_phrases, lambda: confirm_action(recognizer, restart_computer, "Restart")),
        (sleep_phrases, sleep_computer),
        (lock_phrases, lock_computer),
        (["BATTERY"], battery_status),
        (["TIME"], tell_current_time),
        (custom_commands.keys(), lambda: vocalise(custom_commands.get(segment, "")))
    ]
    for phrases, action in command_checks:
        if any(phrase in segment for phrase in phrases):
            action()
            return True
    return False

def recognize_audio(recognizer, audio):
    try:
        text = recognizer.recognize_google(audio)
        text = text.upper().strip()
        logger.info(f"Heard (Google): {text}")
        return text
    except sr.UnknownValueError:
        logger.warning("Google Speech Recognition could not understand audio")
        return ""
    except sr.RequestError as e:
        logger.exception(f"Could not request results from Google Speech Recognition service; {e}")
        return ""

def active_listen_session(recognizer):
    if exit_event.is_set():
        return
    try:
        with mic_lock:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=8)
        command_text = recognize_audio(recognizer, audio).upper().strip()
        if command_text and process_segment(command_text, recognizer):
            return
        else:
            vocalise("Command not recognized. Please try again.")
            with mic_lock:
                with sr.Microphone() as source:
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)
            command_text = recognize_audio(recognizer, audio).upper().strip()
            if command_text:
                process_segment(command_text, recognizer)
            else:
                vocalise("No command received. Switching back to wake word mode.")
    except Exception as e:
        logger.exception("Active listen session error")
        vocalise("Error processing command. Switching back to wake word mode.")

def play_beep():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        beep_file = os.path.join(current_dir, "WAKEBEEP.m4a")
        if os.name == 'nt':
            command_open = f'open "{beep_file}" alias wakebeep'
            command_play = "play wakebeep from 0"
            command_close = "close wakebeep"
            ctypes.windll.winmm.mciSendStringW(command_open, None, 0, None)
            ctypes.windll.winmm.mciSendStringW(command_play, None, 0, None)
            threading.Timer(2, lambda: ctypes.windll.winmm.mciSendStringW(command_close, None, 0, None)).start()
        else:
            print('\a')
    except Exception as e:
        logger.exception("Error playing beep")

def listen_for_commands():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 4000  # Increased sensitivity
    recognizer.dynamic_energy_threshold = True
    logger.info("----- Starting listening session -----")
    
    while not exit_event.is_set():
        try:
            with mic_lock:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=1)
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=7)
            text = recognize_audio(recognizer, audio).upper().strip()
            wake, command_candidate = check_for_wake(text)
            if wake:
                logger.info(f"Wake word detected - command candidate: {command_candidate}")
                play_beep()
                if command_candidate:
                    if not process_segment(command_candidate, recognizer):
                        active_listen_session(recognizer)
                else:
                    active_listen_session(recognizer)
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            continue
        except Exception as e:
            logger.exception("Critical listening error")
            time.sleep(1)
    logger.info("Exiting listening loop.")

def hotkey_exit():
    vocalise("Exiting program via hotkey. Goodbye!")
    keyboard.clear_all_hotkeys()
    logger.info("Hotkey exit invoked. Terminating current process (PID: {}).".format(os.getpid()))
    exit_event.set()

def main():
    logger.info("===== Application Started =====")
    vocalise("Welcome sir")
    try:
        listen_for_commands()
    except Exception as e:
        logger.exception("Fatal error in main loop")
        sys.exit(1)
    sys.exit(0)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        logger.exception("Admin check failed")
        return False

def add_to_startup():
    if os.name != 'nt':
        return
    try:
        import winreg
        startup_key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        script_path = os.path.abspath(sys.argv[0])
        command = f'"{sys.executable}" "{script_path}"'
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, startup_key_path, 0, winreg.KEY_WRITE)
        except Exception:
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup_key_path, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(registry_key, "LUCIFER", 0, winreg.REG_SZ, command)
        winreg.CloseKey(registry_key)
        logger.info("Added program to startup registry key.")
    except Exception as e:
        logger.exception("Failed to add program to startup")

if __name__ == "__main__":
    if os.name == 'nt':
        if not is_admin():
            try:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            except Exception as e:
                logger.exception("Failed to elevate privileges")
            os._exit(0)
        
        current_script = os.path.abspath(sys.argv[0])
        my_pid = os.getpid()
        my_create_time = psutil.Process(my_pid).create_time()
        for proc in psutil.process_iter(['pid', 'cmdline', 'create_time']):
            if proc.pid == my_pid:
                continue
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any(os.path.abspath(arg) == current_script and arg.endswith(".py") for arg in cmdline):
                    proc_create_time = proc.info.get('create_time', 0)
                    if proc_create_time < my_create_time - 1:
                        vocalise("Another instance detected. Closing previous instance.")
                        logger.info("Closing previous instance with PID: {}".format(proc.pid))
                        proc.kill()
            except Exception as e:
                logger.exception("Error terminating previous instance")
        try:
            whnd = ctypes.windll.kernel32.GetConsoleWindow()
            if whnd:
                ctypes.windll.user32.ShowWindow(whnd, 0)
        except Exception as e:
            logger.exception("Error hiding console window")
            print("Error hiding console window:", e)
        add_to_startup()
    keyboard.add_hotkey('ctrl+alt+q', hotkey_exit, suppress=True)
    main()
