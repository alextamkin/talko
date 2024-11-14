import os
import queue
import re
import sys
import anthropic
import subprocess
from gtts import gTTS
from gtts.lang import tts_langs
import tempfile
import random
import json
from datetime import datetime

# Recording speech
import sounddevice as sd
import soundfile as sf

# Command line arguments
from tap import Tap

import colorama
from colorama import Fore, Style

# Deepgram imports
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
)

# Initialize colorama
colorama.init()

LANG_CODE_TO_NAME = {'af': 'Afrikaans', 'ar': 'Arabic', 'bg': 'Bulgarian', 'bn': 'Bengali', 'bs': 'Bosnian', 'ca': 'Catalan', 'cs': 'Czech', 'da': 'Danish', 'de': 'German', 'el': 'Greek', 'en': 'English', 'es': 'Spanish', 'et': 'Estonian', 'fi': 'Finnish', 'fr': 'French', 'gu': 'Gujarati', 'hi': 'Hindi', 'hr': 'Croatian', 'hu': 'Hungarian', 'id': 'Indonesian', 'is': 'Icelandic', 'it': 'Italian', 'iw': 'Hebrew', 'ja': 'Japanese', 'jw': 'Javanese', 'km': 'Khmer', 'kn': 'Kannada', 'ko': 'Korean', 'la': 'Latin', 'lv': 'Latvian', 'ml': 'Malayalam', 'mr': 'Marathi', 'ms': 'Malay', 'my': 'Myanmar (Burmese)', 'ne': 'Nepali', 'nl': 'Dutch', 'no': 'Norwegian', 'pl': 'Polish', 'pt': 'Portuguese', 'ro': 'Romanian', 'ru': 'Russian', 'si': 'Sinhala', 'sk': 'Slovak', 'sq': 'Albanian', 'sr': 'Serbian', 'su': 'Sundanese', 'sv': 'Swedish', 'sw': 'Swahili', 'ta': 'Tamil', 'te': 'Telugu', 'th': 'Thai', 'tl': 'Filipino', 'tr': 'Turkish', 'uk': 'Ukrainian', 'ur': 'Urdu', 'vi': 'Vietnamese', 'zh-CN': 'Chinese (Simplified)', 'zh-TW': 'Chinese (Mandarin/Taiwan)', 'zh': 'Chinese (Mandarin)'}

# Mapping of language codes to macOS voice names with backups
MAC_LANG_TO_VOICE = {
    "es": ["Mónica", "Juan", "Diego", "Jorge"],  # Spanish
    "en": ["Samantha", "Alex", "Fred", "Victoria"],  # English
    "fr": ["Thomas", "Amelie", "Marie", "Daniel"],  # French
    "de": ["Anna", "Helena", "Markus", "Yannick"],  # German
    "it": ["Alice", "Luca", "Federica", "Paolo"],  # Italian
    "pt": ["Joana", "Luciana", "Tiago", "Felipe"],  # Portuguese
    "ru": ["Milena", "Yuri", "Katya", "Alexei"],  # Russian
    "zh-CN": ["Ting-Ting", "Sin-Ji", "Li-Mu", "Mei-Jia"],  # Chinese (Simplified)
    "ko": ["Yuna", "Joon", "Sora", "Jihun"],  # Korean
    "hi": ["Lekha", "Rishi", "Aditi", "Pranav"],  # Hindi
    "ja": ["Kyoko", "Otoya", "Hattori", "Sayaka"],  # Japanese
}

DEEPGRAM_LANG_CODES = {
    'es': 'es-419',     # Latin American Spanish
    'en': 'en-US',      # US English
    'fr': 'fr',         # French
    'de': 'de',         # German
    'it': 'it',         # Italian
    'pt': 'pt',         # Portuguese
    'zh-CN': 'zh-CN',      # Chinese (Simplified)
    'ja': 'ja',         # Japanese
    'ko': 'ko',         # Korean
    'hi': 'hi',         # Hindi
    'ru': 'ru',         # Russian
    'nl': 'nl',         # Dutch
    'pl': 'pl',         # Polish
    'tr': 'tr',         # Turkish
    'uk': 'uk',         # Ukrainian
    'vi': 'vi',         # Vietnamese
    'id': 'id',         # Indonesian
    'th': 'th',         # Thai
    'bg': 'bg',         # Bulgarian
    'ca': 'ca',         # Catalan
    'da': 'da',         # Danish
    'fi': 'fi',         # Finnish
    'el': 'el',         # Greek
    'hu': 'hu',         # Hungarian
    'lt': 'lt',         # Lithuanian
    'lv': 'lv',         # Latvian
    'ro': 'ro',         # Romanian
    'sk': 'sk',         # Slovak
    'sv': 'sv',         # Swedish
}

anthropic_client = anthropic.Anthropic()

def record_speech():
    """Record user speech and save as wav file."""
    q = queue.Queue()
    filename = None

    def callback(indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        q.put(indata.copy())

    try:
        device_info = sd.query_devices(None, "input")
        sample_rate = int(device_info["default_samplerate"])
        filename = "recording.wav"

        with sf.SoundFile(filename, mode="w", samplerate=sample_rate, channels=1) as file:
            with sd.InputStream(samplerate=sample_rate, channels=1, callback=callback):
                print("Press Ctrl+C to stop recording")
                while True:
                    file.write(q.get())
    except KeyboardInterrupt:
        print("\nRecording finished: " + repr(filename))

    return filename

def get_random_word():
    """Get a random word from the macOS words file."""
    try:
        with open('/usr/share/dict/words', 'r') as word_file:
            words = word_file.read().splitlines()
        return random.choice(words).lower()
    except Exception as e:
        print(f"{Fore.RED}Error getting random word: {e}{Style.RESET_ALL}")
        return "default"

def speech_to_text(filename, lang="en"):
    """Convert speech to text using Deepgram Nova 2."""
    print("Converting speech to text with Deepgram Nova 2...")
    try:
        # Initialize Deepgram client
        deepgram = DeepgramClient()
        
        # Read the audio file
        print(f"Reading audio file: {filename}")
        with open(filename, "rb") as file:
            buffer_data = file.read()
        
        # Get the appropriate language code or default to en-US
        language = DEEPGRAM_LANG_CODES.get(lang, 'en-US')
        print(f"Using language: {language}")
        
        # Configure options and transcribe
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            language=language
        )
        
        response = deepgram.listen.rest.v("1").transcribe_file({"buffer": buffer_data}, options)
        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        
        if not transcript.strip():
            print("\nNo speech detected")
            return "(no speech detected)"
            
        print("\nTranscription:")
        print("-" * 80)
        print(transcript)
        print("-" * 80)
        
        return transcript.strip()
        
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        return "(error in speech recognition)"


def query_claude(messages, system_prompt):
    """Get response from Claude 3.5 Sonnet."""
    print("Getting response from Claude 3.5 Sonnet...")
    response = anthropic_client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=1000,
        temperature=0.7,
        system=system_prompt,
        messages=messages
    )
    return response.content[0].text

def text_to_speech_google(text, lang):
    """Convert text to speech using Google TTS (gTTS) with language fallbacks."""
    print("Converting text to speech with Google TTS...")
    available_langs = tts_langs()

    # Try the exact language code first
    if lang in available_langs:
        tts_lang = lang
    else:
        # If not found, try finding a close match (e.g., 'es-ES' for 'es')
        tts_lang = next((l for l in available_langs if l.startswith(lang)), None)

    if tts_lang is None:
        print(f"No suitable language found for {lang}. Falling back to English.")
        tts_lang = 'en'

    tts = gTTS(text=text, lang=tts_lang)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        tts.save(temp_audio.name)
        temp_audio_path = temp_audio.name

    subprocess.run(["afplay", temp_audio_path])
    os.unlink(temp_audio_path)

def text_to_speech_mac(text, lang, rate=200):
    """Variant: Convert text to speech using macOS 'say' command with voice fallbacks."""
    print("Converting text to speech with macOS...")
    voices = MAC_LANG_TO_VOICE.get(lang, ["Samantha"])  # Default to Samantha if language not found

    for voice in voices:
        try:
            subprocess.run(["say", "-v", voice, "-r", str(rate), text], check=True)
            break  # If successful, exit the loop
        except subprocess.CalledProcessError:
            print(f"Voice '{voice}' not available. Trying next option.")
    else:
        print("No suitable voice found. Using default system voice.")
        subprocess.run(["say", "-r", str(rate), text])

def read_latest_user_progress(user_folder):
    """Read the most recent user progress file."""
    if not os.path.exists(user_folder):
        return None
    files = [f for f in os.listdir(user_folder) if f.endswith('.json')]
    if not files:
        return None
    latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(user_folder, f)))
    with open(os.path.join(user_folder, latest_file), 'r') as f:
        return json.load(f)

def write_user_progress(user_folder, lang, level, lesson_summary, overall_progress="", language_goals="", proximal_development=""):
    """Write a new user progress file."""
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"progress_{timestamp}.json"

    previous_progress = read_latest_user_progress(user_folder) or {}

    progress = {
        "timestamp": timestamp,
        "language": LANG_CODE_TO_NAME.get(lang, "Unknown language"),
        "current_level": level,
        "lesson_summary": lesson_summary,
        "overall_progress": overall_progress or previous_progress.get("overall_progress", ""),
        "language_goals": language_goals or previous_progress.get("language_goals", ""),
        "proximal_development": proximal_development or previous_progress.get("proximal_development", "")
    }

    with open(os.path.join(user_folder, filename), 'w') as f:
        json.dump(progress, f, indent=2)

def update_progress_with_claude(user_folder, lang, level, lesson_summary):
    """Use Claude 3.5 Sonnet to update the user's overall progress and language goals."""
    previous_progress = read_latest_user_progress(user_folder) or {}

    system_prompt = """You are an AI language learning assistant. Your task is to provide a detailed update on the user's overall progress and language goals based on their previous progress and recent lesson summary. Focus on the user's proximal zone of development to inform future lessons efficiently."""

    user_message = f"""Based on the user's previous progress and the recent lesson summary, provide an updated overall progress and language goals for the user. Focus on the proximal zone of development to suggest the most efficient ways to improve.

Previous overall progress: {previous_progress.get('overall_progress', 'No previous progress recorded.')}
Previous language goals: {previous_progress.get('language_goals', 'No previous goals recorded.')}

Recent lesson summary: {lesson_summary}

Current language: {LANG_CODE_TO_NAME.get(lang, 'Unknown language')}
Current level: {level}/10

Please provide your response in the following XML format:
<overall_progress>
A few paragraphs detailing the user's overall progress, including strengths, areas for improvement, and how they've advanced since the last update.
</overall_progress>

<language_goals>
A few paragraphs outlining specific language goals tailored to the user's current level and proximal zone of development. Include suggestions for the most efficient ways to achieve these goals.
</language_goals>

<proximal_development>
A paragraph discussing the user's proximal zone of development and recommendations for future lessons to maximize learning efficiency.
</proximal_development>"""

    response = anthropic_client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1000,
        temperature=0.7,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message},
        ]
    )

    claude_response = response.content[0].text

    # Parse the XML response
    overall_progress = re.search(r'<overall_progress>(.*?)</overall_progress>', claude_response, re.DOTALL)
    language_goals = re.search(r'<language_goals>(.*?)</language_goals>', claude_response, re.DOTALL)
    proximal_development = re.search(r'<proximal_development>(.*?)</proximal_development>', claude_response, re.DOTALL)

    overall_progress = overall_progress.group(1).strip() if overall_progress else ""
    language_goals = language_goals.group(1).strip() if language_goals else ""
    proximal_development = proximal_development.group(1).strip() if proximal_development else ""

    return overall_progress, language_goals, proximal_development

def diagnostic_test(lang, user_folder):
    """Conduct a diagnostic test to determine language proficiency."""
    system_prompt = f"""You are a language proficiency evaluator for {LANG_CODE_TO_NAME.get(lang, 'Unknown language')}.
    Conduct a verbal diagnostic test with 3 questions of increasing difficulty to assess the user's proficiency.
    After the test, provide a summary and assign a proficiency level from 1 to 10, where 1 is beginner and 10 is native-like fluency.
    Speak in the target language, but provide translations for beginners if they struggle."""

    messages = [
        {
            "role": "user",
            "content": f"Please start the {LANG_CODE_TO_NAME.get(lang, 'Unknown language')} proficiency test.",
        },
    ]

    response = query_claude(messages, system_prompt)
    text_to_speech_google(response, lang)
    print("Evaluator:", response)

    messages.append({"role": "assistant", "content": response})

    for _ in range(7):  # Ask up to 7 questions
        input("Press enter to record your answer.")
        filename = record_speech()
        user_response = speech_to_text(filename, lang)
        print("You said:", user_response)
        messages.append({"role": "user", "content": user_response})

        response = query_claude(messages, system_prompt)
        text_to_speech_google(response, lang)
        print("Evaluator:", response)

        messages.append({"role": "assistant", "content": response})

        if "proficiency level" in response.lower():
            break

    level = int(response.split("proficiency level")[-1].strip().split()[0])

    lesson_summary = f"Diagnostic test completed. Assigned proficiency level: {level}/10"
    overall_progress, language_goals, proximal_development = update_progress_with_claude(user_folder, lang, level, lesson_summary)
    write_user_progress(user_folder, lang, level, lesson_summary, overall_progress, language_goals, proximal_development)

    return level

def generate_lesson(lang, level, user_folder):
    """Generate a custom interactive lesson based on the given level."""
    print(f"{Fore.CYAN}Generating a topic for the lesson...{Style.RESET_ALL}")

    # Select two random words
    random_word1 = get_random_word()
    random_word2 = get_random_word()

    print(f"{Fore.YELLOW}Inspiration words: {random_word1}, {random_word2}{Style.RESET_ALL}")

    topic_generation_prompt = f"""As a language learning expert, your task is to generate an interesting and level-appropriate topic for a {LANG_CODE_TO_NAME.get(lang, 'Unknown language')} lesson.

    Current language level: {level}/10
    Inspiration words: {random_word1}, {random_word2}

    Please follow these steps and show your full chain of thought:
    1. Consider the two given inspiration words: {random_word1} and {random_word2}.
    2. Use these words as inspiration to create a unique, engaging topic that's suitable for the student's current language level.
    3. Ensure the topic is 2-5 words long and appropriate for a language learning context.
    4. Explain your reasoning for choosing this topic and how it relates to the language level.

    At the end of your response, please clearly state the final topic by prefixing it with "FINAL TOPIC:"."""

    topic_response = query_claude([{"role": "user", "content": topic_generation_prompt}], "You are a creative topic generator for language learning lessons.")

    print(f"{Fore.GREEN}Topic generation process:{Style.RESET_ALL}")
    print(topic_response)

    # Extract the final topic
    topic_match = re.search(r'FINAL TOPIC:\s*(.+)', topic_response)
    if topic_match:
        topic = topic_match.group(1).strip()
    else:
        print(f"{Fore.RED}Failed to extract topic. Using a default topic.{Style.RESET_ALL}")
        topic = "Daily routines"

    print(f"\n{Fore.GREEN}Selected topic: {topic}{Style.RESET_ALL}")

    system_prompt = f"""You are a concise language tutor for {LANG_CODE_TO_NAME.get(lang, 'Unknown language')} at proficiency level {level}/10.
    Create an interactive spoken-language lesson on the topic of {topic}. Possible activities include:
    1. Key vocabulary words or phrases
    2. Short reading passage or dialogue
    3. Comprehension questions
    4. Role-playing scenarios
    5. Other creative exercises
    Keep your responses brief (1-2 sentences max) to maximize student speaking time. Correct any grammar mistakes succinctly and don't overly praise the student's response. Adjust complexity based on proficiency level.
    
    Your words will be read aloud by as system that expects you to speak in the target language, so always speak in the target language, unless using [square brackets], which are not read aloud. [square brackets] can be used for:
    - Translations for each sentence (only levels 1-2) or individual words/phrases (levels 3-6) as appropriate to the level
    - Pronunciation in cases where the user might not know the pronunciation (or appear to be having trouble pronouncing the word), especially at earlier levels. 
    
    Lessons for languages with non-Roman alphabets should be more basic and more heavily annotated (with multiple of translations, pronunciations, and hints) at the early levels than for other languages. 
    
    Be highly interactive and encourage student output. Focus on sentence structure, grammar, and vocabulary rather than minor pronunciation or punctuation issues. If a user can't get the pronunciation right after 1-2 tries, just move on. (Also take into account that the student's response is being transcribed by a good but imperfect STT system) Don't use asterisks in your responses."""

    user_progress = read_latest_user_progress(user_folder)
    if user_progress:
        system_prompt += f"\nUser's overall progress: {user_progress.get('overall_progress', 'Not available')}"
        system_prompt += f"\nUser's language goals: {user_progress.get('language_goals', 'Not available')}"
        system_prompt += f"\nUser's proximal zone of development: {user_progress.get('proximal_development', 'Not available')}"

    messages = [
        {
            "role": "user",
            "content": f"Please start a {LANG_CODE_TO_NAME.get(lang, 'Unknown language')} lesson at level {level} on the topic of {topic}.",
        },
    ]

    response = query_claude(messages, system_prompt)
    print(f"\n{Fore.CYAN}Turn 1 - Tutor:{Style.RESET_ALL}")
    print_colored_response(response)

    spoken_text = re.sub(r'\[.*?\]', '', response)  # Remove text in square brackets
    text_to_speech_google(spoken_text.strip(), lang)

    messages.append({"role": "assistant", "content": response})

    try:
        for turn in range(2, 50):
            input(f"\n{Fore.GREEN}Press enter to record your response (or Ctrl+C to finish early):{Style.RESET_ALL}")
            filename = record_speech()
            user_response = speech_to_text(filename, lang)
            print(f"\n{Fore.YELLOW}You said:{Style.RESET_ALL}", user_response)
            messages.append({"role": "user", "content": user_response})

            response = query_claude(messages, system_prompt)
            print(f"\n{Fore.CYAN}Turn {turn} - Tutor:{Style.RESET_ALL}")
            print_colored_response(response)

            # Improved bracket handling
            spoken_text = re.sub(r'\s*\[.*?\]\s*', ' ', response)  # Remove brackets and their content, handling whitespace
            spoken_text = re.sub(r'\s+', ' ', spoken_text)  # Clean up any double spaces
            spoken_text = spoken_text.strip()  # Remove leading/trailing whitespace
            
            # Only speak if there's actual content after removing brackets
            if spoken_text:
                text_to_speech_google(spoken_text, lang)

            messages.append({"role": "assistant", "content": response})

            if "lesson is complete" in response.lower():
                break

    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Lesson terminated early by user.{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}Writing lesson summary and updating progress...{Style.RESET_ALL}")
    lesson_summary = f"Completed a level {level} lesson on the topic of {topic}"
    overall_progress, language_goals, proximal_development = update_progress_with_claude(user_folder, lang, level, lesson_summary)
    write_user_progress(user_folder, lang, level, lesson_summary, overall_progress, language_goals, proximal_development)

    return level

def print_colored_response(response):
    """Print the response with colorized square bracket translations."""
    parts = re.split(r'(\[[^\]]*\])', response)
    for i, part in enumerate(parts):
        if i % 2 == 0:
            print(part, end='')
        else:
            print(f"{Fore.MAGENTA}{part}{Style.RESET_ALL}", end='')
    print()  # New line at the end

class ArgumentParser(Tap):
    lang: str = "en"  # Language code for text-to-speech
    level: str = "diagnostic"  # Level: 'diagnostic' or 1-10
    user: str  # User folder name for storing progress

def main(args):
    """Main loop."""
    language = LANG_CODE_TO_NAME.get(args.lang, "Unknown language")

    if args.level == "diagnostic":
        print(f"Starting diagnostic test for {language}...")
        level = diagnostic_test(args.lang, args.user)
        print(f"Your proficiency level in {language} is: {level}/10")
    elif args.level.isdigit() and 1 <= int(args.level) <= 10:
        level = int(args.level)
        print(f"Starting a level {level} lesson in {language}...")
        generate_lesson(args.lang, level, args.user)
    else:
        print("Invalid level. Please use 'diagnostic' or a number between 1 and 10.")
        return

    print("Lesson complete. Thank you for learning with us!")

if __name__ == "__main__":
    args = ArgumentParser().parse_args()
    main(args)

# Example usage:
# python talko_lesson.py --lang=es --level=diagnostic --user=yourname
# python talko_lesson.py --lang=fr --level=5 --user=yourname