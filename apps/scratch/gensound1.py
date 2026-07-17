import time
import numpy as np
import pyaudio

class RealTimeToneGenerator:
    def __init__(self, sample_rate=44100, chunk_size=1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        
        # Runtime parameters (can be updated dynamically from another thread)
        self.left_freq = 400.0
        self.right_freq = 404.0
        self.balance = 0.5  # 0.0 to 1.0
        
        # Phase accumulators to maintain perfect waveform continuity between blocks
        self.left_phase = 0.0
        self.right_phase = 0.0
        
        # Initialize PyAudio
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback
        )

    def _audio_callback(self, in_data, frame_count, time_info, status):
        # 1. Compute phase step size per sample based on current frequencies
        left_step = 2 * np.pi * self.left_freq / self.sample_rate
        right_step = 2 * np.pi * self.right_freq / self.sample_rate
        
        # 2. Generate arrays of relative phase steps for this specific chunk
        left_steps = np.arange(frame_count) * left_step + self.left_phase
        right_steps = np.arange(frame_count) * right_step + self.right_phase
        
        # 3. Compute sine waves
        left_samples = np.sin(left_steps)
        right_samples = np.sin(right_steps)
        
        # 4. Save the ending phase for the next block boundary (modulo 2*pi to prevent float drift)
        self.left_phase = (left_steps[-1] + left_step) % (2 * np.pi)
        self.right_phase = (right_steps[-1] + right_step) % (2 * np.pi)
        
        # 5. Apply constant-power balance gains
        left_gain = np.cos(self.balance * (np.pi / 2))
        right_gain = np.sin(self.balance * (np.pi / 2))
        
        left_samples *= left_gain
        right_samples *= right_gain
        
        # 6. Interleave left and right samples into a stereo array
        stereo_samples = np.empty((frame_count * 2,), dtype=np.float32)
        stereo_samples[0::2] = left_samples
        stereo_samples[1::2] = right_samples
        
        return (stereo_samples.tobytes(), pyaudio.paContinue)

    def start(self):
        self.stream.start_stream()

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

# Example Demonstration
if __name__ == "__main__":
    generator = RealTimeToneGenerator()
    generator.start()
    
    print("Playing real-time tones. Modifying parameters on the fly without clicks...")
    try:
        # Shift parameters mid-playback to demonstrate seamless transitioning
        time.sleep(3)
        print("Changing frequencies...")
        generator.left_freq = 300.0
        generator.right_freq = 305.0
        
        time.sleep(3)
        print("Panning hard left...")
        generator.balance = 0.0
        
        time.sleep(2)
        print("Panning hard right...")
        generator.balance = 1.0
        
        time.sleep(2)
    finally:
        generator.stop()
        print("Playback stopped.")
