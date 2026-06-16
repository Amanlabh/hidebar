#!/usr/bin/env python3
"""
Hidebar - An AI assistant powered by the Google Gemini API
Hidden from screen sharing
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, simpledialog
import requests
import json
import threading
import sys
import os
from datetime import datetime

# Voice recognition imports (optional, with fallback)
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

class HidebarApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hidebar")
        self.root.geometry("800x600")

        # Make window always on top and transparent
        self.root.attributes('-topmost', True)  # Always on top - pinned
        self.root.attributes('-alpha', 0.75)  # More transparent (0.0 = fully transparent, 1.0 = opaque)
        
        # Keep window on top even when clicking other windows
        self.root.lift()
        self.root.focus_force()
        
        # Modern dark background
        self.root.configure(bg="#0d1117")
        
        # Set window to appear on all spaces (macOS)
        if sys.platform == "darwin":
            self.setup_multi_space()
        
        # Hide from screen sharing (macOS specific)
        self.setup_privacy()
        
        # Gemini configuration
        # Key resolution order: env var -> saved config file -> empty (prompt user)
        self.config_path = os.path.join(os.path.expanduser("~"), ".hidebar", "config.json")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY") or self.load_config().get("api_key", "")
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-flash-latest"  # Default model, can be changed
        self.available_gemini_models = [
            "gemini-flash-latest",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-flash-lite-latest",
            "gemini-pro-latest",
        ]
        self.conversation_history = []
        # Speed: keep-alive connection pool (skips TLS handshake per request)
        self.session = requests.Session()
        # New-style AQ.* keys authenticate via header, not ?key= query param
        if self.gemini_api_key:
            self.session.headers.update({"X-goog-api-key": self.gemini_api_key})
        # Speed: only send the last N turns as context (fewer input tokens)
        self.max_history_messages = 12
        # Concise system instruction = shorter, faster generations
        self.system_instruction = (
            "You are Hidebar, a fast assistant. Answer directly and concisely. "
            "Skip preamble and filler. Use short paragraphs or bullet points."
        )
        self.streaming_message_start = None
        
        # Voice recognition setup
        self.is_listening = False
        self.recognizer = None
        self.microphone = None
        self.tts_engine = None
        self.audio_devices = []          # list of (index, name)
        self.input_device_index = None   # selected capture device
        self.bg_listener_stop = None     # stopper from listen_in_background
        # Loopback drivers that expose system audio as an input device
        self.loopback_keywords = ("blackhole", "loopback", "soundflower", "aggregate", "multi-output")
        self.setup_voice()
        
        # Setup UI
        self.setup_ui()

        # Global shortcut: Cmd+D (mac) / Ctrl+D (win/linux) toggles the mic
        self.root.bind_all("<Command-d>", self.toggle_voice_shortcut)
        self.root.bind_all("<Control-d>", self.toggle_voice_shortcut)

        # Keep window on top periodically
        self.keep_on_top()
        
        # Check Gemini connection (or prompt for a key on first run)
        if self.gemini_api_key:
            self.check_gemini_connection()
        else:
            self.root.after(600, self.prompt_for_key)

    def setup_multi_space(self):
        """Pin the window to every space and above fullscreen apps (macOS)."""
        try:
            from AppKit import (
                NSApplication,
                NSWindowCollectionBehaviorCanJoinAllSpaces,
                NSWindowCollectionBehaviorFullScreenAuxiliary,
                NSWindowCollectionBehaviorStationary,
                NSScreenSaverWindowLevel,
            )
        except Exception as e:
            print(f"Multi-space setup note (pyobjc unavailable): {e}")
            return

        # Combined behavior: show on all spaces, overlay fullscreen apps,
        # and don't get swept up by Mission Control.
        all_spaces_behavior = (
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
        )

        def pin_window():
            """Re-apply pinning every cycle (runs on the main thread)."""
            try:
                app = NSApplication.sharedApplication()
                for window in app.windows():
                    window.setCollectionBehavior_(all_spaces_behavior)
                    # Screen-saver level floats above fullscreen apps
                    window.setLevel_(NSScreenSaverWindowLevel)
            except Exception as e:
                print(f"[pin] error: {e}")
            # Re-apply often so it wins over any Tk reorder / space swipe
            self.root.after(700, pin_window)

        # Schedule on the main thread once the NSWindow exists
        self.root.after(400, pin_window)
    
    def keep_on_top(self):
        """Keep the window visible on top.

        On macOS, leveling is owned by pin_window (pyobjc screen-saver level) so
        the window floats above fullscreen apps. Do NOT re-assert Tk -topmost
        here — that resets the NSWindow to floating level (below fullscreen).
        """
        if sys.platform != "darwin":
            # Non-mac: Tk -topmost is the mechanism
            self.root.attributes('-topmost', True)
            self.root.lift()
        self.root.after(2000, self.keep_on_top)
        
    def setup_privacy(self):
        """Configure window to be hidden from screen sharing"""
        try:
            # macOS specific: Hide window from screen sharing
            if sys.platform == "darwin":
                # Start background process to continuously hide window
                self.start_privacy_guard()
            
        except Exception as e:
            print(f"Privacy setup note: {e}")
    
    def start_privacy_guard(self):
        """Start a background thread that continuously hides the window from screen sharing"""
        import subprocess
        import threading

        # Capture title here (main thread) — Tk calls from a worker thread crash
        window_title = self.root.title()

        def hide_window_loop():
            """Continuously hide the window from screen sharing using AppleScript only"""
            pid = os.getpid()

            while True:
                try:
                    # Use AppleScript to set window sharing type (safe from background thread)
                    applescript = f'''
                    tell application "System Events"
                        set targetProcs to (every process whose unix id is {pid})
                        repeat with appProc in targetProcs
                            try
                                set windowList to (every window of appProc whose name contains "{window_title}")
                                repeat with aWindow in windowList
                                    try
                                        -- Try to exclude from screen capture (macOS 13+)
                                        set value of attribute "AXExcludedFromScreenCapture" of aWindow to true
                                    end try
                                end repeat
                            end try
                        end repeat
                    end tell
                    '''
                    
                    subprocess.run(
                        ['osascript', '-e', applescript],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=1
                    )
                    
                except Exception:
                    pass
                
                # Check every 0.5 seconds
                import time
                time.sleep(0.5)
        
        # Try to use pyobjc on main thread if available (more reliable)
        def setup_pyobjc_privacy():
            """Setup privacy using pyobjc on the main thread"""
            try:
                import objc
                from AppKit import NSApplication
                from Cocoa import NSWindowSharingNone
                
                window_title = self.root.title()
                app = NSApplication.sharedApplication()
                for window in app.windows():
                    if window.title() == window_title:
                        # Set window sharing type to None (hidden from screen sharing)
                        window.setSharingType_(NSWindowSharingNone)
                        return True
            except (ImportError, AttributeError, Exception):
                pass
            return False
        
        # Try pyobjc method on main thread first
        self.root.after(500, setup_pyobjc_privacy)
        
        # Start the AppleScript-based privacy guard in a daemon thread
        # Small delay to ensure window is fully created
        import time
        time.sleep(0.5)
        privacy_thread = threading.Thread(target=hide_window_loop, daemon=True)
        privacy_thread.start()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main container with gradient-like effect
        main_frame = tk.Frame(self.root, bg="#0d1117")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Header with modern design
        header_frame = tk.Frame(main_frame, bg="#161b22", relief=tk.FLAT)
        header_frame.pack(fill=tk.X, pady=0, padx=0)
        
        # Header content container
        header_content = tk.Frame(header_frame, bg="#161b22")
        header_content.pack(fill=tk.X, padx=20, pady=15)
        
        # Title with icon
        title_container = tk.Frame(header_content, bg="#161b22")
        title_container.pack(side=tk.LEFT, fill=tk.Y)
        
        title_label = tk.Label(
            title_container,
            text="✨ Hidebar",
            font=("SF Pro Display", 20, "bold"),
            bg="#161b22",
            fg="#f0f6fc"
        )
        title_label.pack(side=tk.LEFT)
        
        # Subtitle / model badge
        subtitle_label = tk.Label(
            title_container,
            text="Powered by Gemini",
            font=("SF Pro Display", 10),
            bg="#161b22",
            fg="#8b949e"
        )
        subtitle_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Audio source selector (microphone vs system-audio loopback)
        source_frame = tk.Frame(header_content, bg="#161b22")
        source_frame.pack(side=tk.RIGHT, padx=(0, 16))

        tk.Label(
            source_frame,
            text="Listen:",
            bg="#161b22",
            fg="#8b949e",
            font=("SF Pro Display", 10)
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.source_var = tk.StringVar()
        self.source_dropdown = ttk.Combobox(
            source_frame,
            textvariable=self.source_var,
            width=20,
            state="readonly",
            font=("SF Mono", 10)
        )
        device_labels = [f"{i}: {n}" for i, n in self.audio_devices] or ["default"]
        self.source_dropdown.config(values=device_labels)
        if self.input_device_index is not None:
            self.source_var.set(f"{self.input_device_index}: "
                                f"{dict(self.audio_devices).get(self.input_device_index, '')}")
        else:
            self.source_var.set(device_labels[0])
        self.source_dropdown.pack(side=tk.LEFT)
        self.source_dropdown.bind("<<ComboboxSelected>>", self.on_source_change)

        # Model selector with better styling
        model_frame = tk.Frame(header_content, bg="#161b22")
        model_frame.pack(side=tk.RIGHT)

        tk.Label(
            model_frame,
            text="Model:",
            bg="#161b22",
            fg="#8b949e",
            font=("SF Pro Display", 10)
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        self.model_var = tk.StringVar(value=self.model)
        self.model_dropdown = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            width=18,
            state="readonly",
            font=("SF Mono", 10)
        )
        self.model_dropdown.pack(side=tk.LEFT)
        self.model_dropdown.bind("<<ComboboxSelected>>", self.on_model_change)
        
        # Style the combobox
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox', 
                       fieldbackground='#21262d',
                       background='#21262d',
                       foreground='#c9d1d9',
                       borderwidth=1,
                       relief='flat')
        
        # Chat display area with modern styling
        chat_container = tk.Frame(main_frame, bg="#0d1117")
        chat_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(15, 15))
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_container,
            wrap=tk.WORD,
            font=("SF Mono", 12),
            bg="#0d1117",
            fg="#c9d1d9",
            insertbackground="#58a6ff",
            selectbackground="#264f78",
            padx=20,
            pady=20,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#30363d",
            highlightcolor="#58a6ff"
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        self.chat_display.config(state=tk.DISABLED)
        
        # Input area with modern design
        input_container = tk.Frame(main_frame, bg="#0d1117")
        input_container.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Input field with border
        input_wrapper = tk.Frame(input_container, bg="#21262d", relief=tk.FLAT)
        input_wrapper.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 12))
        
        self.input_field = tk.Text(
            input_wrapper,
            height=3,
            font=("SF Mono", 11),
            bg="#21262d",
            fg="#c9d1d9",
            insertbackground="#58a6ff",
            relief=tk.FLAT,
            padx=15,
            pady=12,
            wrap=tk.WORD,
            highlightthickness=0,
            borderwidth=0
        )
        self.input_field.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.input_field.bind("<Return>", self.on_enter_pressed)
        self.input_field.bind("<Shift-Return>", lambda e: None)
        self.input_field.bind("<FocusIn>", lambda e: input_wrapper.config(bg="#30363d"))
        self.input_field.bind("<FocusOut>", lambda e: input_wrapper.config(bg="#21262d"))
        
        # Button container
        button_frame = tk.Frame(input_container, bg="#0d1117")
        button_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Send button (primary accent)
        self.send_button = tk.Button(
            button_frame,
            text="Send  ⏎",
            command=self.send_message,
            bg="#1f6feb",
            fg="#ffffff",
            font=("SF Pro Display", 12, "bold"),
            relief=tk.FLAT,
            padx=24,
            pady=12,
            cursor="hand2",
            activebackground="#388bfd",
            activeforeground="#ffffff",
            borderwidth=0
        )
        self.send_button.pack(side=tk.TOP, fill=tk.X)

        # Secondary row: voice + clear
        secondary_row = tk.Frame(button_frame, bg="#0d1117")
        secondary_row.pack(side=tk.TOP, pady=(8, 0), fill=tk.X)

        self.voice_button = tk.Button(
            secondary_row,
            text="🎤",
            command=self.toggle_voice_listening,
            bg="#21262d",
            fg="#ffffff",
            font=("SF Pro Display", 14),
            relief=tk.FLAT,
            padx=14,
            pady=8,
            cursor="hand2",
            activebackground="#30363d",
            activeforeground="#ffffff",
            borderwidth=0
        )
        self.voice_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        clear_button = tk.Button(
            secondary_row,
            text="🗑",
            command=self.clear_chat,
            bg="#21262d",
            fg="#ffffff",
            font=("SF Pro Display", 14),
            relief=tk.FLAT,
            padx=14,
            pady=8,
            cursor="hand2",
            activebackground="#30363d",
            activeforeground="#ffffff",
            borderwidth=0
        )
        clear_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 4))

        key_button = tk.Button(
            secondary_row,
            text="🔑",
            command=lambda: self.prompt_for_key(force=True),
            bg="#21262d",
            fg="#ffffff",
            font=("SF Pro Display", 14),
            relief=tk.FLAT,
            padx=14,
            pady=8,
            cursor="hand2",
            activebackground="#30363d",
            activeforeground="#ffffff",
            borderwidth=0
        )
        key_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))
        
        # Status bar with modern styling
        status_container = tk.Frame(main_frame, bg="#0d1117")
        status_container.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        self.status_bar = tk.Label(
            status_container,
            text="● Ready",
            bg="#0d1117",
            fg="#7c3aed",
            font=("SF Mono", 9),
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.LEFT)
        
        # Welcome message
        mic_key = "⌘D" if sys.platform == "darwin" else "Ctrl+D"
        self.add_message("system", f"👋 Hidebar — fast AI assistant powered by Gemini.\n\n💡 Type, click 🎤, or press {mic_key} to toggle the mic. Enter sends, Shift+Enter = newline.\n\n🫥 Hidden from screen sharing.")
    
    def on_enter_pressed(self, event):
        """Handle Enter key press"""
        if event.state == 0:  # No modifier keys
            self.send_message()
            return "break"
        return None
    
    def on_model_change(self, event=None):
        """Handle model selection change"""
        self.model = self.model_var.get()
        self.update_status(f"Model changed to: {self.model}")
        self.load_available_models()

    def clear_chat(self):
        """Reset the conversation and clear the display"""
        self.conversation_history = []
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.add_message("system", "🧹 Conversation cleared.")
        self.update_status("Ready")
    
    def on_source_change(self, event=None):
        """Switch the audio capture device; rebuild mic and restart if listening."""
        if not SPEECH_RECOGNITION_AVAILABLE or not self.recognizer:
            return
        was_listening = self.is_listening
        if was_listening:
            self.stop_listening()
        try:
            label = self.source_var.get()
            idx = int(label.split(":", 1)[0]) if ":" in label else None
        except Exception:
            idx = None
        self.input_device_index = idx
        try:
            self.microphone = sr.Microphone(device_index=idx)
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            self.update_status(f"Audio source set to: {self.source_var.get()}")
        except Exception as e:
            self.update_status(f"Source error: {str(e)[:40]}")
            return
        if was_listening:
            self.start_listening()

    def load_config(self):
        """Load saved settings (e.g. API key) from the user's home dir."""
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_config(self, data):
        """Merge and persist settings to ~/.hidebar/config.json."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            cfg = self.load_config()
            cfg.update(data)
            with open(self.config_path, "w") as f:
                json.dump(cfg, f)
            return True
        except Exception as e:
            print(f"Config save error: {e}")
            return False

    def prompt_for_key(self, force=False):
        """Ask the user for their Gemini API key and save it."""
        if self.gemini_api_key and not force:
            return
        key = simpledialog.askstring(
            "Gemini API Key",
            "Enter your Google Gemini API key.\n"
            "Get a free key at: https://aistudio.google.com/apikey",
            parent=self.root,
            show="•",
            initialvalue=self.gemini_api_key,
        )
        if key:
            key = key.strip()
            self.gemini_api_key = key
            self.session.headers.update({"X-goog-api-key": key})
            self.save_config({"api_key": key})
            self.update_status("API key saved")
            self.check_gemini_connection()
        elif not self.gemini_api_key:
            self.update_status("No API key — click 🔑 to add one")

    def check_gemini_connection(self):
        """Check if Gemini API is reachable and list available models"""
        if not self.gemini_api_key:
            self.update_status("No API key — click 🔑 to add one")
            return
        self.update_status("Checking Gemini connection...")
        threading.Thread(target=self.load_available_models, daemon=True).start()

    def load_available_models(self):
        """Load available models from Gemini API"""
        if not self.gemini_api_key:
            self.root.after(0, lambda: self.update_status("No GEMINI_API_KEY set"))
            return
        try:
            response = self.session.get(
                f"{self.gemini_url}/models",
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                models = [
                    m["name"].replace("models/", "")
                    for m in data.get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                ]
                if not models:
                    models = self.available_gemini_models
                self.root.after(0, lambda: self.model_dropdown.config(values=models))
                if self.model not in models:
                    self.model = models[0]
                    self.root.after(0, lambda: self.model_var.set(self.model))
                self.root.after(0, lambda: self.update_status("Connected to Gemini"))
            elif response.status_code in (401, 403):
                self.root.after(0, lambda: self.model_dropdown.config(values=self.available_gemini_models))
                self.root.after(0, lambda: self.update_status("Invalid Gemini API key"))
            else:
                self.root.after(0, lambda: self.model_dropdown.config(values=self.available_gemini_models))
                self.root.after(0, lambda: self.update_status(f"Gemini returned {response.status_code}"))
        except requests.exceptions.ConnectionError:
            self.root.after(0, lambda: self.update_status("Cannot reach Gemini API. Check your internet."))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"Error: {str(e)}"))
    
    def add_message(self, sender, message):
        """Add a message to the chat display"""
        self.chat_display.config(state=tk.NORMAL)
        
        timestamp = datetime.now().strftime("%H:%M")
        
        if sender == "user":
            prefix = f"[{timestamp}] You: "
            color = "#007AFF"
        elif sender == "assistant":
            prefix = f"[{timestamp}] Assistant: "
            color = "#34C759"
        else:
            prefix = ""
            color = "#888888"
        
        self.chat_display.insert(tk.END, prefix, "prefix")
        self.chat_display.insert(tk.END, message + "\n\n", "message")
        
        # Configure tags for colors
        self.chat_display.tag_config("prefix", foreground=color, font=("SF Mono", 11, "bold"))
        self.chat_display.tag_config("message", foreground="#e0e0e0")
        
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def send_message(self):
        """Send message to Gemini"""
        message = self.input_field.get("1.0", tk.END).strip()
        if not message:
            return
        
        # Clear input
        self.input_field.delete("1.0", tk.END)
        
        # Add user message to display
        self.add_message("user", message)
        
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Update status + lock send button to avoid overlapping requests
        self.update_status("Thinking…")
        self.set_busy(True)

        # Send to Gemini in a separate thread
        threading.Thread(target=self.get_gemini_response, args=(message,), daemon=True).start()

    def set_busy(self, busy):
        """Enable/disable the Send button while a request is in flight"""
        state = tk.DISABLED if busy else tk.NORMAL
        text = "…" if busy else "Send  ⏎"
        self.send_button.config(state=state, text=text)

    def get_gemini_response(self, user_message):
        """Get response from Gemini API with streaming (SSE)"""
        try:
            if not self.gemini_api_key:
                error_msg = "No GEMINI_API_KEY set"
                self.root.after(0, lambda: self.update_status(error_msg))
                self.root.after(0, lambda: self.add_message("system", error_msg))
                return

            # Convert conversation history to Gemini "contents" format.
            # role "assistant" -> "model"; each message becomes parts[{text}].
            # Only keep the last N messages to cut input tokens / latency.
            recent = self.conversation_history[-self.max_history_messages:]
            contents = []
            for msg in recent:
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

            payload = {
                "contents": contents,
                "systemInstruction": {"parts": [{"text": self.system_instruction}]},
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2048,
                    # Disable "thinking" on 2.5 models -> big latency drop.
                    # Ignored by models that don't support it.
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            }

            # Make streaming request (Server-Sent Events) over keep-alive session
            response = self.session.post(
                f"{self.gemini_url}/models/{self.model}:streamGenerateContent",
                params={"alt": "sse"},
                json=payload,
                stream=True,
                timeout=300
            )

            if response.status_code == 200:
                # Start streaming the response
                full_response = ""
                self.root.after(0, lambda: self.start_streaming_message())

                for line in response.iter_lines():
                    if not line:
                        continue
                    decoded = line.decode("utf-8")
                    if not decoded.startswith("data:"):
                        continue
                    data_str = decoded[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        json_data = json.loads(data_str)
                        candidates = json_data.get("candidates", [])
                        if not candidates:
                            continue
                        parts = candidates[0].get("content", {}).get("parts", [])
                        content = "".join(p.get("text", "") for p in parts)
                        if content:
                            full_response += content
                            # Update UI with streaming content
                            self.root.after(0, lambda c=content: self.append_to_streaming(c))
                    except json.JSONDecodeError:
                        continue

                # Add complete message to history
                if full_response:
                    self.conversation_history.append({"role": "assistant", "content": full_response})
                    self.root.after(0, lambda: self.finish_streaming_message())
                    self.root.after(0, lambda: self.update_status("Ready"))
                    # Voice output disabled - AI responses are text-only
                else:
                    error_msg = "No response received from model"
                    self.root.after(0, lambda: self.update_status(error_msg))
                    self.root.after(0, lambda: self.add_message("system", error_msg))
            else:
                error_msg = f"Error: {response.status_code} - {response.text[:200]}"
                self.root.after(0, lambda: self.update_status(error_msg))
                self.root.after(0, lambda: self.add_message("system", error_msg))

        except requests.exceptions.Timeout:
            error_msg = "Request timed out. The model might be too slow or not responding."
            self.root.after(0, lambda: self.update_status(error_msg))
            self.root.after(0, lambda: self.add_message("system", error_msg))
        except requests.exceptions.ConnectionError:
            error_msg = "Cannot reach Gemini API. Check your internet connection."
            self.root.after(0, lambda: self.update_status(error_msg))
            self.root.after(0, lambda: self.add_message("system", error_msg))
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.root.after(0, lambda: self.update_status(error_msg))
            self.root.after(0, lambda: self.add_message("system", error_msg))
            import traceback
            print(f"Full error: {traceback.format_exc()}")
        finally:
            # Always unlock the Send button
            self.root.after(0, lambda: self.set_busy(False))

    def start_streaming_message(self):
        """Start a new streaming message in the chat"""
        self.chat_display.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M")
        prefix = f"🤖 Assistant [{timestamp}]\n"
        self.chat_display.insert(tk.END, prefix, "streaming_prefix")
        self.chat_display.tag_config("streaming_prefix", 
                                     foreground="#7c3aed", 
                                     font=("SF Mono", 10, "bold"),
                                     background="#1c2128")
        self.chat_display.config(state=tk.DISABLED)
        self.streaming_message_start = self.chat_display.index(tk.END + "-1c")
    
    def append_to_streaming(self, content):
        """Append content to the streaming message"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, content, "streaming_message")
        self.chat_display.tag_config("streaming_message", 
                                     foreground="#c9d1d9",
                                     font=("SF Mono", 12),
                                     background="#1c2128")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def finish_streaming_message(self):
        """Finish the streaming message"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, "\n\n")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def update_status(self, message):
        """Update status bar"""
        self.status_bar.config(text=message)
    
    def detect_devices(self):
        """List input devices; prefer a loopback driver (system audio)."""
        try:
            names = sr.Microphone.list_microphone_names()
        except Exception:
            names = []
        self.audio_devices = list(enumerate(names))
        # Pick first loopback-style device if available, else system default
        for idx, name in self.audio_devices:
            if any(k in name.lower() for k in self.loopback_keywords):
                return idx
        return None

    def setup_voice(self):
        """Setup voice recognition and text-to-speech"""
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.input_device_index = self.detect_devices()
                self.microphone = sr.Microphone(device_index=self.input_device_index)

                # Tuned for low latency + complete questions:
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.pause_threshold = 0.6        # snappier end-of-phrase
                self.recognizer.non_speaking_duration = 0.3
                self.recognizer.phrase_threshold = 0.2

                # Quick one-time calibration
                self.root.after(0, lambda: self.update_status("🎤 Calibrating audio..."))
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    self.recognizer.energy_threshold *= 0.8

                self.root.after(0, lambda: self.update_status("Ready"))
            except Exception as e:
                print(f"Voice recognition setup error: {e}")
                self.recognizer = None
                self.microphone = None
                self.root.after(0, lambda: self.update_status(f"Voice setup error: {e}"))
        
        if TTS_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
                # Configure TTS voice settings
                voices = self.tts_engine.getProperty('voices')
                if voices:
                    # Try to use a more natural voice
                    self.tts_engine.setProperty('voice', voices[0].id)
                self.tts_engine.setProperty('rate', 150)  # Speech rate
                self.tts_engine.setProperty('volume', 0.8)  # Volume
            except Exception as e:
                print(f"TTS setup error: {e}")
                self.tts_engine = None
    
    def toggle_voice_shortcut(self, event=None):
        """Cmd+D / Ctrl+D handler — toggle mic, swallow default key action."""
        self.toggle_voice_listening()
        return "break"

    def toggle_voice_listening(self):
        """Toggle voice listening on/off"""
        if not SPEECH_RECOGNITION_AVAILABLE or not self.recognizer:
            messagebox.showwarning(
                "Voice Not Available",
                "Speech recognition is not available. Please install: pip install SpeechRecognition pyaudio"
            )
            return
        
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()
    
    def start_listening(self):
        """Start continuous voice listening"""
        if not self.recognizer or not self.microphone:
            messagebox.showwarning(
                "Voice Not Available",
                "Microphone not initialized. Please check your microphone permissions."
            )
            return
        
        self.is_listening = True
        self.voice_button.config(
            text="🔴",
            bg="#da3633",
            activebackground="#f85149"
        )
        src = "system audio" if self.input_device_index is not None and \
            any(k in dict(self.audio_devices).get(self.input_device_index, "").lower()
                for k in self.loopback_keywords) else "microphone"
        self.update_status(f"🎤 Listening to {src}…")

        # Persistent background stream: low latency, non-blocking, no per-phrase
        # stream reopen. Recognition runs in the library's worker thread.
        self.bg_listener_stop = self.recognizer.listen_in_background(
            self.microphone,
            self._on_audio,
            phrase_time_limit=15,
        )

    def _on_audio(self, recognizer, audio):
        """Background callback: transcribe captured audio, then answer it."""
        if not self.is_listening:
            return
        try:
            text = recognizer.recognize_google(audio, language="en-US")
        except sr.UnknownValueError:
            return  # unintelligible — ignore
        except sr.RequestError as e:
            self.root.after(0, lambda: self.update_status(f"Speech API error: {str(e)[:40]}"))
            return
        except Exception:
            return
        if text and text.strip():
            self.root.after(0, lambda t=text: self.process_voice_input(t))

    def stop_listening(self):
        """Stop voice listening"""
        self.is_listening = False
        if self.bg_listener_stop:
            try:
                self.bg_listener_stop(wait_for_stop=False)
            except Exception:
                pass
            self.bg_listener_stop = None
        self.voice_button.config(
            text="🎤",
            bg="#21262d",
            activebackground="#30363d"
        )
        self.update_status("Voice listening stopped")
    
    def process_voice_input(self, text):
        """Process voice input and send to chat"""
        # Clean up the text
        text = text.strip()
        
        if not text or len(text) < 2:
            # Too short, probably not valid
            return
        
        # Add to input field
        self.input_field.delete("1.0", tk.END)
        self.input_field.insert("1.0", text)
        
        # Show what was heard with voice indicator
        self.add_message("user", f"🎤 {text}")
        
        # Update status
        self.update_status("✅ Voice captured - Sending...")
        
        # Send the message
        self.send_message()
    
    def speak_response(self, text):
        """Speak the AI response using text-to-speech"""
        if not TTS_AVAILABLE or not self.tts_engine:
            return
        
        try:
            # Speak in a separate thread to avoid blocking
            def speak():
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            
            threading.Thread(target=speak, daemon=True).start()
        except Exception as e:
            print(f"TTS error: {e}")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = HidebarApp(root)
    
    # Handle window close
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit Hidebar?"):
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()

