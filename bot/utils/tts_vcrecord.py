import pyttsx3
import subprocess

TEXT = "Tää puhekanava on talletuksessa."

engine = pyttsx3.init()
engine.setProperty("rate", 150)
engine.setProperty("volume", 1.0)
engine.save_to_file(TEXT, "tallennus.wav")
engine.runAndWait()

subprocess.run([
    "ffmpeg",
    "-y",
    "-i", "tallennus.wav",
    "-codec:a", "libmp3lame",
    "-qscale:a", "3",
    "tallennus.mp3"
], check=True)

print("Valmis: tallennus.mp3")
