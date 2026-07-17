import os
import time
import numpy as np
import pyaudio
from scipy.io import wavfile

class RealTimeLoopRecorder:
    def __init__(self, sample_rate=44100, chunk_size=1024, enable_dump=True, min_dump_duration=5.0):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        
        # Diagnostic & Feature Toggles
        self.enable_dump = enable_dump
        self.min_dump_duration = min_dump_duration  # In seconds
        
        # Target internal frequencies
        self.left_freq = 400.0
        self.right_freq = 404.0
        
        # Independent spatial sliders (0.0 = Hard Left, 1.0 = Hard Right)
        self.left_balance = 0.5
        self.right_balance = 0.5
        
        # Phase tracking variables (continuous)
        self.left_phase = 0.0
        self.right_phase = 0.0
        
        # Precise sample trackers for loop boundaries
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
        
        # 2. Optimized Loop Boundary Detection (Checked block-wise to eliminate choppiness)
        if self.enable_dump and not self.loop_found:
            # Check the boundary point of this specific block chunk
            global_sample_idx = self.total_samples_generated + frame_count
            
            left_cycles = (global_sample_idx * self.left_freq) / self.sample_rate
            right_cycles = (global_sample_idx * self.right_freq) / self.sample_rate
            
            # Using a slightly wider matching tolerance to guarantee hardware locks block-wise
            is_left_integer = np.isclose(left_cycles, round(left_cycles), atol=1e-3)
            is_right_integer = np.isclose(right_cycles, round(right_cycles), atol=1e-3)
            
            if is_left_integer and is_right_integer:
                if self.loop_start_sample is None:
                    self.loop_start_sample = global_sample_idx
                    print(f"\n[Marker] Found initial loop lock point at sample: {global_sample_idx}")
                elif self.loop_end_sample is None:
                    self.loop_end_sample = global_sample_idx
                    self.loop_found = True
                    print(f"[Marker] Perfect geometric loop completed at sample: {global_sample_idx}")

        # 3. Apply independent spatial balance laws
        l_tone_to_L_ear = np.cos(self.left_balance * (np.pi / 2)) * left_raw
        l_tone_to_R_ear = np.sin(self.left_balance * (np.pi / 2)) * left_raw
        
        r_tone_to_L_ear = np.cos(self.right_balance * (np.pi / 2)) * right_raw
        r_tone_to_R_ear = np.sin(self.right_balance * (np.pi / 2)) * right_raw
        
        left_master = l_tone_to_L_ear + r_tone_to_L_ear
        right_master = l_tone_to_R_ear + r_tone_to_R_ear
        
        # Interleave into stereo array block
        stereo_samples = np.empty((frame_count * 2,), dtype=np.float32)
        stereo_samples[0::2] = left_master
        stereo_samples[1::2] = right_master
        
        # Store if file dumping feature is requested
        if self.enable_dump:
            self.recorded_chunks.append(stereo_samples.copy())
            
        self.total_samples_generated += frame_count
        return (stereo_samples.tobytes(), pyaudio.paContinue)

    def start(self):
        self.stream.start_stream()

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        if self.enable_dump:
            self._export_perfect_loop()

    def _export_perfect_loop(self):
        if not self.recorded_chunks:
            print("\n[Diagnostic] No audio frames were cached.")
            return
            
        full_recording = np.concatenate(self.recorded_chunks)
        
        if self.loop_start_sample is not None and self.loop_end_sample is not None:
            print("\nProcessing audio buffers for structural disk write...")
            
            # Map chunk boundaries to structural array positions
            start_arr_idx = self.loop_start_sample * 2
            end_arr_idx = self.loop_end_sample * 2
            
            # Extract basic single-cycle perfect loop segment
            base_loop_slice = full_recording[start_arr_idx:end_arr_idx]
            
            # Calculate duration parameters for analysis
            base_sample_count = (self.loop_end_sample - self.loop_start_sample)
            base_duration = base_sample_count / self.sample_rate
            
            print(f"--- Diagnostic Dump Data ---")
            print(f"Base Single Loop Duration : {base_duration:.4f} seconds")
            print(f"Base Single Loop Samples  : {base_sample_count} samples")
            
            # Minimum length verification logic
            if base_duration < self.min_dump_duration:
                # Calculate necessary repetitions needed to clear the timing threshold
                repetitions = int(np.ceil(self.min_dump_duration / base_duration))
                print(f"File length falls below minimum threshold ({self.min_dump_duration}s).")
                print(f"Duplicating base loop array {repetitions} times...")
                
                # Reshape to keep stereo channel pairs grouped together during structural multiplication
                reshaped_slice = base_loop_slice.reshape(-1, 2)
                duplicated_matrix = np.tile(reshaped_slice, (repetitions, 1))
                final_output_slice = duplicated_matrix.flatten()
            else:
                final_output_slice = base_loop_slice
                repetitions = 1
                
            final_duration = (len(final_output_slice) // 2) / self.sample_rate
            print(f"Final Exported File Runtime: {final_duration:.4f} seconds")
            print(f"----------------------------")
            
            # Prevent digital clipping before integer conversion
            peak = np.max(np.abs(final_output_slice))
            if peak > 0:
                final_output_slice = final_output_slice / peak * 0.95
                
            pcm_data = np.int16(final_output_slice * 32767)
            
            filename = f"perfect_loop_{int(self.left_freq)}Hz_{int(self.right_freq)}Hz.wav"
            wavfile.write(filename, self.sample_rate, pcm_data)
            print(f"Success. Clean loop saved to disk: '{filename}'")
        else:
            print("\n[Diagnostic] Program terminated before a complete block-aligned phase match was verified.")

# --- Demo Execution Block ---
if __name__ == "__main__":
    # Initialize the engine with your diagnostic constraints
    recorder = RealTimeLoopRecorder(
        enable_dump=False,          # Requirement 1: Toggle disk dump feature here
        min_dump_duration=8.0      # Requirement 2: Force minimum duration threshold
    )
    
    recorder.start()
    print("Streaming real-time audio cleanly. Sweeping balances independently...")
    
    try:
        # Run a 6-second execution sweep
        for step in range(60):
            time.sleep(0.1)
            recorder.left_balance = (step / 60.0)
            recorder.right_balance = 1.0 - (step / 60.0)
    finally:
        print("\nHalting hardware engine...")
        recorder.stop()
