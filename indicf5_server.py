"""
Standalone Persistent HTTP Server for IndicF5 (ai4bharat/IndicF5)
Enables zero-shot Hindi speech synthesis across process/venv boundaries.
Loads model into VRAM once on startup; serves synthesis requests on port 8765.
"""

import argparse
import io
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Windows UTF-8 console configuration
if sys.stdout and hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "encoding") and sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import soundfile as sf
import torch

# --- Safety Patch: Disable torch.compile on Windows for IndicF5 / Vocos ---
if hasattr(torch, "compile"):
    _original_compile = torch.compile
    def _noop_compile(fn=None, *args, **kwargs):
        if fn is None:
            return lambda f: f
        return fn
    torch.compile = _noop_compile
# --- End Safety Patch ---

from huggingface_hub import hf_hub_download
from safetensors.torch import load_file
from transformers import AutoModel
from f5_tts.infer.utils_infer import preprocess_ref_audio_text, infer_process

# Global state
GLOBAL_MODEL = None
GLOBAL_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
SERVER_INSTANCE = None
REF_CACHE = {}


def load_model(hf_token: str = None, device: str = "cuda"):
    """Load IndicF5 model once and load mapped safetensors weights."""
    global GLOBAL_MODEL, GLOBAL_DEVICE
    GLOBAL_DEVICE = device

    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token
        try:
            import huggingface_hub
            huggingface_hub.login(token=hf_token, add_to_git_credential=False)
        except Exception:
            pass

    print(f"[indicf5_server] Loading IndicF5 on device: {device.upper()}...")
    t0 = time.perf_counter()

    load_kwargs = {"trust_remote_code": True}
    token_to_use = hf_token or os.getenv("HF_TOKEN", None)
    if token_to_use:
        load_kwargs["token"] = token_to_use

    model = AutoModel.from_pretrained("ai4bharat/IndicF5", **load_kwargs)

    # Download safetensors and load state dict (stripping _orig_mod. from keys)
    safetensors_path = hf_hub_download(
        "ai4bharat/IndicF5",
        filename="model.safetensors",
        token=token_to_use
    )
    sd = load_file(safetensors_path, device=str(device))
    cleaned_sd = {}
    for k, v in sd.items():
        clean_key = k.replace("ema_model._orig_mod.", "").replace("ema_model.", "").replace("_orig_mod.", "")
        cleaned_sd[clean_key] = v

    model.ema_model.load_state_dict(cleaned_sd, strict=False)

    if device == "cuda":
        model = model.to("cuda")
        model.ema_model = model.ema_model.to("cuda")
        model.vocoder = model.vocoder.to("cuda")
        allocated_mb = torch.cuda.memory_allocated() / (1024 ** 2)
        print(f"[indicf5_server] Model ready in {time.perf_counter() - t0:.2f}s | VRAM Footprint: {allocated_mb:.1f} MB")
    else:
        print(f"[indicf5_server] Model ready in {time.perf_counter() - t0:.2f}s on CPU.")

    GLOBAL_MODEL = model
    return model


def get_cached_ref(ref_audio_path: str, ref_text: str):
    """Cache preprocessed reference audio/text to save repeated I/O."""
    key = (os.path.abspath(ref_audio_path), ref_text)
    if key not in REF_CACHE:
        if not os.path.isfile(ref_audio_path):
            raise FileNotFoundError(f"Reference audio not found: {ref_audio_path}")
        audio, text = preprocess_ref_audio_text(ref_audio_path, ref_text)
        REF_CACHE[key] = (audio, text)
    return REF_CACHE[key]


class IndicF5RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence routine access logs, print only important messages
        pass

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            vram_mb = torch.cuda.memory_allocated() / (1024 ** 2) if GLOBAL_DEVICE == "cuda" else 0.0
            self._send_json(200, {
                "status": "ok",
                "engine": "indicf5",
                "device": GLOBAL_DEVICE,
                "vram_allocated_mb": round(vram_mb, 1)
            })
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        if self.path == "/shutdown":
            self._send_json(200, {"status": "shutting_down"})
            print("[indicf5_server] Shutdown request received. Exiting server...")
            def _kill():
                time.sleep(0.5)
                if SERVER_INSTANCE:
                    SERVER_INSTANCE.shutdown()
                os._exit(0)
            threading.Thread(target=_kill, daemon=True).start()
            return

        if self.path == "/generate":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._send_json(400, {"error": "Empty body"})
                return

            body = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(body)
            except Exception as e:
                self._send_json(400, {"error": f"Invalid JSON: {e}"})
                return

            text = payload.get("text", "").strip()
            ref_audio_path = payload.get("ref_audio_path", "")
            ref_text = payload.get("ref_text", "")
            speed = float(payload.get("speed", 0.80))
            output_path = payload.get("output_path", None)

            if not text:
                self._send_json(400, {"error": "Missing 'text' field"})
                return
            if not ref_audio_path or not ref_text:
                self._send_json(400, {"error": "Missing 'ref_audio_path' or 'ref_text'"})
                return

            t_start = time.perf_counter()
            try:
                ref_audio, ref_txt = get_cached_ref(ref_audio_path, ref_text)
                
                audio, sample_rate, _ = infer_process(
                    ref_audio,
                    ref_txt,
                    text,
                    GLOBAL_MODEL.ema_model,
                    GLOBAL_MODEL.vocoder,
                    mel_spec_type="vocos",
                    speed=speed,
                    device=GLOBAL_DEVICE,
                )

                if isinstance(audio, torch.Tensor):
                    audio = audio.detach().cpu().numpy()
                audio = np.array(audio, dtype=np.float32)
                duration_sec = len(audio) / sample_rate
                elapsed_sec = time.perf_counter() - t_start

                if output_path:
                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                    sf.write(output_path, audio, samplerate=sample_rate)
                    self._send_json(200, {
                        "status": "completed",
                        "duration_sec": round(duration_sec, 2),
                        "elapsed_sec": round(elapsed_sec, 2),
                        "sample_rate": sample_rate,
                        "output_path": output_path
                    })
                else:
                    # Stream raw WAV audio
                    buf = io.BytesIO()
                    sf.write(buf, audio, samplerate=sample_rate, format="WAV")
                    wav_bytes = buf.getvalue()

                    self.send_response(200)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Length", str(len(wav_bytes)))
                    self.send_header("X-Audio-Duration", str(round(duration_sec, 2)))
                    self.end_headers()
                    self.wfile.write(wav_bytes)

            except Exception as e:
                print(f"[indicf5_server] Generation error: {e}")
                self._send_json(500, {"error": str(e)})
            return

        self._send_json(404, {"error": "Not Found"})


def run_server(host: str = "127.0.0.1", port: int = 8765, hf_token: str = None, device: str = "cuda"):
    global SERVER_INSTANCE
    load_model(hf_token=hf_token, device=device)

    server_address = (host, port)
    SERVER_INSTANCE = ThreadingHTTPServer(server_address, IndicF5RequestHandler)
    print(f"[indicf5_server] IndicF5 HTTP Server listening on http://{host}:{port}")
    try:
        SERVER_INSTANCE.serve_forever()
    except KeyboardInterrupt:
        print("\n[indicf5_server] Server stopped by user.")
    finally:
        SERVER_INSTANCE.server_close()


def main():
    parser = argparse.ArgumentParser(description="IndicF5 Persistent TTS Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    parser.add_argument("--hf-token", default=os.getenv("HF_TOKEN", None), help="Hugging Face User Access Token")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu", help="Device (cuda or cpu)")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, hf_token=args.hf_token, device=args.device)


if __name__ == "__main__":
    main()
