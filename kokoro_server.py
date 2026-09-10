"""
Kokoro TTS Web Server
Run: python kokoro_server.py
Then open: http://localhost:5050
"""

from flask import Flask, request, send_file, jsonify, send_from_directory
import io
import os
import re
import numpy as np

app = Flask(__name__, static_folder="kokoro_ui", static_url_path="")

# ── Voice catalogue ────────────────────────────────────────────────────────────
VOICES = {
    # ── American Female ────────────────────────────────────────────────────────
    "af_heart":   {"name": "Heart",    "gender": "Female", "accent": "American", "lang": "a", "desc": "Warm & natural"},
    "af_bella":   {"name": "Bella",    "gender": "Female", "accent": "American", "lang": "a", "desc": "Clear & expressive"},
    "af_nicole":  {"name": "Nicole",   "gender": "Female", "accent": "American", "lang": "a", "desc": "Soft & gentle"},
    "af_aoede":   {"name": "Aoede",    "gender": "Female", "accent": "American", "lang": "a", "desc": "Melodic & artistic"},
    "af_kore":    {"name": "Kore",     "gender": "Female", "accent": "American", "lang": "a", "desc": "Professional"},
    "af_sarah":   {"name": "Sarah",    "gender": "Female", "accent": "American", "lang": "a", "desc": "Friendly & clear"},
    "af_sky":     {"name": "Sky",      "gender": "Female", "accent": "American", "lang": "a", "desc": "Light & airy"},
    # ── American Male ──────────────────────────────────────────────────────────
    "am_adam":    {"name": "Adam",     "gender": "Male",   "accent": "American", "lang": "a", "desc": "Deep & authoritative"},
    "am_echo":    {"name": "Echo",     "gender": "Male",   "accent": "American", "lang": "a", "desc": "Resonant & rich"},
    "am_eric":    {"name": "Eric",     "gender": "Male",   "accent": "American", "lang": "a", "desc": "Confident"},
    "am_fenrir":  {"name": "Fenrir",   "gender": "Male",   "accent": "American", "lang": "a", "desc": "Bold & strong"},
    "am_liam":    {"name": "Liam",     "gender": "Male",   "accent": "American", "lang": "a", "desc": "Casual & friendly"},
    "am_michael": {"name": "Michael",  "gender": "Male",   "accent": "American", "lang": "a", "desc": "Classic & warm"},
    "am_onyx":    {"name": "Onyx",     "gender": "Male",   "accent": "American", "lang": "a", "desc": "Rich & smooth"},
    "am_puck":    {"name": "Puck",     "gender": "Male",   "accent": "American", "lang": "a", "desc": "Upbeat & energetic"},
    # ── British Female ─────────────────────────────────────────────────────────
    "bf_alice":   {"name": "Alice",    "gender": "Female", "accent": "British",  "lang": "b", "desc": "Elegant & crisp"},
    "bf_emma":    {"name": "Emma",     "gender": "Female", "accent": "British",  "lang": "b", "desc": "Sophisticated"},
    "bf_isabella":{"name": "Isabella", "gender": "Female", "accent": "British",  "lang": "b", "desc": "Refined & poised"},
    "bf_lily":    {"name": "Lily",     "gender": "Female", "accent": "British",  "lang": "b", "desc": "Delicate & charming"},
    # ── British Male ───────────────────────────────────────────────────────────
    "bm_daniel":  {"name": "Daniel",   "gender": "Male",   "accent": "British",  "lang": "b", "desc": "Professional"},
    "bm_fable":   {"name": "Fable",    "gender": "Male",   "accent": "British",  "lang": "b", "desc": "Storyteller"},
    "bm_george":  {"name": "George",   "gender": "Male",   "accent": "British",  "lang": "b", "desc": "Classic British"},
    "bm_lewis":   {"name": "Lewis",    "gender": "Male",   "accent": "British",  "lang": "b", "desc": "Deep & powerful"},
    # ── Blended Voices ─────────────────────────────────────────────────────────
    "blend_fable_echo": {"name": "Fable + Echo (Blend)", "gender": "Male", "accent": "Hybrid", "lang": "b", "desc": "Storyteller + Rich Resonance (Default)"},
}

# ── Lazy-load pipelines ────────────────────────────────────────────────────────
_pipelines = {}

def get_pipeline(lang_code: str):
    if lang_code not in _pipelines:
        print(f"  Loading Kokoro pipeline for lang='{lang_code}'...")
        from kokoro import KPipeline
        _pipelines[lang_code] = KPipeline(lang_code=lang_code)
        print(f"  Pipeline '{lang_code}' ready.")
    return _pipelines[lang_code]


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("kokoro_ui", "index.html")


@app.route("/api/voices")
def api_voices():
    return jsonify(VOICES)


def normalize_text(text: str) -> str:
    # 1. Strip markdown dividers and artifacts
    text = re.sub(r'^-{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)

    # 2. Normalize clock times ending in :00 (e.g. 7:00 -> 7, 7:00 AM -> 7 AM)
    text = re.sub(r'\b(\d{1,2}):00\s*([ap]\.?m\.?)\b', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d{1,2}):00\b', r'\1', text)

    # 3. Flowing text: connect isolated single-sentence lines into natural flowing speech
    # This prevents Kokoro from inserting dead pauses after every short line
    paragraphs = text.split("\n\n")
    cleaned_paragraphs = []
    for p in paragraphs:
        p_clean = " ".join([line.strip() for line in p.splitlines() if line.strip()])
        if p_clean:
            cleaned_paragraphs.append(p_clean)
    
    return "\n\n".join(cleaned_paragraphs)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data    = request.get_json(force=True)
    text    = data.get("text", "").strip()
    voice   = data.get("voice", "bm_fable,am_echo")
    speed   = float(data.get("speed", 0.85))

    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Map named blend alias to actual blend voices
    if voice == "blend_fable_echo":
        voice = "bm_fable,am_echo"

    # Support comma-separated blended voices (e.g. "bm_fable,am_echo")
    voice_parts = [v.strip() for v in voice.split(",") if v.strip()]
    if not voice_parts:
        return jsonify({"error": "No valid voice specified"}), 400

    for v in voice_parts:
        if v not in VOICES and v != "bm_fable,am_echo":
            return jsonify({"error": f"Unknown voice: {v}"}), 400

    lang_code = VOICES.get(voice_parts[0], {}).get("lang", "b")

    # Pre-normalize text for natural pronunciation and flowing pacing
    text = normalize_text(text)

    try:
        pipeline = get_pipeline(lang_code)

        all_audio = []
        sample_rate = 24000

        for result in pipeline(text, voice=voice, speed=speed):
            # Kokoro 0.9.4 yields KPipeline.Result objects with a .audio torch.Tensor
            if hasattr(result, 'audio'):
                audio = result.audio
            elif isinstance(result, tuple):
                audio = result[-1]  # fallback for older versions
            else:
                audio = result

            if audio is None:
                continue

            # Convert torch.Tensor -> numpy if needed
            if hasattr(audio, 'detach'):
                audio = audio.detach().cpu().numpy()

            if len(audio) > 0:
                all_audio.append(audio)

        if not all_audio:
            return jsonify({"error": "No audio generated"}), 500

        combined = np.concatenate(all_audio)

        # Write WAV to in-memory buffer
        import soundfile as sf
        buf = io.BytesIO()
        sf.write(buf, combined, sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)

        return send_file(
            buf,
            mimetype="audio/wav",
            as_attachment=False,
            download_name=f"kokoro_{voice}.wav"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\nKokoro TTS Server")
    print("   Open http://localhost:5050 in your browser\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
