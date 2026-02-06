# """
# Test script for XTTS-v2 voice cloning
# Author: Jai
# Purpose: Validate local voice-cloned TTS before integration
# """

# import re
# from TTS.api import TTS

# VOICE_SAMPLE = "/Users/jg/projects/ecameo/New Recording.m4a"
# OUTPUT_FILE = "output.wav"

# TEST_TEXT = """
# Hi, this is a test of my AI avatar voice.
# If this sounds like me, then the system is working correctly.
# Later, this voice will answer questions about my professional experience.
# """

# def chunk_text(text, max_chars=200):
#     sentences = re.split(r'(?<=[.!?]) +', text.strip())
#     chunks, current = [], ""
#     for s in sentences:
#         if len(current) + len(s) <= max_chars:
#             current += " " + s
#         else:
#             chunks.append(current.strip())
#             current = s
#     if current:
#         chunks.append(current.strip())
#     return chunks


# def main():
#     print("Loading XTTS-v2 model...")
#     tts = TTS(
#         model_name="tts_models/multilingual/multi-dataset/xtts_v2",
#         gpu=True
#     )

#     chunks = chunk_text(TEST_TEXT)
#     print(f"Text split into {len(chunks)} chunks")

#     for i, chunk in enumerate(chunks):
#         out = OUTPUT_FILE if i == 0 else f"temp_{i}.wav"
#         print(f"Generating chunk {i+1}: {chunk}")

#         tts.tts_to_file(
#             text=chunk,
#             speaker_wav=VOICE_SAMPLE,
#             language="en",
#             file_path=out
#         )

#     print("Done. Play output.wav to verify voice similarity.")


# if __name__ == "__main__":
#     main()


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
