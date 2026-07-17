import numpy as np
import pyaudio
import time

class AudioDeviceProber:
    """Sweeps through available system hardware inputs to detect live signals."""
    def __init__(self, sample_rate=44100, chunk_size=2048, check_duration=5.0):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.check_duration = check_duration
        self.p = pyaudio.PyAudio()

    def discover_inputs(self):
        """Collects all hardware devices reported as input-capable by the host."""
        input_devices = []
        try:
            info = self.p.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount', 0)
        except Exception:
            num_devices = self.p.get_device_count()

        for i in range(num_devices):
            try:
                device_info = self.p.get_device_info_by_host_api_device_index(0, i)
            except Exception:
                try:
                    device_info = self.p.get_device_info_by_index(i)
                except Exception:
                    continue

            if device_info.get('maxInputChannels', 0) > 0:
                input_devices.append({
                    'index': i,
                    'name': device_info.get('name'),
                    'channels': device_info.get('maxInputChannels'),
                    'default_rate': device_info.get('defaultSampleRate')
                })
        return input_devices

    def probe_device(self, device):
        """Opens a temporary stream on an index and tracks peak signal levels."""
        idx = device['index']
        name = device['name']
        
        # Test if the device default rate overrides our baseline target
        rate = int(device['default_rate']) if device['default_rate'] else self.sample_rate
        
        print(f"  Testing Index {idx}: '{name}' ({rate}Hz)...", end="", flush=True)
        
        try:
            stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=rate,
                input=True,
                input_device_index=idx,
                frames_per_buffer=self.chunk_size
            )
        except Exception:
            print(" [Failed to Open Stream]")
            return None

        peak_volume = 0.0
        start_time = time.time()
        
        while time.time() - start_time < self.check_duration:
            try:
                raw_data = stream.read(self.chunk_size, exception_on_overflow=False)
                audio_block = np.frombuffer(raw_data, dtype=np.float32)
                
                # Check absolute peak deviation from center line
                current_peak = np.max(np.abs(audio_block))
                if current_peak > peak_volume:
                    peak_volume = current_peak
            except IOError:
                continue

        stream.stop_stream()
        stream.close()
        print(f" [Done] Peak Level Detected: {peak_volume:.5f}")
        return peak_volume

    def run_sweep(self):
        """Executes the systematic review across the gathered infrastructure map."""
        print("=== Initiating Audio Interface Signal Sweep ===")
        devices = self.discover_inputs()
        
        if not devices:
            print("[Error] No input-capable physical hardware nodes detected by PyAudio.")
            self.p.terminate()
            return

        print(f"Found {len(devices)} potential input devices. Probing each for {self.check_duration} seconds...")
        print("Make some continuous noise (hum, speak, clap) near your mic now.\n")

        results = []
        for dev in devices:
            peak = self.probe_device(dev)
            if peak is not None:
                results.append((dev['index'], dev['name'], peak))

        self.p.terminate()

        print("\n" + "="*50)
        print("                 SWEEP RESULTS                 ")
        print("="*50)
        print(f"{'Index':<7}{'Peak Level':<15}{'Device Name'}")
        print("-"*50)
        
        # Sort by loudest registered volume down to zero
        results.sort(key=lambda x: x[2], reverse=True)
        
        for idx, name, peak in results:
            # Highlight devices that clearly registered input above minimal systemic electrical hiss
            status_flag = "<- [LIVE SIGNAL]" if peak > 0.001 else ""
            print(f"{idx:<7}{peak:<15.5f}{name} {status_flag}")
            
        print("="*50)

if __name__ == "__main__":
    # Lowered check duration to 5 seconds per device to keep the script snappy, 
    # but you can increase it if needed.
    prober = AudioDeviceProber(check_duration=5.0)
    prober.run_sweep()
