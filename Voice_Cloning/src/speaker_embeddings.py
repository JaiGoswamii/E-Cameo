import torch
from pathlib import Path
from pydub import AudioSegment
from TTS.api import TTS

# ---------- PATHS ----------
BASE_DIR = Path(__file__).resolve().parents[1]
AUDIO_DIR = BASE_DIR / "Raw_data"
TMP_WAV_DIR = BASE_DIR / "src" / "tmp_wavs"
OUTPUT_FILE = BASE_DIR / "src" / "jai_voice_latents.pt"

TMP_WAV_DIR.mkdir(exist_ok=True)

print("Audio directory :", AUDIO_DIR)

# ---------- LOAD MODEL ----------
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

# ---------- COLLECT AUDIO ----------
SUPPORTED_EXTS = ("*.wav", "*.m4a", "*.mp3", "*.M4A")
audio_files = []
for ext in SUPPORTED_EXTS:
    audio_files.extend(AUDIO_DIR.glob(ext))

print(f"Found {len(audio_files)} audio files")
if not audio_files:
    raise RuntimeError("No audio files found")

# ---------- ACCESS INTERNAL XTTS MODEL ----------
xtts_model = tts.synthesizer.tts_model

speaker_embeddings = []
gpt_cond_latent = None

for audio_file in audio_files:
    wav_path = TMP_WAV_DIR / f"{audio_file.stem}.wav"

    AudioSegment.from_file(audio_file).export(wav_path, format="wav")

    gpt_cond, speaker_emb = xtts_model.get_conditioning_latents(
        audio_path=str(wav_path)
    )

    speaker_embeddings.append(speaker_emb)

    if gpt_cond_latent is None:
        gpt_cond_latent = gpt_cond  # take once

# ---------- FINALIZE ----------
speaker_embedding = torch.mean(torch.stack(speaker_embeddings), dim=0)
speaker_embedding = speaker_embedding / torch.norm(speaker_embedding)

torch.save(
    {
        "gpt_cond_latent": gpt_cond_latent,
        "speaker_embedding": speaker_embedding,
    },
    OUTPUT_FILE,
)

print("Saved voice latents →", OUTPUT_FILE)
