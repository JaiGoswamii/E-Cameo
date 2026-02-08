import torch
import numpy as np
import soundfile as sf
from pathlib import Path
from TTS.api import TTS

# ---------- PATHS ----------
LATENTS_FILE = "/Users/jg/projects/ecameo/Voice_Cloning/src/jai_voice_latents.pt"
OUTPUT_WAV = "/Users/jg/projects/ecameo/Voice_Cloning/Outputs/jai_voice_cloned.wav"

Path(OUTPUT_WAV).parent.mkdir(parents=True, exist_ok=True)

# ---------- LOAD MODEL ----------
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
xtts_model = tts.synthesizer.tts_model

# ---------- LOAD LATENTS ----------
latents = torch.load(LATENTS_FILE, map_location="cpu")

# ---------- INFERENCE ----------
out = xtts_model.inference(
    text="My name is Jai Goswami, and I am from Delhi, India.",
    language="en",
    gpt_cond_latent=latents["gpt_cond_latent"],
    speaker_embedding=latents["speaker_embedding"],
)

# ---------- NORMALIZE OUTPUT (CRITICAL FIX) ----------
# Handle dict output
if isinstance(out, dict):
    wav = out.get("wav", None)
    sr = out.get("sample_rate", 24000)
else:
    wav = out
    sr = 24000

# Handle list output
if isinstance(wav, list):
    wav = wav[0]

# Handle torch tensor
if isinstance(wav, torch.Tensor):
    wav = wav.detach().cpu().numpy()

# Force numpy array
wav = np.asarray(wav)

# Handle scalar / empty edge cases
if wav.ndim == 0:
    wav = wav.reshape(1)

# Final safety: ensure 1-D float32
wav = wav.astype(np.float32).flatten()

# ---------- SAVE ----------
sf.write(OUTPUT_WAV, wav, sr)
print("Done →", OUTPUT_WAV)
