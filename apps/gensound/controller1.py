import os
import json
import time
import random
import numpy as np
import pyaudio
from scipy.signal import find_peaks

class EnvironmentListener:
    """Monitors background audio, captures pitch boundaries on threshold cross,
    calculates algorithmic frequency offsets, and updates the configuration.
    """
    def __init__(self, output_dir="var", config_name="oscillators.json", noise_floor=0.015, sample_rate=44100, chunk_size=2048):
        self.output_dir = output_dir
        self.config_path = os.path.join(self.output_dir, config_name)
        self.lock_path = self.config_path + ".lock"
        
        self.noise_floor = noise_floor
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        
        # Audio interface states
        self.p = None
        self.stream = None
        
        # Audio bounds limits
        self.min_hearing_bound = 44.0
        self.max_hearing_bound = 444.0
        
        # Current baseline tracking targets
        self.current_left_freq = 440.0
        self.current_right_freq = 440.0
        self.current_amp = 0.0
        
        os.makedirs(self.output_dir, exist_ok=True)
        self._ensure_baseline_config()

    def _ensure_baseline_config(self):
        if not os.path.exists(self.config_path):
            initial_data = [
                {"id": "pitch_node_left", "frequency": 440.0, "balance": 0.0, "amplitude": 0.0},
                {"id": "pitch_node_right", "frequency": 440.0, "balance": 1.0, "amplitude": 0.0}
            ]
            self._safe_write_config(initial_data)

    def _safe_write_config(self, data):
        with open(self.lock_path, "w") as lock:
            lock.write("LOCKED")
        try:
            with open(self.config_path, "w") as f:
                json.dump(data, f, indent=2)
        finally:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)

    def _detect_pitch(self, audio_data):
        signal = audio_data - np.mean(audio_data)
        norm = np.sum(signal**2)
        if norm == 0:
            return None
            
        corr = np.correlate(signal, signal, mode='full')
        corr = corr[len(corr)//2:]
        
        peaks, _ = find_peaks(corr, distance=20)
        valid_peaks = peaks[peaks > 0]
        if len(valid_peaks) == 0:
            return None
            
        best_peak = valid_peaks[np.argmax(corr[valid_peaks])]
        freq = self.sample_rate / best_peak
        
        if 60.0 <= freq <= 2000.0:
            return freq
        return None

    def _capture_window(self, duration):
        pitches = []
        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                raw_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                audio_block = np.frombuffer(raw_data, dtype=np.float32)
            except IOError:
                continue
                
            pitch = self._detect_pitch(audio_block)
            if pitch is not None:
                pitches.append(pitch)
        return pitches

    def _process_algorithmic_math(self, min_p, max_p):
        """Anchors the matrix onto the lower detected tone and selects a clean 
        binaural offset based on the final digit of the maximum pitch boundary.
        """
        # Step 1: Establish the stable anchor tone
        anchor_freq = (min_p+max_p)/2

        # Step 2: Define target brainwave state deltas
        # Alpha (10 Hz), Beta (20 Hz), Gamma (40 Hz), Delta (2.5 Hz), Theta (5 Hz)
        binaural_deltas = [10.0, 20.0, 40.0, 2.5, 5.0]

        # Step 3: Extract the last integer digit of max_p as the index selector
        selector_digit = int(abs(max_p)) % 10
        
        # Map the 0-9 single digit down to our 5 available options via modulo
        delta_index = selector_digit % len(binaural_deltas)
        chosen_delta = binaural_deltas[delta_index]
        print(f"Next up:a {['Alpha', 'Beta', 'Gamma', 'Delta', 'Theta'][delta_index]} wave!")

        # Step 4: Construct the left and right channel frequency matrix
        # Left channel holds the baseline anchor; right channel provides the offset
        left_target = anchor_freq
        right_target = anchor_freq + chosen_delta

        # Step 5: Keep targets bounded within strict human hearing limits
        bound_span = self.max_hearing_bound - self.min_hearing_bound
        left_target = self.min_hearing_bound + ((left_target - self.min_hearing_bound) % bound_span)
        right_target = self.min_hearing_bound + ((right_target - self.min_hearing_bound) % bound_span)

        return round(left_target, 2), round(right_target, 2)


    def start(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            input_device_index=0
        )
        
        print(f"[Listener] Monitoring environment. Noise floor threshold: {self.noise_floor}")
        try:
            while True:
                try:
                    raw_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_block = np.frombuffer(raw_data, dtype=np.float32)
                except IOError:
                    continue

                if np.sqrt(np.mean(audio_block**2)) > self.noise_floor:
                    wait_duration = random.uniform(3.0, 30.0)
                    print(f"\n[Trigger] Analysis window open. Monitoring for {wait_duration:.2f}s...")
                    
                    pitches = self._capture_window(wait_duration)
                    
                    if pitches:
                        min_detected = min(pitches)
                        max_detected = max(pitches)
                        print(f"[Captured Data] Min: {min_detected:.2f}Hz | Max: {max_detected:.2f}Hz")
                        
                        # Process mathematical targets matrix
                        self.current_left_freq, self.current_right_freq = self._process_algorithmic_math(min_detected, max_detected)
                        self.current_amp = 0.95
                        print(f"[Calculated Matrix] Target Left: {self.current_left_freq}Hz | Target Right: {self.current_right_freq}Hz")
                    else:
                        self.current_amp = 0.0
                        print("[Update] No stable pitch tracking achieved. Dropping amplitude.")

                    payload = [
                        {"id": "pitch_node_left", "frequency": self.current_left_freq, "balance": 0.0, "amplitude": self.current_amp},
                        {"id": "pitch_node_right", "frequency": self.current_right_freq, "balance": 1.0, "amplitude": self.current_amp}
                    ]
                    self._safe_write_config(payload)
                    
        except KeyboardInterrupt:
            print("\n[Listener] Halting safely.")
        finally:
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()

if __name__ == "__main__":
    listener = EnvironmentListener()
    listener.start()
