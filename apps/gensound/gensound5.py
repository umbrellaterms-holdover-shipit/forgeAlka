import time
import numpy as np
import pyaudio
from scipy.io import wavfile

class WaveOscillator:
    """
    Manages raw signal generation, phase tracking, and individual panning.
    All properties can be mutated safely in real-time by an operator.
    """
    def __init__(self, frequency=400.0, balance=0.5, amplitude=0.5, sample_rate=44100):
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.phase = 0.0
        
        # Operator Targets (Mutate these anytime)
        self.balance = balance       # 0.0 (Hard Left) to 1.0 (Hard Right)
        self.amplitude = amplitude   # 0.0 to 1.0
        
        # Internal state history for click-free parameter smoothing (lerping)
        self._current_balance = balance
        self._current_amplitude = amplitude

    def generate_block(self, frame_count):
        """Generates a smoothly panned, continuous phase stereo chunk."""
        # 1. Compute raw continuous wave phase steps
        step_size = 2 * np.pi * self.frequency / self.sample_rate
        steps = np.arange(frame_count) * step_size + self.phase
        raw_sine = np.sin(steps)
        
        # Maintain phase lock for next block boundary
        self.phase = (steps[-1] + step_size) % (2 * np.pi)
        
        # 2. Linear parameter interpolation vectors across this specific frame block
        # This completely eliminates popping artifacts when an operator sweeps parameters rapidly.
        amps = np.linspace(self._current_amplitude, self.amplitude, frame_count, dtype=np.float32)
        balances = np.linspace(self._current_balance, self.balance, frame_count, dtype=np.float32)
        
        # Update baseline values for the start of the next chunk request
        self._current_amplitude = self.amplitude
        self._current_balance = self.balance
        
        # 3. Calculate spatial constant-power curves per sample point
        left_gains = np.cos(balances * (np.pi / 2)) * amps
        right_gains = np.sin(balances * (np.pi / 2)) * amps
        
        # 4. Construct stereo block canvas
        stereo_block = np.empty((frame_count, 2), dtype=np.float32)
        stereo_block[:, 0] = raw_sine * left_gains
        stereo_block[:, 1] = raw_sine * right_gains
        return stereo_block


class MixerEngine:
    """Manages the active layer stack, real-time summing, and audio streaming hardware."""
    def __init__(self, sample_rate=44100, chunk_size=1024, enable_dump=True):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.enable_dump = enable_dump
        
        self.oscillators = []  # Stack of live running layers
        self.recorded_blocks = []
        self.total_samples_generated = 0
        
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback
        )

    def add_oscillator(self, osc):
        osc.sample_rate = self.sample_rate
        self.oscillators.append(osc)

    def _audio_callback(self, in_data, frame_count, time_info, status):
        master_mix = np.zeros((frame_count, 2), dtype=np.float32)
        
        # Linearly layer all active oscillator nodes together
        for osc in self.oscillators:
            master_mix += osc.generate_block(frame_count)
            
        interleaved_output = master_mix.flatten()
        
        if self.enable_dump:
            self.recorded_blocks.append(interleaved_output.copy())
            
        self.total_samples_generated += frame_count
        return (interleaved_output.tobytes(), pyaudio.paContinue)

    def start(self):
        self.stream.start_stream()

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()


class LoopExporter:
    """Post-processing workspace to clean up cached timeline data and write loops to disk."""
    def __init__(self, sample_rate=44100, min_duration=5.0):
        self.sample_rate = sample_rate
        self.min_duration = min_duration

    def _find_common_loop_point(self, frequencies, total_samples):
        for i in range(1, total_samples):
            all_aligned = True
            for freq in frequencies:
                cycles = (i * freq) / self.sample_rate
                if not np.isclose(cycles, round(cycles), atol=1e-4):
                    all_aligned = False
                    break
            if all_aligned:
                return i
        return None

    def export(self, recorded_blocks, active_frequencies, total_samples, filename="live_mix.wav"):
        if not recorded_blocks:
            return

        print("\nParsing live session tracking files for geometric boundaries...")
        full_stream = np.concatenate(recorded_blocks)
        loop_samples = self._find_common_loop_point(active_frequencies, total_samples)
        
        if loop_samples is not None:
            base_duration = loop_samples / self.sample_rate
            base_slice = full_stream[0 : loop_samples * 2]
            
            print(f"--- Session Export Logs ---")
            print(f"Base Perfect Loop Period: {base_duration:.4f} seconds")
            
            if base_duration < self.min_duration:
                repetitions = int(np.ceil(self.min_duration / base_duration))
                print(f"Duplicating loop matrix {repetitions} times to clear baseline threshold...")
                reshaped = base_slice.reshape(-1, 2)
                duplicated = np.tile(reshaped, (repetitions, 1))
                final_output = duplicated.flatten()
            else:
                final_output = base_slice
                
            final_duration = (len(final_output) // 2) / self.sample_rate
            print(f"Final Output Duration  : {final_duration:.4f} seconds")
            print(f"---------------------------")
            
            peak = np.max(np.abs(final_output))
            if peak > 0:
                final_output = final_output / peak * 0.95
                
            pcm_data = np.int16(final_output * 32767)
            wavfile.write(filename, self.sample_rate, pcm_data)
            print(f"File successfully output to script home directory: '{filename}'")
        else:
            print("\n[Exporter] Session data lacked an intersecting geometric boundary phase zero lock.")


# --- Live Operator Simulation ---
if __name__ == "__main__":
    mixer = MixerEngine(enable_dump=True)
    
    # Initialize separate tone components inside the operational pool
    osc1 = WaveOscillator(frequency=398.0, balance=0.1, amplitude=0.0) # Hidden at start
    osc2 = WaveOscillator(frequency=402.0, balance=0.9, amplitude=0.3)
    
    mixer.add_oscillator(osc1)
    mixer.add_oscillator(osc2)
    
    mixer.start()
    print("Operator board hot. Audio pipeline running smoothly...")
    
    try:
        # Simulate an operator working the dials over an 8-second window
        print("\n[Operator Action]: Smoothly sliding Osc2 position across spatial landscape...")
        for step in range(30):
            time.sleep(0.1)
            osc2.balance = 0.9 - (step * 0.02)  # Sweep right node across left boundaries
            
        print("\n[Operator Action]: Dropping a third oscillator into the mix...")
        osc3 = WaveOscillator(frequency=400.0, balance=0.5, amplitude=0.0)
        mixer.add_oscillator(osc3)
        
        # Smooth fade-in
        for step in range(20):
            time.sleep(0.1)
            osc3.amplitude = (step * 0.015)
            
        print("\n[Operator Action]: Fading out Osc2 while bringing up hidden Osc1...")
        for step in range(30):
            time.sleep(0.1)
            osc2.amplitude = max(0.0, osc2.amplitude - 0.01)
            osc1.amplitude = min(0.3, osc1.amplitude + 0.01)
            
        time.sleep(1.0)
    finally:
        print("\nClosing live audio stream...")
        mixer.stop()
        
        # Compile unique tracking list of all frequency paths utilized
        freq_list = [osc.frequency for osc in mixer.oscillators]
        
        exporter = LoopExporter(min_duration=8.0)
        exporter.export(
            recorded_blocks=mixer.recorded_blocks,
            active_frequencies=freq_list,
            total_samples=mixer.total_samples_generated,
            filename="operator_session_loop.wav"
        )
