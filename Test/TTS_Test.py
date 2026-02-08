from TTS.api import TTS

tts = TTS(
    model_name="tts_models/multilingual/multi-dataset/xtts_v2"
)

tts.tts_to_file(
    text="This is a clean test of my AI avatar voice.",
    speaker_wav="/Users/jg/projects/ecameo/jai_voice.wav",
    language="en",
    file_path="output.wav"
)

print("Done. Check output.wav")
