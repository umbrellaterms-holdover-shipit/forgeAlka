import pyttsx3
import os
import wave
import struct
import random
import array

# --- Configuration ---
OUTPUT_DIR = "generated_lines"
FINAL_FILE = "hypno_master.wav"
TARGET_DURATION_S = 300  # Total length of the final audio in seconds

SCRIPTS = [
    "script1.txt",
    "script2.txt",
    "script3.txt",
    "script4.txt"
]

# Fixed positions in the stereo field (Left Vol, Right Vol)
VOICE_POSITIONS = [
    (1.0, 0.15),  # Hard Left
    (0.85, 0.3),  # Center Left
    (0.3, 0.85),  # Center Right
    (0.15, 1.0)   # Hard Right
]

def generate_tts_lines():
    """Generates WAV files and returns a list of paths."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    engine = pyttsx3.init()
    engine.setProperty('rate', 140) 
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)
    print("Voice set to:", engine.getProperty('voice'))
    # for voice in voices:
    #     print(voice.id)
    #     if 'ZIRA' in voice.id:
    #         engine.setProperty('voice', voice.id)
    #         print("Voice set to:", engine.getProperty('voice'))
    #         break
        
    audio_files = []
    
    for filename in SCRIPTS:
        if not os.path.exists(filename):
            print(f"Skipping {filename} - not found.")
            continue
            
        with open(filename, 'r', encoding='utf-8') as f:
            lines = []
            for line in f:
                line = line.replace('. ', '.\n')
                for sentence in line.strip().split('.\n'):
                    if sentence:
                        lines.append(sentence)
        print(lines[:2])
    
            
        for i, line in enumerate(lines):
            safe_name = "".join([c for c in line if c.isalpha() or c.isspace()]).strip()
            safe_name = safe_name.replace(" ", "_").lower()[:15]
            file_path = os.path.join(OUTPUT_DIR, f"{filename.split('.')[0]}_{i}.wav")
            
            if not os.path.exists(file_path):
                engine.save_to_file(line, file_path)
            audio_files.append(file_path)
            
    engine.runAndWait()
    return audio_files

def get_wav_info(file_path):
    """Reads the WAV header to get sample rate, channels, and frame count."""
    with wave.open(file_path, 'rb') as wf:
        return {
            "framerate": wf.getframerate(),
            "nchannels": wf.getnchannels(),
            "nframes": wf.getnframes(),
            "duration": wf.getnframes() / wf.getframerate()
        }

def read_and_fade_audio(file_path, master_framerate, fade_ms=50):
    """
    Reads WAV frames, averages them to mono if necessary, 
    and applies a linear fade-in/fade-out to eliminate pops.
    """
    with wave.open(file_path, 'rb') as wf:
        nframes = wf.getnframes()
        nchannels = wf.getnchannels()
        raw_data = wf.readframes(nframes)
        
    # Unpack 16-bit PCM
    fmt = f"<{nframes * nchannels}h"
    samples = list(struct.unpack(fmt, raw_data))
    
    # Convert to mono if it's stereo
    if nchannels == 2:
        mono_samples = [(samples[i] + samples[i+1]) / 2.0 for i in range(0, len(samples), 2)]
    else:
        mono_samples = [float(s) for s in samples]
        
    # Apply Anti-Pop Envelope (Fade In / Fade Out)
    fade_samples = int(master_framerate * (fade_ms / 1000.0))
    total_samples = len(mono_samples)
    
    for i in range(min(fade_samples, total_samples)):
        factor = i / fade_samples
        # Fade In
        mono_samples[i] *= factor
        # Fade Out
        mono_samples[total_samples - 1 - i] *= factor
        
    return mono_samples

def generate_schedule(audio_files, positions, target_duration):
    """Creates independent timelines for each voice position."""
    # Cache durations to build accurate schedules
    file_metadata = {f: get_wav_info(f) for f in audio_files}
    
    schedules = []
    for i, pan in enumerate(positions):
        current_time = random.uniform(0.0, 5.0)  # Initial staggered start
        while current_time < target_duration:
            chosen_file = random.choice(audio_files)
            duration = file_metadata[chosen_file]["duration"]
            
            schedules.append({
                "file": chosen_file,
                "start_s": current_time,
                "pan_L": pan[0],
                "pan_R": pan[1]
            })
            
            # Move time forward by the clip duration + a random gap
            gap = random.uniform(2.0, 6.0)
            current_time += duration + gap
            
    return schedules

def mix_and_render(schedules, master_framerate, target_duration, output_path):
    """Mixes overlapping schedules into a master stereo array and writes to disk."""
    print("Initializing mixing buffers...")
    total_frames = int(target_duration * master_framerate)
    
    # Using arrays for memory efficiency instead of standard lists
    master_L = array.array('d', [0.0] * total_frames)
    master_R = array.array('d', [0.0] * total_frames)
    
    print(f"Mixing {len(schedules)} audio events...")
    for idx, item in enumerate(schedules):
        start_idx = int(item["start_s"] * master_framerate)
        
        # Ensure we don't process files that start after the target duration
        if start_idx >= total_frames:
            continue
            
        audio_data = read_and_fade_audio(item["file"], master_framerate)
        
        pan_l = item["pan_L"]
        pan_r = item["pan_R"]
        
        # Add values into the master tracks
        for i, sample in enumerate(audio_data):
            if start_idx + i < total_frames:
                master_L[start_idx + i] += sample * pan_l
                master_R[start_idx + i] += sample * pan_r
                
    print("Normalizing, clamping, and packing binary data...")
    # Interleave L and R channels into a binary bytearray
    out_bytes = bytearray()
    for l, r in zip(master_L, master_R):
        # Clamp values to valid 16-bit signed integer range to prevent wrap-around distortion
        clamped_l = max(-32768, min(32767, int(l)))
        clamped_r = max(-32768, min(32767, int(r)))
        out_bytes.extend(struct.pack("<hh", clamped_l, clamped_r))
        
    print(f"Writing final audio to {output_path}...")
    with wave.open(output_path, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2) # 16-bit audio (2 bytes)
        wf.setframerate(master_framerate)
        wf.writeframes(out_bytes)

def main():
    print("Phase 1: Generating missing TTS lines...")
    audio_files = generate_tts_lines()
    if not audio_files:
        print("No audio files found. Check scripts.")
        return

    # Grab the sample rate from the first generated file to use as the master
    master_framerate = get_wav_info(audio_files[0])["framerate"]

    print("Phase 2: Generating spatial schedule...")
    schedules = generate_schedule(audio_files, VOICE_POSITIONS, TARGET_DURATION_S)

    print("Phase 3: Rendering master audio...")
    mix_and_render(schedules, master_framerate, TARGET_DURATION_S, FINAL_FILE)
    print("Done.")

if __name__ == "__main__":
    main()
