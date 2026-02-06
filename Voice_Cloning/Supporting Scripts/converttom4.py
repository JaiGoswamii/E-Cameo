from pydub import AudioSegment
from datetime import datetime

audio = AudioSegment.from_file("/Users/jg/projects/ecameo/Jai.m4a", format="m4a")
audio = audio.set_channels(1).set_frame_rate(44100)
audio.export(f"/Users/jg/projects/ecameo/Voice_Cloning/Raw_data/jai_voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav", format="wav")

print("Converted to jai_voice.wav")
