"""
Kokoro TTS Client for AI Agents & Automation
Backend: https://kokoro-tts.celfedu.com
Defaults: Blend Voice (bm_fable,am_echo) @ 0.85x speed with flowing pacing
"""

import os
import requests


def generate_voiceover(
    text: str,
    output_filename: str = "narration.wav",
    voice: str = "blend_fable_echo",
    speed: float = 0.85,
    server_url: str = "https://kokoro-tts.celfedu.com/api/generate"
) -> str:
    """
    Generates high-quality speech audio from text using your deployed Kokoro TTS server.

    Args:
        text (str): The script or sentence to speak.
        output_filename (str): Where to save the WAV file (default: 'narration.wav').
        voice (str): Voice name or blend (default: 'blend_fable_echo').
        speed (float): Playback speed (default: 0.85).
        server_url (str): Endpoint URL of your deployed server.

    Returns:
        str: Absolute path to the saved WAV audio file.
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    payload = {
        "text": text.strip(),
        "voice": voice,
        "speed": speed
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(server_url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()

        output_path = os.path.abspath(output_filename)
        with open(output_path, "wb") as f:
            f.write(response.content)

        return output_path

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"TTS generation failed: {e}")


# Example usage for testing
if __name__ == "__main__":
    sample_text = (
        "It's a Saturday morning. You're standing in the driveway in a pair of old sneakers, "
        "holding a coffee that's already gone cold."
    )
    
    print("Sending text to TTS server...")
    saved_path = generate_voiceover(sample_text, output_filename="sample_voiceover.wav")
    print(f"Audio successfully saved to: {saved_path}")
