import time
import numpy as np
import pyaudio

def create_looping_buffer(left_freq, right_freq, sample_rate=44100, target_duration=60.0):
    """
    Generates a stereo buffer where both channels complete an exact integer 
    number of cycles, guaranteeing a click-free loop boundary.
    """
    num_samples = int(round(target_duration * sample_rate))
    actual_duration = num_samples / sample_rate
    
    # Force alignment to integer cycle counts to prevent sub-sample boundary drift
    left_cycles = round(actual_duration * left_freq)
    right_cycles = round(actual_duration * right_freq)
    
    adjusted_left_freq = left_cycles / actual_duration
    adjusted_right_freq = right_cycles / actual_duration
    
    t = np.arange(num_samples) / sample_rate
    
    left_channel = np.sin(2 * np.pi * adjusted_left_freq * t)
    right_channel = np.sin(2 * np.pi * adjusted_right_freq * t)
    
    stereo_buffer = np.empty((num_samples * 2,), dtype=np.float32)
    stereo_buffer[0::2] = left_channel
    stereo_buffer[1::2] = right_channel
    
    return stereo_buffer, num_samples

class LoopPlaybackManager:
    def __init__(self, sample_rate=44100, chunk_size=1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.current_buffer = None
        self.buffer_samples = 0
        self.playback_index = 0  
        self.balance = 0.5  # Dynamic balance property (0.0 to 1.0)
        
        # Initialize PyAudio infrastructure
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback
        )
        
    def load_combination(self, left_freq, right_freq):
        """Pre-generates the loop and stores it in memory."""
        self.current_buffer, self.buffer_samples = create_looping_buffer(
            left_freq, right_freq, self.sample_rate
        )
        
    def _audio_callback(self, in_data, frame_count, time_info, status):
        if self.current_buffer is None:
            silence = np.zeros(frame_count * 2, dtype=np.float32)
            return (silence.tobytes(), pyaudio.paContinue)
            
        start_idx = self.playback_index % self.buffer_samples
        end_idx = start_idx + frame_count
        
        if end_idx <= self.buffer_samples:
            chunk = self.current_buffer[start_idx * 2 : end_idx * 2].copy()
        else:
            overflow = end_idx - self.buffer_samples
            part1 = self.current_buffer[start_idx * 2 :]
            part2 = self.current_buffer[0 : overflow * 2]
            chunk = np.concatenate((part1, part2))
            
        # Apply constant-power panning laws to the extracted chunk on the fly
        left_gain = np.cos(self.balance * (np.pi / 2))
        right_gain = np.sin(self.balance * (np.pi / 2))
        
        chunk[0::2] *= left_gain
        chunk[1::2] *= right_gain
        
        self.playback_index = (self.playback_index + frame_count) % self.buffer_samples
        return (chunk.tobytes(), pyaudio.paContinue)

    def start(self):
        """Activates the audio hardware processing stream."""
        self.stream.start_stream()

    def stop(self):
        """Gracefully halts the audio hardware streams and cleans up memory allocations."""
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

# --- Execution Block ---
if __name__ == "__main__":
    # Initialize the runtime manager
    manager = LoopPlaybackManager()
    
    # Pre-generate and cache the initial configuration in memory
    print("Pre-rendering 60-second perfect loop into memory...")
    manager.load_combination(left_freq=400.0, right_freq=404.0)
    
    # Start playback explicitly
    manager.start()
    print("Playback active. Running pre-rendered loop with cheap real-time balance mixing.")
    
    try:
        # Run execution loop, altering the balance parameter on the fly
        time.sleep(3)
        print("Moving balance toward the left (0.1)...")
        manager.balance = 0.1
        
        time.sleep(3)
        print("Moving balance toward the right (0.9)...")
        manager.balance = 0.9
        
        time.sleep(4)
    finally:
        manager.stop()
        print("Playback engine terminated.")
