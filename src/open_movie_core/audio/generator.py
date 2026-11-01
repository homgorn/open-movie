"""
Audio Generation - Procedural and AI
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pathlib import Path
import numpy as np
from scipy import signal
from scipy.io import wavfile
import subprocess
import logging
import tempfile
import os

from ..brief import ProjectBrief, AudioBrief, AudioCue

logger = logging.getLogger(__name__)


class AudioGenerator(ABC):
    """Abstract base class for audio generation"""
    
    @abstractmethod
    async def generate(self, brief: ProjectBrief) -> str:
        """Generate audio file, return path"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict:
        pass


class ProceduralAudioGenerator(AudioGenerator):
    """Procedural ambient score generator (like our score.py)"""
    
    def __init__(self, sample_rate: int = 48000):
        self.sr = sample_rate
    
    def get_capabilities(self) -> Dict:
        return {
            "sample_rate": self.sr,
            "formats": ["wav", "mp3", "flac"],
            "styles": ["ambient", "cinematic", "electronic", "drone"],
            "deterministic": True
        }
    
    async def generate(self, brief: ProjectBrief) -> str:
        """Generate procedural score for entire project"""
        
        duration = brief.duration
        if brief.audio.duration > 0:
            duration = brief.audio.duration
        
        logger.info(f"Generating {duration}s procedural audio ({brief.audio.style})")
        
        # Generate audio array
        audio = self._generate_score(brief, duration)
        
        # Apply loudnorm
        audio = self._apply_loudnorm(audio, brief.audio.loudnorm_target)
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name
        
        wavfile.write(temp_path, self.sr, (audio * 32767).astype(np.int16))
        
        return temp_path
    
    def _generate_score(self, brief: ProjectBrief, duration: float) -> np.ndarray:
        """Generate the actual audio signal"""
        
        N = int(self.sr * duration)
        t = np.arange(N) / self.sr
        mix = np.zeros(N)
        
        # Parse chord progression
        chords = self._parse_chords(brief.audio.progression)
        chord_dur = duration / len(chords) if chords else duration
        
        # 1. DRONE PAD (low, warm)
        mix += self._render_drone_pad(t, chords, chord_dur, duration) * 0.18
        
        # 2. BREATHY PAD (mid, evolving)
        mix += self._render_breathy_pad(t, chords, chord_dur, duration) * 0.12
        
        # 3. ARPEGGIO (high, sparse)
        mix += self._render_arpeggio(t, chords, chord_dur, duration) * 0.22
        
        # 4. LEAD MOTIF (very sparse)
        mix += self._render_lead_motif(t, chords, chord_dur, duration) * 0.15
        
        # 5. TEXTURE
        mix += self._render_texture(N) * 0.05
        
        # 6. SUB BASS
        mix += self._render_sub_bass(t, chords, chord_dur, duration) * 0.10
        
        # Convolution reverb
        mix = self._apply_reverb(mix)
        
        # Fade in/out
        fade_in = np.minimum(1.0, t / 2.0)
        fade_out = np.minimum(1.0, (duration - t) / 3.0)
        mix *= fade_in * fade_out
        
        # Normalize
        peak = np.max(np.abs(mix))
        if peak > 0:
            mix = mix / peak * 0.95
        
        return mix
    
    def _parse_chords(self, progression: List[str]) -> List[tuple]:
        """Parse chord symbols to MIDI note tuples"""
        chord_map = {
            "Am9": (57, 60, 64, 67, 71),   # A3 C4 E4 G4 B4
            "Fmaj7": (53, 57, 60, 64, 69),  # F3 A3 C4 E4 G4
            "Dm9": (50, 53, 57, 60, 65),    # D3 F3 A3 C4 E4
            "Em7": (52, 55, 59, 62, 66),    # E3 G3 B3 D4 F#4
            "Cmaj7": (48, 52, 55, 59, 64),  # C3 E3 G3 B3 E4
            "G7": (43, 47, 50, 53, 57),     # G2 B2 D3 F3 G3
        }
        return [chord_map.get(c, chord_map["Am9"]) for c in progression]
    
    def _render_drone_pad(self, t: np.ndarray, chords: List[tuple], 
                         chord_dur: float, duration: float) -> np.ndarray:
        """Low drone pad with long attack/release"""
        sig = np.zeros_like(t)
        
        for ci, chord in enumerate(chords):
            start = ci * chord_dur
            end = min(start + chord_dur, duration)
            mask = (t >= start) & (t < end)
            if not np.any(mask):
                continue
            
            seg_t = t[mask] - start
            root = 440 * 2**((chord[0] - 69) / 12) / 4
            fifth = 440 * 2**((chord[2] - 69) / 12) / 4
            
            # ADSR envelope
            env = self._adsr(seg_t, chord_dur, a=4.0, d=6.0, s=0.7, r=8.0)
            
            # Detuned oscillators
            sig[mask] += (
                self._osc(root, seg_t, 'tri') * 0.6 +
                self._osc(root * 1.004, seg_t, 'tri') * 0.4 +
                self._osc(fifth, seg_t, 'tri') * 0.35 +
                self._osc(fifth * 0.996, seg_t, 'tri') * 0.25
            ) * env
        
        # Lowpass
        return self._lowpass(sig, 180)
    
    def _render_breathy_pad(self, t: np.ndarray, chords: List[tuple],
                           chord_dur: float, duration: float) -> np.ndarray:
        """Noise-based breathy pad"""
        sig = np.zeros_like(t)
        noise = np.random.randn(len(t)) * 0.5
        
        for ci in range(len(chords)):
            start = ci * chord_dur
            end = min(start + chord_dur, duration)
            mask = (t >= start) & (t < end)
            if not np.any(mask):
                continue
            
            seg_t = t[mask] - start
            
            # Bandpass around 800Hz
            filtered = self._bandpass(noise[mask], 500, 1100)
            
            # Slow amplitude modulation
            env = 0.3 + 0.7 * (0.5 + 0.5 * np.sin(seg_t * 0.15))
            
            sig[mask] = filtered * env
        
        return sig
    
    def _render_arpeggio(self, t: np.ndarray, chords: List[tuple],
                        chord_dur: float, duration: float) -> np.ndarray:
        """Sparse arpeggio at 16th notes"""
        sig = np.zeros_like(t)
        beat = 60.0 / 60.0  # 60 BPM = 1 beat/sec
        sixteenth = beat / 4
        
        for ci, chord in enumerate(chords):
            start = ci * chord_dur
            end = min(start + chord_dur, duration)
            
            # Play on beats 1, 3, and sometimes 2.5
            beat_times = np.arange(start, end, sixteenth)
            for bt in beat_times:
                beat_in_bar = ((bt - start) / beat) % 4
                if beat_in_bar in [0, 2] or (beat_in_bar == 1.5 and np.random.rand() < 0.3):
                    idx = np.random.randint(len(chord))
                    freq = 440 * 2**((chord[idx] - 69) / 12)
                    
                    i0 = int(bt * self.sr)
                    i1 = min(i0 + int(0.35 * self.sr), len(t))
                    if i0 >= len(t):
                        continue
                    
                    seg_len = i1 - i0
                    seg_t = np.arange(seg_len) / self.sr
                    
                    env = np.exp(-seg_t * 6) * (1 - np.exp(-seg_t * 80))
                    mod = np.sin(seg_t * 40) * 0.002 * env
                    note = np.sin(2 * np.pi * freq * seg_t + mod) * env
                    
                    note = self._highpass(note, 800)
                    sig[i0:i1] += note * 0.22
        
        return sig
    
    def _render_lead_motif(self, t: np.ndarray, chords: List[tuple],
                          chord_dur: float, duration: float) -> np.ndarray:
        """Sparse lead melody at section boundaries"""
        sig = np.zeros_like(t)
        
        # Motif at section starts
        motif_times = np.cumsum([0] + [chord_dur] * len(chords))[:-1]
        motif_notes = [72, 74, 76, 77, 79, 81, 84]  # High register
        
        for mt, mn in zip(motif_times, motif_notes):
            if mt >= duration:
                break
            i0 = int(mt * self.sr)
            i1 = min(i0 + int(2.5 * self.sr), len(t))
            if i0 >= len(t):
                continue
            
            seg_len = i1 - i0
            seg_t = np.arange(seg_len) / self.sr
            freq = 440 * 2**((mn - 69) / 12)
            
            env = np.exp(-seg_t * 0.8) * (1 - np.exp(-seg_t * 15))
            vib = np.sin(seg_t * 5.5) * 0.015
            note = np.sin(2 * np.pi * freq * seg_t + vib) * env
            note = self._lowpass(note, 3000)
            sig[i0:i1] += note * 0.15
        
        return sig
    
    def _render_texture(self, N: int) -> np.ndarray:
        """Vinyl crackle / texture"""
        tex = np.random.randn(N) * 0.0005
        clicks = np.random.rand(N) < 0.00008
        tex[clicks] += np.random.randn(np.sum(clicks)) * 0.02
        return self._bandpass(tex, 80, 8000)
    
    def _render_sub_bass(self, t: np.ndarray, chords: List[tuple],
                        chord_dur: float, duration: float) -> np.ndarray:
        """Sub-bass felt more than heard"""
        sig = np.zeros_like(t)
        
        for ci, chord in enumerate(chords):
            start = ci * chord_dur
            end = min(start + chord_dur, duration)
            mask = (t >= start) & (t < end)
            if not np.any(mask):
                continue
            
            seg_t = t[mask] - start
            root = 440 * 2**((chord[0] - 69) / 12) / 8
            
            env = self._adsr(seg_t, chord_dur, a=8.0, d=10.0, s=0.5, r=12.0)
            note = np.sin(2 * np.pi * root * seg_t) * env
            sig[mask] += self._lowpass(note, 60)
        
        return sig
    
    def _apply_reverb(self, sig: np.ndarray) -> np.ndarray:
        """Algorithmic convolution reverb"""
        ir_len = int(4.0 * self.sr)
        ir_t = np.arange(ir_len) / self.sr
        
        # Early reflections
        ir = np.zeros(ir_len)
        early_times = [0.012, 0.024, 0.038, 0.052, 0.071, 0.095]
        early_gains = [0.6, 0.45, 0.35, 0.25, 0.18, 0.12]
        for et, eg in zip(early_times, early_gains):
            idx = int(et * self.sr)
            if idx < ir_len:
                ir[idx] = eg * np.random.randn() * 0.5
        
        # Late tail
        tail = np.exp(-ir_t * 1.8) * np.random.randn(ir_len) * 0.3
        tail = self._lowpass(tail, 3000)
        ir += tail
        
        # Normalize
        ir = ir / np.sqrt(np.sum(ir**2)) * 0.7
        
        # Convolve
        return signal.fftconvolve(sig, ir)[:len(sig)]
    
    def _adsr(self, t: np.ndarray, dur: float, a: float, d: float, 
             s: float, r: float) -> np.ndarray:
        """Vectorized ADSR envelope"""
        env = np.zeros_like(t)
        # Simplified: attack + decay + sustain + release
        attack = np.minimum(1.0, t / a)
        decay = 1.0 - (1.0 - s) * np.minimum(1.0, (t - a) / d)
        decay = np.maximum(decay, s)
        sustain = s
        release = s * np.maximum(0.0, 1.0 - (t - dur + r) / r)
        
        env[t < a] = attack[t < a]
        mid = (t >= a) & (t < dur)
        env[mid] = decay[mid]
        env[t >= dur] = release[t >= dur]
        
        return np.clip(env, 0, 1)
    
    def _osc(self, freq: float, t: np.ndarray, shape: str = 'sine') -> np.ndarray:
        ph = 2 * np.pi * freq * t
        if shape == 'sine':
            return np.sin(ph)
        elif shape == 'tri':
            return 2 * np.abs(ph / (2 * np.pi) - np.floor(ph / (2 * np.pi) + 0.5)) - 1
        return np.sin(ph)
    
    def _lowpass(self, sig: np.ndarray, cutoff: float) -> np.ndarray:
        b, a = signal.butter(4, cutoff / (self.sr / 2), 'low')
        return signal.filtfilt(b, a, sig)
    
    def _highpass(self, sig: np.ndarray, cutoff: float) -> np.ndarray:
        b, a = signal.butter(2, cutoff / (self.sr / 2), 'high')
        return signal.filtfilt(b, a, sig)
    
    def _bandpass(self, sig: np.ndarray, low: float, high: float) -> np.ndarray:
        b, a = signal.butter(2, [low / (self.sr / 2), high / (self.sr / 2)], 'band')
        return signal.filtfilt(b, a, sig)
    
    def _apply_loudnorm(self, audio: np.ndarray, target: float = -16.0) -> np.ndarray:
        """Apply EBU R128 loudnorm via ffmpeg"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f_in:
            wavfile.write(f_in.name, self.sr, (audio * 32767).astype(np.int16))
            in_path = f_in.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f_out:
            out_path = f_out.name
        
        try:
            cmd = [
                'ffmpeg', '-y', '-i', in_path,
                '-af', f'loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json',
                '-ar', str(self.sr), '-sample_fmt', 's16', out_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                sr, normalized = wavfile.read(out_path)
                return normalized.astype(np.float32) / 32767.0
        except Exception as e:
            logger.warning(f"Loudnorm failed: {e}")
        finally:
            os.unlink(in_path)
            os.unlink(out_path)
        
        return audio


# AI Audio Generator placeholder
class AIAudioGenerator(AudioGenerator):
    """AI-based audio generation (ElevenLabs, etc.)"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
    
    def get_capabilities(self) -> Dict:
        return {"styles": ["voiceover", "music", "sfx"], "deterministic": False}
    
    async def generate(self, brief: ProjectBrief) -> str:
        # Placeholder - would call ElevenLabs, etc.
        raise NotImplementedError("AI audio generation not implemented")


def create_audio_generator(brief: ProjectBrief, config: Dict = None) -> AudioGenerator:
    """Factory function"""
    gen_type = brief.audio.generator if brief.audio else "procedural"
    
    if gen_type == "procedural":
        return ProceduralAudioGenerator(config.get("sample_rate", 48000) if config else 48000)
    elif gen_type == "ai":
        return AIAudioGenerator(config)
    else:
        return ProceduralAudioGenerator()