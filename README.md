# Hidebar

A private, local AI assistant using Ollama that runs entirely on your computer and is designed to be hidden from screen sharing.

## Features

- 🤖 **Local AI**: Uses Ollama for completely local AI inference - no data leaves your machine
- 🔒 **Private**: Designed to be hidden from screen sharing
- 💬 **Chat Interface**: Clean, modern chat interface similar to Cluely
- 🎨 **Dark Theme**: Easy on the eyes with a sleek dark interface
- ⚡ **Fast**: Direct connection to local Ollama instance
- 🎤 **Voice Input**: Speak to the AI using your microphone
- 🔊 **Voice Output**: AI responses are spoken aloud (when voice listening is active)
- 📌 **Always on Top**: Window stays pinned on top of all screens
- 🌫️ **Transparent**: Semi-transparent window that stays visible

## Prerequisites

1. **Python 3.7+** installed on your system
2. **Ollama** installed and running locally
   - Download from: https://ollama.ai
   - Make sure Ollama is running: `ollama serve`
   - Pull at least one model: `ollama pull llama2` (or any other model)

## Installation

1. Navigate to the hide directory:
   ```bash
   cd hide
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. **For voice features** (optional but recommended):
   - On macOS, you may need to install PortAudio for PyAudio:
     ```bash
     brew install portaudio
     ```
   - Then install the voice dependencies:
     ```bash
     pip install SpeechRecognition pyaudio pyttsx3
     ```
   - Grant microphone permissions in System Settings > Privacy & Security > Microphone

## Usage

1. Make sure Ollama is running:
   ```bash
   ollama serve
   ```

2. Run Hidebar:
   ```bash
   python Hidebar.py
   ```

3. The application will:
   - Connect to your local Ollama instance
   - Display available models
   - Allow you to chat with the AI

4. **Using Voice Features**:
   - Click the 🎤 button to start voice listening
   - Speak your question - it will be transcribed and sent to the AI
   - When the AI responds, it will be spoken aloud automatically
   - Click 🔴 to stop voice listening

## Configuration

- **Ollama URL**: Default is `http://localhost:11434`. You can modify this in `Hidebar.py` if your Ollama runs on a different port.
- **Default Model**: The app defaults to `llama2`, but you can select any available model from the dropdown.

## Privacy Notes

- The app attempts to hide from screen sharing using macOS accessibility features
- All AI processing happens locally - no data is sent to external servers
- Conversation history is stored only in memory (cleared when app closes)

### Screen Sharing Protection

The app includes a background process that attempts to hide the window from screen sharing. For best results:

1. **Install pyobjc** (optional, for better hiding):
   ```bash
   pip install pyobjc
   ```

2. **Grant Accessibility Permissions**:
   - Go to System Settings > Privacy & Security > Accessibility
   - Add Terminal (or your terminal app) to the allowed list
   - This allows the app to modify window properties

3. **Note**: Screen sharing hiding may not work perfectly on all macOS versions. The app uses AppleScript to attempt to exclude the window from screen capture, but this depends on macOS accessibility features.

If the window still appears in screen sharing, you may need to:
- Use a different windowing approach (requires code changes)
- Manually minimize/hide the window during screen sharing
- Use macOS's built-in "Do Not Disturb" or screen sharing controls

## Troubleshooting

### "Cannot connect to Ollama"
- Make sure Ollama is running: `ollama serve`
- Check that Ollama is running on the default port (11434)

### "No models found"
- Pull a model first: `ollama pull llama2`
- Or pull other models like: `ollama pull mistral`, `ollama pull codellama`

### Model not responding
- Some models may take longer to respond
- Try a smaller/faster model if responses are too slow

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- Built with [Ollama](https://ollama.ai) for local AI inference
- Uses [SpeechRecognition](https://github.com/Uberi/speech_recognition) for voice input
- Inspired by modern AI assistants like Cluely

