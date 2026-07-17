import os
import time
import numpy as np
import pyaudio
from scipy.io import wavfile

class RealTimeLoopRecorder:
    def __init__(self, sample_rate=44100, chunk_size=1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        
        # Target internal parameters (Mutate these anytime from your loop)
        self.left_freq = 400.0
        self.right_freq = 404.0
        
        # Independent spatial sliders (0.0 = Hard Left, 1.0 = Hard Right)
        self.left_balance = 0.5
        self.right_balance = 0.5
        
        # Phase tracking variables (continuous)
        self.left_phase = 0.0
        self.right_phase = 0.0
        
        # Precise sample/cycle trackers for loop detection
        self.total_samples_generated = 0
        self.loop_start_sample = None
        self.loop_end_sample = None
        self.loop_found = False
        
        # Memory buffers to record raw master audio output
        self.recorded_chunks = []
        
        # Audio hardware setup
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
        # 1. Compute individual phase steps per channel
        left_step = 2 * np.pi * self.left_freq / self.sample_rate
        right_step = 2 * np.pi * self.right_freq / self.sample_rate
        
        left_steps = np.arange(frame_count) * left_step + self.left_phase
        right_steps = np.arange(frame_count) * right_step + self.right_phase
        
        left_raw = np.sin(left_steps)
        right_raw = np.sin(right_steps)
        
        # Save continuous phase positions for the next frame boundary
        self.left_phase = (left_steps[-1] + left_step) % (2 * np.pi)
        self.right_phase = (right_steps[-1] + right_step) % (2 * np.pi)
        
        # 2. Check for the absolute geometric loop alignment window
        # We check every sample in this block to see if both waveforms hit zero phase simultaneously
        for i in range(frame_count):
            global_sample_idx = self.total_samples_generated + i
            
            # Theoretical cycle count completed up to this specific sample
            left_cycles = (global_sample_idx * self.left_freq) / self.sample_rate
            right_cycles = (global_sample_idx * self.right_freq) / self.sample_rate
            
            # Check if both are matching integers down to a reasonable floating point limit
            if not self.loop_found and global_sample_idx > 0:
                is_left_integer = np.isclose(left_cycles, round(left_cycles), atol=1e-5)
                is_right_integer = np.isclose(right_cycles, round(right_cycles), atol=1e-5)
                
                if is_left_integer and is_right_integer:
                    if self.loop_start_sample is None:
                        self.loop_start_sample = global_sample_idx
                        print(f"\n[Marker] Found initial loop lock point at sample: {global_sample_idx}")
                    elif self.loop_end_sample is None:
                        self.loop_end_sample = global_sample_idx
                        self.loop_found = True
                        print(f"[Marker] Perfect geometric loop completed at sample: {global_sample_idx}")
                        print(f"-> Total Loop Length: {self.loop_end_sample - self.loop_start_sample} samples")

        # 3. Apply independent spatial balance laws (constant-power matrix layout)
        # Left Tone positioning
        l_tone_to_L_ear = np.cos(self.left_balance * (np.pi / 2)) * left_raw
        l_tone_to_R_ear = np.sin(self.left_balance * (np.pi / 2)) * left_raw
        
        # Right Tone positioning
        r_tone_to_L_ear = np.cos(self.right_balance * (np.pi / 2)) * right_raw
        r_tone_to_R_ear = np.sin(self.right_balance * (np.pi / 2)) * right_raw
        
        # Combine onto structural output channels
        left_master = l_tone_to_L_ear + r_tone_to_L_ear
        right_master = l_tone_to_R_ear + r_tone_to_R_ear
        
        # Interleave into stereo array block
        stereo_samples = np.empty((frame_count * 2,), dtype=np.float32)
        stereo_samples[0::2] = left_master
        stereo_samples[1::2] = right_master
        
        # Track master buffer stream in memory for file export
        self.recorded_chunks.append(stereo_samples.copy())
        self.total_samples_generated += frame_count
        
        return (stereo_samples.tobytes(), pyaudio.paContinue)

    def start(self):
        self.stream.start_stream()

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        self._export_perfect_loop()

    def _export_perfect_loop(self):
        if not self.recorded_chunks:
            return
            
        # Concatenate memory blocks into one continuous array layout
        full_recording = np.concatenate(self.recorded_chunks)
        
        if self.loop_start_sample is not None and self.loop_end_sample is not None:
            print("\nProcessing audio buffers for structural disk write...")
            
            # Map global sample offsets directly to interleaved array indices (multiply by 2 for stereo)
            start_arr_idx = self.loop_start_sample * 2
            end_arr_idx = self.loop_end_sample * 2
            
            # Extract the absolute perfect looping block window
            loop_slice = full_recording[start_arr_idx:end_arr_idx]
            
            # Prevent digital clipping before conversion to 16-bit integers
            peak = np.max(np.abs(loop_slice))
            if peak > 0:
                loop_slice = loop_slice / peak * 0.95
                
            pcm_data = np.int16(loop_slice * 32767)
            
            filename = f"perfect_loop_{int(self.left_freq)}Hz_{int(self.right_freq)}Hz.wav"
            wavfile.write(filename, self.sample_rate, pcm_data)
            print(f"Success. Perfect seamless loop saved to disk: '{filename}'")
        else:
            print("\nProgram ended before a complete geometric cycle match was hit. No file generated.")

# --- Demo Execution Block ---
if __name__ == "__main__":
    recorder = RealTimeLoopRecorder()
    recorder.start()
    
    print("Streaming real-time audio. Sweeping balance paths independently...")
    try:
        # Run a 12-second real-time sweep showcase
        for step in range(120):
            time.sleep(0.1)
            
            # Sweep the left tone smoothly from hard left to right
            recorder.left_balance = (step / 120.0)
            
            # Sweep the right tone smoothly from hard right to left
            recorder.right_balance = 1.0 - (step / 120.0)
            
    finally:
        print("\nHalting streaming hardware engine...")
        recorder.stop()
        
