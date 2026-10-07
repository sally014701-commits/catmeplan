import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / "backend/.venv/bin/python"


def use_project_python() -> None:
    if Path(sys.prefix) != VENV_PYTHON.parent.parent:
        os.execv(VENV_PYTHON, [str(VENV_PYTHON), str(Path(__file__).resolve())])


def main() -> None:
    use_project_python()

    import ngrok
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    frontend_port = os.environ.get("PORT", "8000")
    backend_port = os.environ.get("BACKEND_PORT", "8001")
    env = os.environ.copy()
    env["BACKEND_URL"] = f"http://127.0.0.1:{backend_port}"

    backend_command = [
        str(ROOT / "backend/.venv/bin/uvicorn"),
        "backend.app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        backend_port,
    ]
    if (ROOT / ".env").is_file():
        backend_command.extend(["--env-file", str(ROOT / ".env")])

    backend = subprocess.Popen(
        backend_command,
        cwd=ROOT,
        env=env,
    )
    frontend = subprocess.Popen(
        [
            "npm",
            "--prefix",
            str(ROOT / "frontend"),
            "run",
            "dev",
            "--",
            "--hostname",
            "0.0.0.0",
            "--port",
            frontend_port,
        ],
        cwd=ROOT,
        env=env,
    )

    forwarder = None
    if os.environ.get("NGROK_AUTHTOKEN"):
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "")
        domain = os.environ.get("NGROK_DOMAIN") or urlparse(redirect_uri).hostname
        forward_options = {"authtoken_from_env": True}
        if domain and domain.endswith(".ngrok-free.dev"):
            forward_options["domain"] = domain
        forwarder = ngrok.forward(f"localhost:{frontend_port}", **forward_options)

    print(f"Local URL:  http://127.0.0.1:{frontend_port}", flush=True)
    if forwarder:
        print(f"Public URL: {forwarder.url()}", flush=True)
    try:
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if forwarder:
            ngrok.disconnect()
        for process in (frontend, backend):
            process.terminate()
        for process in (frontend, backend):
            process.wait()


if __name__ == "__main__":
    sys.exit(main())
