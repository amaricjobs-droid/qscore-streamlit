import os, sys, subprocess, time, requests
import webview

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
os.chdir(ROOT)

env = os.environ.copy()
env.setdefault("BASE_URL", "http://127.0.0.1:8001")
env.setdefault("CALENDLY_URL", "https://calendly.com/your-clinic/bp-check")
env.setdefault("MSG_API", env["BASE_URL"])

def start_proc(args):
    si = None
    cf = 0
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        cf = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(args, cwd=ROOT, env=env, startupinfo=si, creationflags=cf)

# Start FastAPI (Messaging Center)
uvicorn_proc = start_proc([sys.executable, "-m", "uvicorn", "messaging_center.main:app", "--port", "8001"])

# Start Streamlit headless
streamlit_proc = start_proc([sys.executable, "-m", "streamlit", "run", "app/app.py", "--server.headless", "true"])

def wait_url(url, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

# Wait for services
wait_url("http://127.0.0.1:8001", timeout=60)
wait_url("http://127.0.0.1:8501", timeout=60)

# Create native window
window = webview.create_window("Q-Score Suite", "http://127.0.0.1:8501", width=1280, height=860, resizable=True)

def _cleanup():
    for p in (streamlit_proc, uvicorn_proc):
        if p and p.poll() is None:
            try:
                p.terminate()
                time.sleep(0.5)
                if p.poll() is None:
                    p.kill()
            except Exception:
                pass

window.events.closed += _cleanup

# Use Edge WebView2 on Windows
webview.start(gui="edgechromium")
