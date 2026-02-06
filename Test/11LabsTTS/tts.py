from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

client = ElevenLabs(
    api_key="sk_444c5d649ba38fe8ec6673eb08bc0f21b9552a6274c24680"
)

audio = client.text_to_speech.convert(
    text="The first move is what sets everything in motion.",
    voice_id="QtEl85LECywm4BDbmbXB",
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128",
)

play(audio)