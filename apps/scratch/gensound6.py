import time
import json
import os
import threading
import numpy as np
import pyaudio
from scipy.io import wavfile


class WaveOscillator:
    """Manages continuous phase signal generation with smooth parameter tracking."""
    def __init__(self, osc_id, frequency=400.0, balance=0.5, amplitude=0.0, sample_rate=44100):
        self.id = osc_id
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.phase = 0.0
        
        # Targets mutated dynamically by the file watcher
        self.balance = balance       
        self.amplitude = amplitude   
        
        # Internal states for click-free interpolation (lerping)
        self._current_balance = balance
        self._current_amplitude = amplitude

    def generate_block(self, frame_count):
        step_size = 2 * np.pi * self.frequency / self.sample_rate
        steps = np.arange(frame_count) * step_size + self.phase
        raw_sine = np.sin(steps)
        
        self.phase = (steps[-1] + step_size) % (2 * np.pi)
        
        # Vectorized interpolation over the sample block
        amps = np.linspace(self._current_amplitude, self.amplitude, frame_count, dtype=np.float32)
        balances = np.linspace(self._current_balance, self.balance, frame_count, dtype=np.float32)
        
        self._current_amplitude = self.amplitude
        self._current_balance = self.balance
        
        left_gains = np.cos(balances * (np.pi / 2)) * amps
        right_gains = np.sin(balances * (np.pi / 2)) * amps
        
        stereo_block = np.empty((frame_count, 2), dtype=np.float32)
        stereo_block[:, 0] = raw_sine * left_gains
        stereo_block[:, 1] = raw_sine * right_gains
        return stereo_block


class MixerEngine:
    """Manages oscillator mapping, real-time summing, and lock-aware file polling."""
    def __init__(self, config_path="oscillators.json", sample_rate=44100, chunk_size=1024, enable_dump=True):
        self.config_path = config_path
        self.lock_path = config_path + ".lock"
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.enable_dump = enable_dump
        
        # Thread-safe storage for active oscillators map: {osc_id: WaveOscillator}
        self.osc_dict = {}
        self.osc_lock = threading.Lock()
        
        self.recorded_blocks = []
        self.total_samples_generated = 0
        self.all_used_frequencies = set()
        
        # Thread controls
        self.running = False
        self.watcher_thread = None
        
        # PyAudio Hardware Open
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
        master_mix = np.zeros((frame_count, 2), dtype=np.float32)
        
        # Safely access the dictionary across threads during real-time mixing
        with self.osc_lock:
            for osc in list(self.osc_dict.values()):
                master_mix += osc.generate_block(frame_count)
                
        interleaved_output = master_mix.flatten()
        
        if self.enable_dump:
            self.recorded_blocks.append(interleaved_output.copy())
            
        self.total_samples_generated += frame_count
        return (interleaved_output.tobytes(), pyaudio.paContinue)

    def _watch_config_file(self):
        """Background worker loop that tracks file mutations and protects reads via locks."""
        print(f"[Watcher] Scanning tracking target: '{self.config_path}'")
        last_mtime = 0
        
        while self.running:
            time.sleep(0.1) # Check state 10 times a second
            
            if not os.path.exists(self.config_path):
                continue
                
            # If the writing application has established a lock, back off and wait
            if os.path.exists(self.lock_path):
                continue
                
            try:
                current_mtime = os.path.getmtime(self.config_path)
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    
                    with open(self.config_path, "r") as f:
                        data = json.load(f)
                        
                    self._sync_oscillators(data)
            except (json.JSONDecodeError, IOError):
                # Guard against hitting a partial read if the lock mechanism was bypassed
                continue

    def _sync_oscillators(self, config_data):
        """Updates properties of active nodes, spawns missing ones, and cleans out dead IDs."""
        with self.osc_lock:
            active_ids = set()
            
            for item in config_data:
                osc_id = item["id"]
                active_ids.add(osc_id)
                freq = float(item["frequency"])
                self.all_used_frequencies.add(freq)
                
                if osc_id in self.osc_dict:
                    # Update target variables smoothly on a running oscillator
                    # Checking if frequency changed; if it did, we let it jump (or restart)
                    if self.osc_dict[osc_id].frequency != freq:
                        self.osc_dict[osc_id].frequency = freq
                    self.osc_dict[osc_id].balance = float(item["balance"])
                    self.osc_dict[osc_id].amplitude = float(item["amplitude"])
                else:
                    # Spawn new tracking target safely starting at 0 volume to prevent pops
                    print(f"[Engine] Spawning new oscillator node: '{osc_id}' at {freq}Hz")
                    new_osc = WaveOscillator(
                        osc_id=osc_id,
                        frequency=freq,
                        balance=float(item["balance"]),
                        amplitude=float(item["amplitude"]),
                        sample_rate=self.sample_rate
                    )
                    self.osc_dict[osc_id] = new_osc
            
            # Clean up out-of-bounds nodes no longer present in the JSON definition
            for osc_id in list(self.osc_dict.keys()):
                if osc_id not in active_ids:
                    print(f"[Engine] Removing deactivated node ID: '{osc_id}'")
                    del self.osc_dict[osc_id]

    def start(self):
        self.running = True
        self.watcher_thread = threading.Thread(target=self._watch_config_file, daemon=True)
        self.watcher_thread.start()
        self.stream.start_stream()

    def stop(self):
        self.running = False
        if self.watcher_thread:
            self.watcher_thread.join()
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()


class LoopExporter:
    """Post-processing layout to parse historical streams and cut loops."""
    def __init__(self, sample_rate=44100, min_duration=5.0):
        self.sample_rate = sample_rate
        self.min_duration = min_duration

    def export(self, recorded_blocks, frequencies, total_samples, filename="file_driven_output.wav"):
        if not recorded_blocks:
            return
            
        full_stream = np.concatenate(recorded_blocks)
        loop_samples = None
        
        # Scan if a common denominator phase match exists for all frequencies used
        for i in range(1, total_samples):
            all_aligned = True
            for freq in frequencies:
                cycles = (i * freq) / self.sample_rate
                if not np.isclose(cycles, round(cycles), atol=1e-4):
                    all_aligned = False
                    break
            if all_aligned:
                loop_samples = i
                break
                
        if loop_samples is not None:
            base_duration = loop_samples / self.sample_rate
            base_slice = full_stream[0 : loop_samples * 2]
            
            if base_duration < self.min_duration:
                repetitions = int(np.ceil(self.min_duration / base_duration))
                reshaped = base_slice.reshape(-1, 2)
                duplicated = np.tile(reshaped, (repetitions, 1))
                final_output = duplicated.flatten()
            else:
                final_output = base_slice
                
            print(f"\n--- Exporter Metadata ---")
            print(f"Base Loop Duration: {base_duration:.4f}s")
            print(f"Final Export Time:  {(len(final_output) // 2) / self.sample_rate:.4f}s")
            
            peak = np.max(np.abs(final_output))
            if peak > 0:
                final_output = final_output / peak * 0.95
            wavfile.write(filename, self.sample_rate, np.int16(final_output * 32767))
            print(f"File successfully written: '{filename}'")
        else:
            print("\n[Exporter] Lacked intersecting geometric phase lock points inside session timeline.")

def test_run():
    CONFIG_FILE = "oscillators.json"
    LOCK_FILE = CONFIG_FILE + ".lock"
    
    # Clean up old states from previous runs
    for f_path in [CONFIG_FILE, LOCK_FILE]:
        if os.path.exists(f_path):
            os.remove(f_path)
            
    # Helper utility simulating what your EXTERNAL program will execute
    def external_program_write(data_structure):
        # Create lock file
        with open(LOCK_FILE, "w") as lock:
            lock.write("LOCKED")
        # Write content
        with open(CONFIG_FILE, "w") as f:
            json.dump(data_structure, f)
        # Drop lock file
        os.remove(LOCK_FILE)

    # Write an initial profile setup to disk
    initial_setup = [
        {"id": "node1", "frequency": 400.0, "balance": 0.0, "amplitude": 0.3},
        {"id": "node2", "frequency": 404.0, "balance": 1.0, "amplitude": 0.3}
    ]
    external_program_write(initial_setup)
    
    # Start the engine
    mixer = MixerEngine(config_path=CONFIG_FILE, enable_dump=True)
    mixer.start()
    print("Mixer running. Change the contents of 'oscillators.json' manually or via script to test.")
    
    try:
        time.sleep(3.0)
        print("\n[Simulating External Writer]: Shifting balance and fading in a third tracking tone...")
        updated_setup = [
            {"id": "node1", "frequency": 400.0, "balance": 0.3, "amplitude": 0.3}, # shifted pan
            {"id": "node2", "frequency": 404.0, "balance": 0.7, "amplitude": 0.1}, # reduced volume
            {"id": "node3", "frequency": 410.0, "balance": 0.5, "amplitude": 0.4}  # new tone enters
        ]
        external_program_write(updated_setup)
        
        time.sleep(4.0)
        print("\n[Simulating External Writer]: Killing node2 entirely out of stack...")
        final_setup = [
            {"id": "node1", "frequency": 400.0, "balance": 0.5, "amplitude": 0.4},
            {"id": "node3", "frequency": 410.0, "balance": 0.5, "amplitude": 0.4}
        ]
        external_program_write(final_setup)
        
        time.sleep(3.0)
    finally:
        print("\nHalted mixer engine system...")
        mixer.stop()
        
        exporter = LoopExporter(min_duration=6.0)
        exporter.export(
            recorded_blocks=mixer.recorded_blocks,
            frequencies=list(mixer.all_used_frequencies),
            total_samples=mixer.total_samples_generated,
            filename="external_controlled_session.wav"
        )
        
        # Cleanup demonstration artifacts
        for f_path in [CONFIG_FILE, LOCK_FILE]:
            if os.path.exists(f_path):
                os.remove(f_path)

# --- Demo Runner ---
if __name__ == "__main__":
    CONFIG_FILE = "var/oscillators.json"
    LOCK_FILE = CONFIG_FILE + ".lock"
    
    # Start the engine
    try:
        mixer = MixerEngine(config_path=CONFIG_FILE, enable_dump=False)
        mixer.start()
        print("Mixer running. Change the contents of 'oscillators.json' manually or via script to test.")
        while True:
            time.sleep(5)
    finally:
        print("\nHalted mixer engine system...")
        mixer.stop()
        
        exporter = LoopExporter(min_duration=6.0)
        exporter.export(
            recorded_blocks=mixer.recorded_blocks,
            frequencies=list(mixer.all_used_frequencies),
            total_samples=mixer.total_samples_generated,
            filename="external_controlled_session.wav"
        )
