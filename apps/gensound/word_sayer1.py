import os
import time
import random
import pyttsx3
from faster_whisper import WhisperModel

class WordSayerProcessor:
    """Manages randomized phrase selection from an external file context,
    renders the utterance to a local audio track via offline TTS, plays it, 
    and verifies the audio state using a local Whisper model.
    """
    def __init__(self, wordlist_path="wordlist.txt", model_dir="models/whisper-tiny-en-ct2", audio_target="input_audio.wav"):
        self.wordlist_path = wordlist_path
        self.model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), model_dir)
        self.audio_target = audio_target
        
        # Lazy-loaded engine slots
        self.model = None
        self.tts_engine = None

    def _load_wordlist(self):
        """Reads external dictionary file, raising an error if missing."""
        if not os.path.exists(self.wordlist_path):
            raise FileNotFoundError(f"The external dictionary file '{self.wordlist_path}' does not exist.")
            
        with open(self.wordlist_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    def _generate_utterance(self, words):
        """Extracts 1 to 3 words randomly to compile a phrase string."""
        count = random.randint(1, 3)
        selected = random.sample(words, min(count, len(words)))
        return " ".join(selected)

    def _initialize_model(self):
        """Instantiates the Whisper loop within strict local resource parameters."""
        if not self.model:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Local model layout missing at: {self.model_path}")
            
            print(f"[Model] Initializing local Whisper context from {self.model_path}...")
            self.model = WhisperModel(
                self.model_path,
                device="cpu",
                compute_type="int8",
                local_files_only=True
            )

    def _speak_to_file(self, text):
        """Uses local native TTS to compile the text string directly into a physical WAV file."""
        if not self.tts_engine:
            self.tts_engine = pyttsx3.init()
            # Optional: adjust rate slightly slower for clearer offline processing
            self.tts_engine.setProperty('rate', 145) 
            
        print(f"[TTS] Rendering phrase text to physical master track: '{self.audio_target}'")
        
        # Remove old artifact if it exists to ensure a fresh write
        if os.path.exists(self.audio_target):
            os.remove(self.audio_target)
            
        self.tts_engine.save_to_file(text, self.audio_target)
        self.tts_engine.runAndWait()
        
        # Give the OS file system a brief window to flush the file handle to disk
        time.sleep(0.2)

    def _play_audio_aloud(self):
        """Plays the rendered WAV file using native platform hooks so the mic listener can hear it."""
        print("[Audio] Broadcasting utterance to environment...")
        if os.name == 'nt': # Windows
            import winsound
            winsound.PlaySound(self.audio_target, winsound.SND_FILENAME)
        else: # Mac/Linux fallback system calls
            import subprocess
            cmd = ['afplay', self.audio_target] if os.uname().sysname == 'Darwin' else ['aplay', self.audio_target]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def process_and_wait_loop(self):
        """Main execution loop: pulls words, speaks them aloud, validates with Whisper, 
        and undergoes designated 27 to 279 second interval waits.
        """
        print("[Sayer] Initializing phrase engine loop...")
        try:
            words = self._load_wordlist()
        except FileNotFoundError as e:
            print(f"[Error] {e}")
            return

        try:
            while True:
                # 1. Select the random phrase
                phrase = self._generate_utterance(words)
                print(f"\n[Utterance Selection] -> \"{phrase}\"")
                
                # 2. Render text to real audio file
                self._speak_to_file(phrase)
                
                # 3. Play the audio aloud for the microphone to pick up
                if os.path.exists(self.audio_target):
                    self._play_audio_aloud()
                    
                    # 4. Use Whisper to verify the file content
                    try:
                        self._initialize_model()
                        print(f"[Model] Verifying audio track composition...")
                        segments, _ = self.model.transcribe(self.audio_target)
                        
                        print("--- Verified Transcription Blocks ---")
                        for segment in segments:
                            print(f"[{segment.start:.2f}s -> {segment.end:.2f}s]: {segment.text}")
                    except Exception as e:
                        print(f"[Model Error] Failed parsing session audio: {e}")
                else:
                    print(f"[Error] Failed to generate target audio asset '{self.audio_target}'.")

                # 5. Long cooldown wait before repeating
                sleep_duration = random.uniform(27.0, 39.0)
                print(f"[Loop] Staging next interval. Sleeping for {sleep_duration:.2f} seconds...")
                time.sleep(sleep_duration)
                
        except KeyboardInterrupt:
            print("\n[Sayer] Processing thread terminated cleanly.")

if __name__ == "__main__":
    sayer = WordSayerProcessor(wordlist_path="var/wordlist.txt")
    sayer.process_and_wait_loop()
