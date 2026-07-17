import pyttsx3

engine = pyttsx3.init('sapi5')
voices = engine.getProperty('voices')
for voice in voices:
    print(voice.id)
    if 'ZIRA' in voice.id:
        engine.setProperty('voice', voice.id)
        engine.say("Hello, this is ... no one")
        engine.runAndWait()