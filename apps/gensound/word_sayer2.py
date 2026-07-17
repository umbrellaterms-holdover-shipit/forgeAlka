import os
import time
import random
import numpy as np
from kokoro_onnx import Kokoro
from scipy.io import wavfile

class WordSayerProcessor:
    """Manages randomized phrase selection from an external file context,
    and renders the utterance directly to disk via an in-memory kokoro-onnx instance.
    """
    def __init__(self, wordlist_path="wordlist.txt", audio_target="input_audio.wav", 
                 model_dir="scripts/models", model_name="kokoro-v1.0.onnx", 
                 voices_name="voices-v1.0.bin", voice_name="af_sarah"):
        
        # Resolve assets relative to the location of this script execution file
        base_path = os.curdir
        
        self.wordlist_path = os.path.join(base_path, wordlist_path)
        self.audio_target = os.path.join(base_path, audio_target)
        self.model_path = os.path.join(base_path, model_dir, model_name)
        self.voices_path = os.path.join(base_path, model_dir, voices_name)
        
        self.voice_name = voice_name
        self.tts = None

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

    def _initialize_kokoro(self):
        """Loads the ONNX runtime model files into memory space if not already allocated."""
        if not self.tts:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Missing ONNX model file target at: '{self.model_path}'")
            if not os.path.exists(self.voices_path):
                raise FileNotFoundError(f"Missing voices binary profile target at: '{self.voices_path}'")
                
            print(f"[Kokoro-ONNX] Initializing runtime context using: {self.model_path}")
            self.tts = Kokoro(self.model_path, self.voices_path)

    def _render_with_kokoro(self, text):
        """Generates raw audio via internal ONNX evaluation pipelines and saves to a WAV structure."""
        try:
            self._initialize_kokoro()
            
            if os.path.exists(self.audio_target):
                try:
                    os.remove(self.audio_target)
                except OSError:
                    pass

            print(f"[Kokoro-ONNX] Processing vocal array generation for: \"{text}\"")
            
            # Create outputs flat numpy float32 array along with the model sample rate
            samples, sample_rate = self.tts.create(
                text, 
                voice=self.voice_name, 
                speed=1.0, 
                lang="en-us"
            )
            
            if samples is None or len(samples) == 0:
                print("[Error] Received blank wave matrix back from ONNX runtime evaluation.")
                return False

            # Normalize and scale directly to 16-bit PCM integer depth boundaries
            max_val = np.max(np.abs(samples))
            if max_val > 0:
                scaled_audio = np.int16(samples / max_val * 32767)
            else:
                scaled_audio = np.int16(samples)
            
            wavfile.write(self.audio_target, sample_rate, scaled_audio)
            return True
            
        except Exception as e:
            print(f"[Kokoro-ONNX Error] Local execution failed: {e}")
            return False

    def _play_audio_aloud(self):
        """Plays the rendered WAV file using native platform hooks so the mic listener can hear it."""
        print("[Audio] Broadcasting utterance to environment...")
        if os.name == 'nt':  # Windows
            import winsound
            winsound.PlaySound(self.audio_target, winsound.SND_FILENAME)
        else:  # Mac/Linux platform fallback configurations
            import subprocess
            cmd = ['afplay', self.audio_target] if os.uname().sysname == 'Darwin' else ['aplay', self.audio_target]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def process_and_wait_loop(self):
        """Main execution loop: pulls words, speaks them aloud via Kokoro-ONNX,
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
                
                # 2. Render text to real audio file via pure in-memory execution
                success = self._render_with_kokoro(phrase)
                
                # 3. Play the audio aloud for the microphone listener to pick up
                if success and os.path.exists(self.audio_target):
                    self._play_audio_aloud()
                else:
                    print(f"[Error] Aborting playback for this interval due to rendering failure.")

                # 4. Long cooldown wait before repeating
                sleep_duration = random.uniform(27.0, 279.0)
                print(f"[Loop] Staging next interval. Sleeping for {sleep_duration:.2f} seconds...")
                time.sleep(sleep_duration)
                
        except KeyboardInterrupt:
            print("\n[Sayer] Processing thread terminated cleanly.")

if __name__ == "__main__":
    sayer = WordSayerProcessor(
        wordlist_path="var/wordlist.txt",
        model_dir="scripts/models",
        model_name="kokoro-v1.0.int8.onnx",     # Adjust specific name if using quantized variants
        voices_name="voices-v1.0.bin",
        voice_name="af_sarah"
    )
    sayer.process_and_wait_loop()