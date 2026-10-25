import tkinter as tk
from tkinter import messagebox
import speech_recognition as sr
import subprocess
import base64
import datetime
import webbrowser
import threading
import ollama
ollama_client = ollama.Client(host="http://127.0.0.1:11434")
import re
import time
import math
import ast
import operator
import os
import urllib.parse
import sys

from PIL import Image, ImageTk


# ============================================================
# AIRA - AI DESKTOP VOICE ASSISTANT
# Local AI: Ollama / gemma3:1b
# ============================================================

APP_TITLE = "AIRA - AI Desktop Voice Assistant"

IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "AIRA_AI_Girl_Icon.png.png"
)

if getattr(sys, "frozen", False):
    IMAGE_PATH = os.path.join(
        sys._MEIPASS,
        "AIRA_AI_Girl_Icon.png.png"
    )

OLLAMA_MODEL = "gemma3:1b"

BG = "#070712"
PANEL = "#101027"
PANEL_LIGHT = "#171735"
PURPLE = "#A855F7"
BLUE = "#38BDF8"
WHITE = "#F5F3FF"
GRAY = "#A1A1C2"
GREEN = "#34D399"
RED = "#FB7185"

conversation_history = []
current_language = "en"
assistant_busy = False
listening_enabled = True
app_closing = False

girl_photo = None
girl_canvas_image = None
ring_items = []
animation_phase = 0

recognizer = sr.Recognizer()
recognizer.pause_threshold = 0.8
recognizer.dynamic_energy_threshold = True


# ============================================================
# MAIN WINDOW
# ============================================================

window = tk.Tk()
window.title(APP_TITLE)
window.geometry("1000x850")
window.minsize(800, 700)
window.configure(bg=BG)


# ============================================================
# THREAD-SAFE UI HELPERS
# ============================================================

def ui_call(callback, *args):
    """Run a UI update safely from any thread."""
    if app_closing:
        return

    try:
        window.after(0, lambda: callback(*args))
    except (tk.TclError, RuntimeError):
        pass


def set_status(text, color=BLUE):
    status_label.config(text=text, fg=color)


def show_message(speaker, text):
    """Display the latest assistant or user message."""
    message_label.config(text=f"{speaker}: {text}")


def update_status(text, color=BLUE):
    ui_call(set_status, text, color)


def update_message(speaker, text):
    ui_call(show_message, speaker, text)


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_language(text):
    text_lower = text.lower()

    # Devanagari script: Hindi or Marathi
    if re.search(r"[\u0900-\u097F]", text):
        marathi_words = [
            "आहे", "काय", "मला", "माझे", "माझी",
            "कर", "सांग", "उघड", "वेळ", "दाखव",
            "झाले", "होते", "नको", "पाहिजे", "तू",
            "कुठे", "कसे", "कशी", "मराठी"
        ]

        if any(word in text for word in marathi_words):
            return "mr"

        return "hi"

    # Roman Marathi
    marathi_words = [
        " aahe", " ahe", " mala ", " maza ", " mazi ",
        " sang", " kar ", " karaycha", " pahije",
        " kuthe", " kasa", " kashi", " kay ",
        " nako", " zala", " zalay", " dakhav",
        " ughad", " bol", " karun de", " sang na",
        " mala", " atta", " nahi", " ho "
    ]

    # Roman Hindi
    hindi_words = [
        " mujhe ", " mera ", " meri ", " batao",
        " kaise ", " kya ", " kholo", " dikhao",
        " karo", " chahiye", " hindi"
    ]

    padded = f" {text_lower} "

    if any(word in padded for word in marathi_words):
        return "mr"

    if any(word in padded for word in hindi_words):
        return "hi"

    return "en"


def language_name(language):
    names = {
        "en": "English",
        "hi": "Hindi",
        "mr": "Marathi"
    }
    return names.get(language, "English")


def language_prompt(language):
    if language == "mr":
        return (
            "Reply in simple, natural Marathi. "
            "If the user writes Marathi using English letters, "
            "understand it and reply in Marathi using Devanagari. "
            "Keep answers clear and conversational."
        )

    if language == "hi":
        return (
            "Reply in simple, natural Hindi using Devanagari. "
            "Keep answers clear and conversational."
        )

    return (
        "Reply in clear, simple English. "
        "Keep answers helpful and conversational."
    )


# ============================================================
# TEXT TO SPEECH
# Uses Windows System.Speech; no paid API required
# ============================================================

def speak(text, language=None):
    if not text or app_closing:
        return

    language = language or current_language

    try:
        text_b64 = base64.b64encode(
            text.encode("utf-8")
        ).decode("ascii")

        culture = {
            "en": "en-IN",
            "hi": "hi-IN",
            "mr": "mr-IN"
        }.get(language, "en-IN")

        # Select a matching installed voice when available.
        # Windows may fall back to its default voice.
        ps_script = f"""
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$text = [System.Text.Encoding]::UTF8.GetString(
    [System.Convert]::FromBase64String('{text_b64}')
)
$culture = '{culture}'
$voice = $speaker.GetInstalledVoices() |
    Where-Object {{ $_.VoiceInfo.Culture.Name -eq $culture }} |
    Select-Object -First 1

if ($voice) {{
    $speaker.SelectVoice($voice.VoiceInfo.Name)
}}

$speaker.Rate = 0
$speaker.Speak($text)
$speaker.Dispose()
"""

        encoded_script = base64.b64encode(
            ps_script.encode("utf-16le")
        ).decode("ascii")

        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-EncodedCommand", encoded_script
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    except Exception as error:
        print("Speech error:", error)


# ============================================================
# LOCAL AI - OLLAMA
# ============================================================

def ask_gemma(user_text, language=None):
    language = language or current_language

    system_prompt = (
        "You are AIRA, a friendly desktop AI voice assistant. "
        "Be helpful, polite, and concise. "
        "You can answer general questions but do not claim to have "
        "performed computer actions unless the Python app did so. "
        + language_prompt(language)
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Keep recent context for follow-up questions.
    messages.extend(conversation_history[-10:])
    messages.append({"role": "user", "content": user_text})

    
    try:
        result = ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=messages
        )

        answer = result["message"]["content"].strip()

        conversation_history.append({
            "role": "user",
            "content": user_text
        })
        conversation_history.append({
            "role": "assistant",
            "content": answer
        })

        # Prevent unlimited history growth.
        if len(conversation_history) > 20:
            del conversation_history[:-20]

        return answer

    except Exception as error:
        print("Ollama error:", error)
        import traceback
        traceback.print_exc()

        if language == "mr":
            return (
                "Mala local AI connect karta ala nahi. "
                "Ollama suru aahe ka ani gemma3:1b model installed aahe ka "
                "te check kar."
            )

        if language == "hi":
            return (
                "Main local AI se connect nahi kar pa rahi hoon. "
                "Ollama aur gemma3:1b model check kijiye."
            )

        return (
            "I couldn't connect to the local AI. "
            "Please check that Ollama is running and gemma3:1b is installed."
        )


# ============================================================
# SAFE CALCULATOR
# ============================================================

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos
}


def safe_calculate(expression):
    expression = expression.replace("^", "**")
    tree = ast.parse(expression, mode="eval")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Invalid number")

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)

            if op_type not in _ALLOWED_OPERATORS:
                raise ValueError("Unsupported operator")

            left = evaluate(node.left)
            right = evaluate(node.right)

            # Prevent accidental enormous exponent calculations.
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("Exponent too large")

            return _ALLOWED_OPERATORS[op_type](left, right)

        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)

            if op_type not in _ALLOWED_OPERATORS:
                raise ValueError("Unsupported operator")

            return _ALLOWED_OPERATORS[op_type](evaluate(node.operand))

        raise ValueError("Invalid expression")

    return evaluate(tree)


def calculate_from_text(text):
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:\s*[\+\-\*/%\^]\s*[-+]?\d+(?:\.\d+)?)+", text)

    if not match:
        return None

    expression = match.group(0)

    try:
        result = safe_calculate(expression)
        return f"{expression} = {result}"
    except Exception:
        return None


# ============================================================
# APP COMMANDS
# ============================================================

def process_command(command):
    global current_language

    command = command.strip()

    if not command:
        return None

    language = detect_language(command)
    lower = command.lower().strip()

    update_message("You", command)
    update_status("Processing your command...", PURPLE)

    # Language selection
    if (
        "speak marathi" in lower
        or "marathi madhe bol" in lower
        or "marathi bol" in lower
        or "मराठीत बोल" in command
        or "मराठी बोल" in command
    ):
        current_language = "mr"
        return "Ho, ata mi tuzyashi Marathi madhye bolen."

    if (
        "speak hindi" in lower
        or "hindi mein bolo" in lower
        or "हिंदी में बोलो" in command
    ):
        current_language = "hi"
        return "Theek hai, ab main aapse Hindi mein baat karungi."

    if (
        "speak english" in lower
        or "english madhe bol" in lower
    ):
        current_language = "en"
        return "Sure! I will speak with you in English."

    # Use the detected language for ordinary requests.
    # An explicit language-selection command overrides this.
    current_language = language

    # Exit
    exit_words = [
        "exit", "quit", "close aira", "stop assistant",
        "band karo", "बंद करो", "बंद कर दो",
        "aira band kar", "aira band kar",
        "थांब", "बंद कर"
    ]

    if any(word in lower for word in exit_words):
        ui_call(set_status, "Closing AIRA...", RED)
        ui_call(window.after, 700, window.destroy)
        return "Goodbye! Talk to you soon."

    # Time
    time_words = [
        "what time", "current time", "time now",
        "time sang", "vel kiti", "वेळ किती",
        "समय क्या", "kitne baje"
    ]

    if any(word in lower for word in time_words):
        current_time = datetime.datetime.now().strftime("%I:%M %p")

        if language == "mr":
            return f"Ata vel {current_time} aahe."

        if language == "hi":
            return f"Abhi samay {current_time} hai."

        return f"The current time is {current_time}."

    # Date
    date_words = [
        "today's date", "what date", "today date",
        "aaj ki date", "aaj ki tarikh",
        "aajchi tarikh", "आज की तारीख",
        "आजची तारीख", "आज की डेट"
    ]

    if any(word in lower for word in date_words):
        today = datetime.datetime.now().strftime("%d %B %Y")

        if language == "mr":
            return f"Aajchi tarikh {today} aahe."

        if language == "hi":
            return f"Aaj ki tareekh {today} hai."

        return f"Today's date is {today}."

    # Open Calculator
    if (
        "open calculator" in lower
        or "calculator open" in lower
        or "calculator ughad" in lower
        or "कॅल्क्युलेटर उघड" in command
        or "कैलकुलेटर खोलो" in command
    ):
        try:
            subprocess.Popen("calc.exe")
            return "Calculator is open."
        except Exception:
            return "I couldn't open Calculator."

    # Open Notepad
    if (
        "open notepad" in lower
        or "notepad open" in lower
        or "notepad ughad" in lower
        or "नोटपैड खोलो" in command
        or "नोटपॅड उघड" in command
    ):
        try:
            subprocess.Popen("notepad.exe")
            return "Notepad is open."
        except Exception:
            return "I couldn't open Notepad."

    # Open File Explorer
    if (
        "open file explorer" in lower
        or "open explorer" in lower
        or "file explorer open" in lower
        or "files ughad" in lower
        or "फाइल एक्सप्लोरर खोलो" in command
    ):
        try:
            subprocess.Popen("explorer.exe")
            return "File Explorer is open."
        except Exception:
            return "I couldn't open File Explorer."

    # Open Chrome
    if "open chrome" in lower or "chrome ughad" in lower:
        try:
            subprocess.Popen("cmd /c start chrome", shell=True)
            return "Opening Google Chrome."
        except Exception:
            webbrowser.open("https://www.google.com")
            return "Opening your browser."

    # MIT-WPU official website
    if (
        "mit wpu" in lower
        or "mitwpu" in lower
        or "mit world peace university" in lower
    ):
        webbrowser.open("https://mitwpu.edu.in/")
        return "Opening the MIT-WPU official website."

    # YouTube commands
    if "youtube" in lower or "you tube" in lower:
        search_terms = re.sub(
            r"\b(open|launch|play|search|on|in|youtube|you tube|"
            r"find|video|videos|please)\b",
            " ",
            lower
        ).strip()

        search_terms = re.sub(r"\s+", " ", search_terms)

        if search_terms:
            url = (
                "https://www.youtube.com/results?search_query="
                + urllib.parse.quote_plus(search_terms)
            )
            webbrowser.open(url)
            return f"Searching YouTube for {search_terms}."

        webbrowser.open("https://www.youtube.com")
        return "Opening YouTube."

    # Google search
    if (
        "google" in lower
        or "search for" in lower
        or "search on internet" in lower
        or "google search" in lower
        or "search about" in lower
    ):
        search_terms = re.sub(
            r"\b(open|google|search|for|about|on|internet|please)\b",
            " ",
            lower
        ).strip()

        search_terms = re.sub(r"\s+", " ", search_terms)

        if search_terms:
            url = (
                "https://www.google.com/search?q="
                + urllib.parse.quote_plus(search_terms)
            )
            webbrowser.open(url)
            return f"Searching Google for {search_terms}."

        webbrowser.open("https://www.google.com")
        return "Opening Google."

    # General browser search phrases
    if lower.startswith("search "):
        search_terms = command[7:].strip()

        if search_terms:
            webbrowser.open(
                "https://www.google.com/search?q="
                + urllib.parse.quote_plus(search_terms)
            )
            return f"Searching for {search_terms}."

    # Open other websites by name.
    # If the exact URL is not configured, search for its official website.
    website_match = re.search(
        r"\\bopen\\s+(.+?)\\s+(?:website|site)\\b",
        lower
    )
    if website_match:
        site_name = website_match.group(1).strip()
        if site_name:
            search_url = (
                "https://www.google.com/search?q="
                + urllib.parse.quote_plus(site_name + " official website")
            )
            webbrowser.open(search_url)
            return f"Searching for the official {site_name} website."

    # Also support "open <site name>" for unknown websites.
    if lower.startswith("open "):
        site_name = lower[5:].strip()
        if site_name and not any(
            phrase in site_name for phrase in (
                "calculator", "notepad", "file explorer", "explorer",
                "chrome", "google", "youtube", "you tube",
                "mit wpu", "mitwpu", "mit world peace university"
            )
        ):
            search_url = (
                "https://www.google.com/search?q="
                + urllib.parse.quote_plus(site_name + " official website")
            )
            webbrowser.open(search_url)
            return f"Searching for the official {site_name} website."

    # Calculator expressions
    calculation = calculate_from_text(lower)

    if calculation:
        return calculation

    # Otherwise ask the local AI.
    return ask_gemma(command, current_language)


# ============================================================
# VOICE LISTENING
# ============================================================

def recognize_speech(audio):
    """
    Try the selected language first, then other supported languages.
    Google speech recognition needs an internet connection.
    """
    language_codes = {
        "en": "en-IN",
        "hi": "hi-IN",
        "mr": "mr-IN"
    }

    order = [current_language]

    for code in ("en", "hi", "mr"):
        if code not in order:
            order.append(code)

    for language in order:
        try:
            return recognizer.recognize_google(
                audio,
                language=language_codes[language]
            )
        except sr.UnknownValueError:
            continue
        except sr.RequestError as error:
            print("Speech recognition service error:", error)
            return None

    return None


def voice_reply(command):
    """Process one voice command and speak its reply."""
    global assistant_busy

    try:
        answer = process_command(command)

        if answer:
            update_message("AIRA", answer)
            update_status("AIRA is speaking...", PURPLE)
            speak(answer, current_language)

    except Exception as error:
        print("Command error:", error)
        answer = "Sorry, something went wrong while processing that command."
        update_message("AIRA", answer)
        speak(answer, current_language)

    finally:
        assistant_busy = False

        if not app_closing:
            update_status("Listening for your command...", GREEN)


def listen_loop():
    """
    Automatically starts listening after launch.
    Keep listening in a background thread so the UI remains responsive.
    """
    global assistant_busy

    try:
        with sr.Microphone(device_index=1) as source:
            print("AIRA microphone opened successfully")
            update_status("Adjusting microphone...", BLUE)
            recognizer.adjust_for_ambient_noise(source, duration=1)

            update_status("Listening for your command...", GREEN)

            while not app_closing:
                if not listening_enabled or assistant_busy:
                    time.sleep(0.2)
                    continue

                try:
                    audio = recognizer.listen(
                        source,
                        timeout=1,
                        phrase_time_limit=10
                    )

                except sr.WaitTimeoutError:
                    continue

                except Exception as error:
                    print("Microphone listening error:", error)
                    time.sleep(0.5)
                    continue

                if app_closing:
                    break

                update_status("Recognizing speech...", BLUE)
                command = recognize_speech(audio)

                if not command:
                    update_status("Listening for your command...", GREEN)
                    continue

                command = command.strip()

                if not command:
                    continue

                assistant_busy = True
                threading.Thread(
                    target=voice_reply,
                    args=(command,),
                    daemon=True
                ).start()

                # Wait until the command is processed before listening again.
                while assistant_busy and not app_closing:
                    time.sleep(0.1)

    except Exception as error:
        print("Microphone setup error:", error)
        update_status(
            "Microphone unavailable. Check microphone permissions.",
            RED
        )
        update_message(
            "AIRA",
            "Please check your microphone and restart the app."
        )


# ============================================================
# TALK BUTTON / QUICK COMMANDS
# ============================================================

def talk_button_action():
    global listening_enabled

    listening_enabled = True
    update_status("AIRA is ready to listen...", GREEN)

    # The automatic listener already runs in the background.
    # This button re-enables listening if it was paused.
    update_message("AIRA", "I'm listening. What would you like me to do?")


def run_quick_command(command):
    global assistant_busy

    if assistant_busy:
        update_status("Please wait for the current response...", PURPLE)
        return

    assistant_busy = True

    def worker():
        try:
            answer = process_command(command)

            if answer:
                update_message("AIRA", answer)
                update_status("AIRA is speaking...", PURPLE)
                speak(answer, current_language)

        except Exception as error:
            print("Quick command error:", error)
            update_message("AIRA", "Sorry, that command could not be completed.")

        finally:
            assistant_busy = False
            if not app_closing:
                update_status("Listening for your command...", GREEN)

    threading.Thread(target=worker, daemon=True).start()


# ============================================================
# ANIMATED CENTER CANVAS
# ============================================================

canvas = tk.Canvas(
    window,
    bg=BG,
    highlightthickness=0
)
canvas.pack(fill="both", expand=True, padx=18, pady=(10, 0))


def load_girl_image():
    global girl_photo

    try:
        if not os.path.isfile(IMAGE_PATH):
            print("AI Girl image not found:", IMAGE_PATH)
            return

        original = Image.open(IMAGE_PATH).convert("RGBA")
        original.thumbnail((270, 270), Image.Resampling.LANCZOS)
        girl_photo = ImageTk.PhotoImage(original)

    except Exception as error:
        print("Could not load AI Girl image:", error)
        girl_photo = None


load_girl_image()


def draw_scene():
    """Redraw the scene whenever the canvas changes size."""
    global girl_canvas_image, ring_items

    canvas.delete("scene")
    ring_items = []

    width = max(canvas.winfo_width(), 600)
    height = max(canvas.winfo_height(), 350)

    center_x = width // 2
    center_y = int(height * 0.43)

    # Outer futuristic rings
    for radius, color, line_width in [
        (170, "#25205A", 2),
        (145, "#403080", 2),
        (120, "#5B36A5", 2),
        (95, "#245B9B", 2)
    ]:
        item = canvas.create_oval(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            outline=color,
            width=line_width,
            tags="scene"
        )
        ring_items.append(item)

    # Orbiting dots
    for i in range(8):
        angle = i * (math.pi / 4)
        x = center_x + 158 * math.cos(angle)
        y = center_y + 158 * math.sin(angle)

        canvas.create_oval(
            x - 4, y - 4, x + 4, y + 4,
            fill=BLUE if i % 2 == 0 else PURPLE,
            outline="",
            tags="scene"
        )

    # Girl image centered above the rings.
    if girl_photo is not None:
        canvas.create_image(
            center_x,
            center_y,
            image=girl_photo,
            tags="scene"
        )
    else:
        # Fallback if the image file cannot be loaded.
        canvas.create_oval(
            center_x - 75,
            center_y - 75,
            center_x + 75,
            center_y + 75,
            fill=PANEL,
            outline=PURPLE,
            width=3,
            tags="scene"
        )
        canvas.create_text(
            center_x,
            center_y,
            text="A",
            font=("Segoe UI", 60, "bold"),
            fill=WHITE,
            tags="scene"
        )

    canvas.create_text(
        center_x,
        center_y + 195,
        text="A I R A",
        font=("Segoe UI", 22, "bold"),
        fill=WHITE,
        tags="scene"
    )

    canvas.create_text(
        center_x,
        center_y + 225,
        text="YOUR PERSONAL AI ASSISTANT",
        font=("Segoe UI", 9, "bold"),
        fill=GRAY,
        tags="scene"
    )


def animate_rings():
    global animation_phase

    if app_closing:
        return

    animation_phase += 1

    width = max(canvas.winfo_width(), 600)
    height = max(canvas.winfo_height(), 350)
    center_x = width // 2
    center_y = int(height * 0.43)

    # Smoothly pulse each ring.
    for index, item in enumerate(ring_items):
        radius = [170, 145, 120, 95][index]
        pulse = 5 * math.sin(
            animation_phase * 0.06 + index * 0.9
        )
        r = radius + pulse

        try:
            canvas.coords(
                item,
                center_x - r,
                center_y - r,
                center_x + r,
                center_y + r
            )
        except tk.TclError:
            pass

    # Move small orbit dots around the girl.
    canvas.delete("orbit")

    for i in range(8):
        angle = animation_phase * 0.025 + i * (math.pi / 4)

        x = center_x + 158 * math.cos(angle)
        y = center_y + 158 * math.sin(angle)

        canvas.create_oval(
            x - 4,
            y - 4,
            x + 4,
            y + 4,
            fill=BLUE if i % 2 == 0 else PURPLE,
            outline="",
            tags=("scene", "orbit")
        )

    window.after(40, animate_rings)


def on_canvas_resize(event):
    draw_scene()


canvas.bind("<Configure>", on_canvas_resize)


# ============================================================
# APP HEADER
# ============================================================

header = tk.Frame(window, bg=BG)
header.pack(fill="x", padx=28, pady=(12, 4))

title_label = tk.Label(
    header,
    text="A I R A",
    font=("Segoe UI", 25, "bold"),
    bg=BG,
    fg=WHITE
)
title_label.pack()

subtitle_label = tk.Label(
    header,
    text="FUTURISTIC AI VOICE ASSISTANT",
    font=("Segoe UI", 9, "bold"),
    bg=BG,
    fg=PURPLE
)
subtitle_label.pack(pady=(0, 5))


# ============================================================
# STATUS AND LIVE MESSAGE
# ============================================================

status_label = tk.Label(
    window,
    text="Starting AIRA...",
    font=("Segoe UI", 10, "bold"),
    bg=BG,
    fg=BLUE
)
status_label.pack(pady=(0, 6))

message_label = tk.Label(
    window,
    text="AIRA: Initializing local AI...",
    font=("Segoe UI", 10),
    bg=BG,
    fg=WHITE,
    wraplength=850,
    justify="center"
)
message_label.pack(fill="x", padx=35, pady=(0, 8))


# ============================================================
# TALK TO AIRA BUTTON
# ============================================================

talk_button = tk.Button(
    window,
    text="🎙  TALK TO AIRA",
    command=talk_button_action,
    font=("Segoe UI", 13, "bold"),
    bg=PURPLE,
    fg="white",
    activebackground="#9333EA",
    activeforeground="white",
    relief="flat",
    cursor="hand2",
    padx=35,
    pady=12
)
talk_button.pack(pady=(3, 12))


# ============================================================
# QUICK COMMANDS
# ============================================================

quick_frame = tk.Frame(window, bg=BG)
quick_frame.pack(fill="x", padx=25, pady=(0, 10))

quick_title = tk.Label(
    quick_frame,
    text="QUICK COMMANDS",
    font=("Segoe UI", 10, "bold"),
    bg=BG,
    fg=GRAY
)
quick_title.pack(pady=(0, 8))


def create_quick_button(parent, text, command, color):
    return tk.Button(
        parent,
        text=text,
        command=lambda: run_quick_command(command),
        font=("Segoe UI", 9, "bold"),
        bg=PANEL_LIGHT,
        fg=color,
        activebackground=PANEL,
        activeforeground=WHITE,
        relief="flat",
        cursor="hand2",
        padx=13,
        pady=8
    )


button_row = tk.Frame(quick_frame, bg=BG)
button_row.pack()

create_quick_button(
    button_row, "YouTube", "open YouTube", RED
).pack(side="left", padx=5)

create_quick_button(
    button_row, "Google", "open Google", BLUE
).pack(side="left", padx=5)

create_quick_button(
    button_row, "Calculator", "open calculator", GREEN
).pack(side="left", padx=5)

create_quick_button(
    button_row, "Notepad", "open notepad", PURPLE
).pack(side="left", padx=5)

create_quick_button(
    button_row, "File Explorer", "open file explorer", WHITE
).pack(side="left", padx=5)


# ============================================================
# FOOTER
# ============================================================

footer = tk.Label(
    window,
    text="POWERED BY OLLAMA  •  GEMMA3:1B  •  LOCAL AI",
    font=("Segoe UI", 8),
    bg=BG,
    fg="#696987"
)
footer.pack(pady=(0, 12))


# ============================================================
# CLOSE APP SAFELY
# ============================================================

def on_close():
    global app_closing, listening_enabled

    app_closing = True
    listening_enabled = False

    try:
        window.destroy()
    except tk.TclError:
        pass


window.protocol("WM_DELETE_WINDOW", on_close)


# ============================================================
# START AIRA AUTOMATICALLY
# ============================================================

def startup_greeting():
    greeting = "Hello! I am AIRA. How can I help you today?"

    update_message("AIRA", greeting)
    update_status("Starting voice assistant...", PURPLE)

    speak(greeting, "en")

    if not app_closing:
        update_status("Listening for your command...", GREEN)


def start_assistant():
    # Greeting and speech recognition run in background threads.
    threading.Thread(
        target=startup_greeting,
        daemon=True
    ).start()

    # Automatically begin listening when the app opens.
    threading.Thread(
        target=listen_loop,
        daemon=True
    ).start()


# Draw the initial screen.
window.update_idletasks()
draw_scene()
animate_rings()

# Start voice assistant automatically.
window.after(500, start_assistant)

# Run the app.
window.mainloop()