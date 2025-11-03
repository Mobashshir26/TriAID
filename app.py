import os
import re
import unicodedata
import tempfile
import asyncio
import streamlit as st
import speech_recognition as sr
from dotenv import load_dotenv
import google.generativeai as genai
import edge_tts

# -------------------- Load Environment --------------------
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# -------------------- Initialize Session --------------------
if "conversation" not in st.session_state:
    st.session_state.conversation = []
if "is_playing" not in st.session_state:
    st.session_state.is_playing = False


# -------------------- Gemini Response --------------------
def get_gemini_response(question, image=None):
    model = genai.GenerativeModel("gemini-2.5-flash")

    if image:
        prompt = """
        You are an experienced and empathetic medical professional.
        The user is speaking in English.
        Analyze the uploaded image and respond conversationally in English.
        Be natural, clear, and caring.
        Avoid bullet points or markdown symbols.
        """
        response = model.generate_content([prompt, image])
    else:
        prompt = f"""
        You are an empathetic, experienced medical professional.
        The user is speaking in English.
        Reply ONLY in English, naturally and conversationally.
        Avoid bullet points, markdown symbols, or punctuation like * or -.
        Be caring, clear, and concise like a real doctor.

        Patient: {question}
        """
        response = model.generate_content(prompt)

    return response.text


# -------------------- Smart Listening (English only) --------------------
def listen_smart():
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1.8
    recognizer.energy_threshold = 250
    recognizer.dynamic_energy_threshold = True

    with sr.Microphone() as source:
        st.info("🎙️ Listening... Speak naturally. I'll stop when you pause.")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = recognizer.listen(source, timeout=None, phrase_time_limit=None)
            st.info("🧠 Processing your speech...")
            text = recognizer.recognize_google(audio, language="en-IN")
            return text
        except sr.UnknownValueError:
            return "Sorry, I couldn’t understand that."
        except sr.RequestError:
            return "Speech recognition service unavailable."
        except sr.WaitTimeoutError:
            return "No speech detected, please try again."


# -------------------- Text Cleaner --------------------
def clean_text_for_tts(text):
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[*_~#`>\-•\[\]\(\){}<>_]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# -------------------- Text-to-Speech (English only) --------------------
def speak(text):
    text = clean_text_for_tts(text)
    voice = "en-IN-NeerjaNeural"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")

    async def generate():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_file.name)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(generate())
        else:
            loop.run_until_complete(generate())
    except RuntimeError:
        asyncio.run(generate())

    return temp_file.name


# -------------------- Stop Audio --------------------
def stop_audio():
    st.session_state.is_playing = False


# -------------------- Streamlit UI --------------------
st.set_page_config(page_title="🩺 Virtual Doctor", page_icon="💬", layout="centered")
st.title("🩺 TriAID")
st.caption("Talk or upload images to consult your AI Medical Assistant — conversational, vision-enabled, and caring.")

# -------------------- Input Section --------------------
col1, col2 = st.columns([8, 1])
with col1:
    user_input = st.text_input(
        "💬 Type your message or use the mic:",
        key="input_field",
        placeholder="Ask your health query here..."
    )
with col2:
    mic_pressed = st.button("🎤", help="Click to talk")

# Image uploader
uploaded_image = st.file_uploader("📸 Upload a medical image (e.g., report, scan, symptom photo)", type=["jpg", "jpeg", "png"])

# -------------------- Handle Mic Input --------------------
if mic_pressed:
    stop_audio()
    spoken_text = listen_smart()
    user_input = spoken_text
    st.write(f"🗣️ You said: **{spoken_text}**")

# -------------------- Process Query or Image --------------------
if user_input or uploaded_image:
    stop_audio()

    if uploaded_image:
        image_data = {
            "mime_type": uploaded_image.type,
            "data": uploaded_image.read()
        }
        st.image(image_data["data"], caption="🩻 Uploaded Image", use_container_width=True)
    else:
        image_data = None

    st.session_state.conversation.append(("user", user_input if user_input else "[Uploaded Image]"))

    gemini_response = get_gemini_response(user_input, image_data)
    st.session_state.conversation.append(("doctor", gemini_response))

    st.success("👨‍⚕️ Doctor:")
    st.write(gemini_response)

    # Audio response
    audio_file = speak(gemini_response)
    st.session_state.is_playing = True
    with open(audio_file, "rb") as f:
        st.audio(f.read(), format="audio/mp3")

# -------------------- Conversation History --------------------
st.markdown("---")
st.subheader("🩻 Conversation History")
for role, msg in st.session_state.conversation:
    if role == "user":
        st.markdown(f"**🧑 You:** {msg}")
    else:
        st.markdown(f"**👨‍⚕️ Doctor:** {msg}")
