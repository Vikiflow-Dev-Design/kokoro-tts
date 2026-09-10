r'''
Kokoro TTS — Batch Voice Tester
Starts kokoro_server.py in the background, fetches all voices from /api/voices,
generates a WAV sample for each voice, and saves them to ./voice_samples/
'''
import subprocess
import sys
import time
import os
import json
import urllib.request
import urllib.error
import threading
import pathlib

SERVER_URL = "http://localhost:5050"
SAMPLE_TEXT = "Hello! This is a test of the Kokoro TTS voice system. The audio generation is sounding crisp and natural."
OUT_DIR = pathlib.Path("voice_samples")
OUT_DIR.mkdir(exist_ok=True)

def wait_for_server(proc, timeout=120):
    print("Waiting for Kokoro server to start ...", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            print(f"Server process terminated early with code {proc.returncode}")
            return False
        try:
            with urllib.request.urlopen(f"{SERVER_URL}/api/voices", timeout=3) as r:
                if r.status == 200:
                    print("Server is up and responding!\n", flush=True)
                    return True
        except Exception:
            time.sleep(1)
    return False

def get_voices():
    with urllib.request.urlopen(f"{SERVER_URL}/api/voices", timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))

def test_voice(voice_id, meta):
    payload = json.dumps({"text": SAMPLE_TEXT, "voice": voice_id, "speed": 1.0}).encode("utf-8")
    req = urllib.request.Request(
        f"{SERVER_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        elapsed = time.time() - t0
        out_file = OUT_DIR / f"{voice_id}.wav"
        out_file.write_bytes(data)
        size_kb = len(data) / 1024
        return True, f"{size_kb:6.1f} KB  ({elapsed:4.2f}s) -> {out_file.name}"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")[:120]
        return False, f"HTTP {e.code}: {err_msg}"
    except Exception as exc:
        return False, str(exc)

def main():
    python_exe = sys.executable
    server_env = os.environ.copy()
    server_env["PYTHONIOENCODING"] = "utf-8"

    server_proc = subprocess.Popen(
        [python_exe, "kokoro_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=server_env,
    )

    def _stream_server():
        for line in server_proc.stdout:
            # Uncomment if you want to inspect server stdout:
            # print(f"  [server] {line.strip()}", flush=True)
            pass

    threading.Thread(target=_stream_server, daemon=True).start()

    try:
        if not wait_for_server(server_proc):
            print("ERROR: Server failed to start.")
            return 1

        voices_dict = get_voices()
        total = len(voices_dict)
        print(f"Loaded {total} voices from server catalogue.")
        print(f"Sample text: \"{SAMPLE_TEXT}\"\n")
        print(f"{'-'*75}")
        print(f"{'#':<3} {'Voice ID':<14} {'Name':<10} {'Gender':<8} {'Accent':<10} {'Status':<6} {'Details'}")
        print(f"{'-'*75}")

        results = []
        for idx, (vid, meta) in enumerate(voices_dict.items(), start=1):
            name = meta.get("name", vid)
            gender = meta.get("gender", "")
            accent = meta.get("accent", "")
            ok, msg = test_voice(vid, meta)
            status_str = "PASS" if ok else "FAIL"
            print(f"{idx:02d}  {vid:<14} {name:<10} {gender:<8} {accent:<10} {status_str:<6} {msg}", flush=True)
            results.append((vid, ok, msg))

        passed = sum(1 for _, ok, _ in results if ok)
        failed = sum(1 for _, ok, _ in results if not ok)

        print(f"{'='*75}")
        print(f"TEST SUMMARY: {passed}/{total} Passed, {failed} Failed")
        print(f"Audio files directory: {OUT_DIR.resolve()}")
        print(f"{'='*75}\n")
        return 0 if failed == 0 else 1

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except Exception:
            server_proc.kill()

if __name__ == "__main__":
    sys.exit(main())
