#!/usr/bin/env python3
"""
Hidebar - A private local AI assistant using Ollama
Hidden from screen sharing and runs entirely on your local machine
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
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
        
        # Ollama configuration
        self.ollama_url = "http://localhost:11434"
        self.model = "llama3.2:latest"  # Default model, can be changed
        self.conversation_history = []
        self.streaming_message_start = None
        
        # Voice recognition setup
        self.is_listening = False
        self.recognizer = None
        self.microphone = None
        self.tts_engine = None
        self.setup_voice()
        
        # Setup UI
        self.setup_ui()
        
        # Keep window on top periodically
        self.keep_on_top()
        
        # Check Ollama connection
        self.check_ollama_connection()
    
    def setup_multi_space(self):
        """Setup window to appear on all spaces and screens"""
        try:
            import subprocess
            import threading
            
            def set_space_behavior():
                """Set window to appear on all spaces"""
                window_title = self.root.title()
                pid = os.getpid()
                
                # Wait for window to be fully created
                import time
                time.sleep(0.5)
                
                # AppleScript to set window collection behavior
                applescript = f'''
                tell application "System Events"
                    set targetProcs to (every process whose unix id is {pid})
                    repeat with appProc in targetProcs
                        try
                            set windowList to (every window of appProc whose name contains "{window_title}")
                            repeat with aWindow in windowList
                                try
                                    -- Set window to appear on all spaces
                                    set value of attribute "AXFullScreen" of aWindow to false
                                    -- Make it visible on all spaces
                                    set value of attribute "AXMinimized" of aWindow to false
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
                    timeout=2
                )
                
                # Try using pyobjc for more reliable multi-space support
                try:
                    import objc
                    from AppKit import NSWindow, NSWindowCollectionBehavior
                    from Cocoa import NSWindowCollectionBehaviorCanJoinAllSpaces
                    
                    def set_collection_behavior():
                        app = objc.objc_getClass('NSApplication').sharedApplication()
                        windows = app.windows()
                        for window in windows:
                            if window.title() == window_title:
                                # Make window appear on all spaces
                                behavior = window.collectionBehavior()
                                behavior |= NSWindowCollectionBehaviorCanJoinAllSpaces
                                window.setCollectionBehavior_(behavior)
                                # Keep it on top
                                window.setLevel_(NSWindow.NSFloatingWindowLevel)
                                break
                    
                    # Run on main thread
                    self.root.after(500, set_collection_behavior)
                except (ImportError, AttributeError):
                    pass
            
            # Run in background thread
            threading.Thread(target=set_space_behavior, daemon=True).start()
            
        except Exception as e:
            print(f"Multi-space setup note: {e}")
    
    def keep_on_top(self):
        """Periodically ensure window stays on top across all screens"""
        self.root.attributes('-topmost', True)
        self.root.lift()
        
        # Also ensure it's visible on current screen
        if sys.platform == "darwin":
            try:
                # Keep window on top and ensure it's on the active screen
                self.root.update_idletasks()
            except:
                pass
        
        # Check every 2 seconds to ensure it stays on top
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
        
        def hide_window_loop():
            """Continuously hide the window from screen sharing using AppleScript only"""
            window_title = self.root.title()
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
        
        # Subtitle
        subtitle_label = tk.Label(
            title_container,
            text="Private AI Assistant",
            font=("SF Pro Display", 10),
            bg="#161b22",
            fg="#8b949e"
        )
        subtitle_label.pack(side=tk.LEFT, padx=(10, 0))
        
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
        
        # Voice button with modern design
        self.voice_button = tk.Button(
            button_frame,
            text="🎤",
            command=self.toggle_voice_listening,
            bg="#238636" if not self.is_listening else "#da3633",
            fg="#ffffff",
            font=("SF Pro Display", 18),
            relief=tk.FLAT,
            padx=18,
            pady=12,
            cursor="hand2",
            activebackground="#2ea043" if not self.is_listening else "#f85149",
            activeforeground="#ffffff",
            borderwidth=0
        )
        self.voice_button.pack(side=tk.TOP, pady=(0, 8))
        
        # Send button with modern design
        send_button = tk.Button(
            button_frame,
            text="Send",
            command=self.send_message,
            bg="#238636",
            fg="#ffffff",
            font=("SF Pro Display", 12, "bold"),
            relief=tk.FLAT,
            padx=24,
            pady=12,
            cursor="hand2",
            activebackground="#2ea043",
            activeforeground="#ffffff",
            borderwidth=0
        )
        send_button.pack(side=tk.TOP)
        
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
        self.add_message("system", "👋 Welcome to Hidebar! Your private local AI assistant.\n\n💡 You can type messages or use the microphone button to speak.\n\n🔒 All processing happens locally on your machine.")
    
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
    
    def check_ollama_connection(self):
        """Check if Ollama is running and get available models"""
        self.update_status("Checking Ollama connection...")
        threading.Thread(target=self.load_available_models, daemon=True).start()
    
    def load_available_models(self):
        """Load available models from Ollama"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models_data = response.json()
                models = [model["name"] for model in models_data.get("models", [])]
                if models:
                    self.root.after(0, lambda: self.model_dropdown.config(values=models))
                    if self.model not in models and models:
                        self.model = models[0]
                        self.root.after(0, lambda: self.model_var.set(self.model))
                    self.root.after(0, lambda: self.update_status("Connected to Ollama"))
                else:
                    self.root.after(0, lambda: self.update_status("No models found. Please pull a model first."))
            else:
                self.root.after(0, lambda: self.update_status("Ollama returned an error"))
        except requests.exceptions.ConnectionError:
            self.root.after(0, lambda: self.update_status("Cannot connect to Ollama. Make sure it's running on localhost:11434"))
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
        """Send message to Ollama"""
        message = self.input_field.get("1.0", tk.END).strip()
        if not message:
            return
        
        # Clear input
        self.input_field.delete("1.0", tk.END)
        
        # Add user message to display
        self.add_message("user", message)
        
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Update status
        self.update_status("Thinking...")
        
        # Send to Ollama in a separate thread
        threading.Thread(target=self.get_ollama_response, args=(message,), daemon=True).start()
    
    def get_ollama_response(self, user_message):
        """Get response from Ollama API with streaming"""
        try:
            # Prepare the request with streaming enabled
            payload = {
                "model": self.model,
                "messages": self.conversation_history,
                "stream": True
            }
            
            # Make streaming request
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                stream=True,
                timeout=300
            )
            
            if response.status_code == 200:
                # Start streaming the response
                full_response = ""
                self.root.after(0, lambda: self.start_streaming_message())
                
                for line in response.iter_lines():
                    if line:
                        try:
                            json_data = json.loads(line.decode('utf-8'))
                            content = json_data.get("message", {}).get("content", "")
                            if content:
                                full_response += content
                                # Update UI with streaming content
                                self.root.after(0, lambda c=content: self.append_to_streaming(c))
                            
                            # Check if done
                            if json_data.get("done", False):
                                break
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
            error_msg = "Cannot connect to Ollama. Make sure it's running."
            self.root.after(0, lambda: self.update_status(error_msg))
            self.root.after(0, lambda: self.add_message("system", error_msg))
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.root.after(0, lambda: self.update_status(error_msg))
            self.root.after(0, lambda: self.add_message("system", error_msg))
            import traceback
            print(f"Full error: {traceback.format_exc()}")
    
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
    
    def setup_voice(self):
        """Setup voice recognition and text-to-speech"""
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                
                # Better ambient noise adjustment
                self.root.after(0, lambda: self.update_status("🎤 Calibrating microphone..."))
                with self.microphone as source:
                    # Longer calibration for better accuracy
                    self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
                    # Set energy threshold dynamically
                    self.recognizer.energy_threshold = self.recognizer.energy_threshold * 0.8
                
                # Configure recognizer for better accuracy
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.pause_threshold = 0.8  # Pause before considering phrase complete
                
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
        self.update_status("🎤 Listening... Speak clearly")
        
        # Recalibrate for current environment
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
        except:
            pass
        
        # Start listening in a separate thread
        threading.Thread(target=self.listen_continuously, daemon=True).start()
    
    def stop_listening(self):
        """Stop voice listening"""
        self.is_listening = False
        self.voice_button.config(
            text="🎤",
            bg="#34C759",
            activebackground="#28A745"
        )
        self.update_status("Voice listening stopped")
    
    def listen_continuously(self):
        """Continuously listen for voice input with improved accuracy"""
        consecutive_errors = 0
        max_errors = 5
        
        while self.is_listening:
            try:
                with self.microphone as source:
                    # Improved listening parameters
                    # Longer timeout to catch speech better
                    # Longer phrase_time_limit to capture complete sentences
                    audio = self.recognizer.listen(
                        source, 
                        timeout=2,  # Increased from 1 to 2 seconds
                        phrase_time_limit=10  # Increased from 5 to 10 seconds for longer phrases
                    )
                
                # Update status to show processing
                self.root.after(0, lambda: self.update_status("🔍 Processing speech..."))
                
                try:
                    # Try Google's speech recognition first (most accurate)
                    text = self.recognizer.recognize_google(audio, language='en-US')
                    
                    if text and len(text.strip()) > 0:
                        # Reset error counter on success
                        consecutive_errors = 0
                        
                        # Add to input field and send
                        self.root.after(0, lambda t=text: self.process_voice_input(t))
                        
                        # Brief pause before listening again
                        import time
                        time.sleep(0.3)
                        
                except sr.UnknownValueError:
                    # Could not understand audio - this is normal, just continue
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        self.root.after(0, lambda: self.update_status("🎤 Listening... (speak louder or clearer)"))
                        consecutive_errors = 0
                    continue
                    
                except sr.RequestError as e:
                    # Network or API error
                    consecutive_errors += 1
                    error_msg = f"Speech API error: {str(e)[:50]}"
                    self.root.after(0, lambda: self.update_status(error_msg))
                    
                    if consecutive_errors >= max_errors:
                        self.root.after(0, lambda: self.update_status("🎤 Listening... (check internet connection)"))
                        consecutive_errors = 0
                    
                    # Wait a bit before retrying
                    import time
                    time.sleep(1)
                    continue
                    
            except sr.WaitTimeoutError:
                # Timeout - this is normal, just continue listening
                continue
                
            except Exception as e:
                if self.is_listening:
                    consecutive_errors += 1
                    error_msg = f"Error: {str(e)[:40]}"
                    self.root.after(0, lambda: self.update_status(error_msg))
                    
                    if consecutive_errors >= max_errors:
                        # Too many errors, try to recalibrate
                        try:
                            with self.microphone as source:
                                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                            consecutive_errors = 0
                            self.root.after(0, lambda: self.update_status("🎤 Recalibrated - Listening..."))
                        except:
                            pass
                    
                    # Wait before retrying
                    import time
                    time.sleep(0.5)
                else:
                    break
    
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

