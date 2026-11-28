"""Tests del lanzador de escritorio (WSL + SPA)."""

import http.server
import os
import socket
import threading

from scripts import lanzar_app


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def test_is_wsl_por_variable(monkeypatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    assert lanzar_app.is_wsl() is True


def test_is_wsl_por_proc(monkeypatch, tmp_path):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    proc = tmp_path / "osrelease"
    proc.write_text("5.15.0-microsoft-standard-WSL2\n", encoding="utf-8")
    monkeypatch.setattr(lanzar_app, "PROC_VERSION", proc)
    assert lanzar_app.is_wsl() is True


def test_is_wsl_fuera(monkeypatch, tmp_path):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    proc = tmp_path / "osrelease"
    proc.write_text("6.1.0-13-amd64\n", encoding="utf-8")
    monkeypatch.setattr(lanzar_app, "PROC_VERSION", proc)
    assert lanzar_app.is_wsl() is False


def test_browser_command_windows():
    assert lanzar_app.browser_command("http://127.0.0.1:8000/", windows=True) == [
        "cmd.exe",
        "/c",
        "start",
        "",
        "http://127.0.0.1:8000/",
    ]


def test_browser_command_local():
    assert lanzar_app.browser_command("http://127.0.0.1:8000/", windows=False) is None


def test_open_browser_windows_sin_cmd(monkeypatch):
    llamadas: list[str] = []
    monkeypatch.setattr(lanzar_app.shutil, "which", lambda _: None)
    monkeypatch.setattr(lanzar_app.webbrowser, "open", lambda url: llamadas.append(url))

    lanzar_app.open_browser("http://127.0.0.1:8000/", windows=True)

    assert llamadas == ["http://127.0.0.1:8000/"]


def test_wait_for_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/"
        assert lanzar_app.wait_for_server(url, timeout=2) is True
    finally:
        server.shutdown()
        server.server_close()


def test_wait_for_server_timeout():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}/"
    assert lanzar_app.wait_for_server(url, timeout=0.3) is False


def test_build_available(tmp_path):
    assert lanzar_app.build_available(tmp_path) is False
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    assert lanzar_app.build_available(tmp_path) is True


def test_main_sin_build(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(lanzar_app, "FRONTEND_DIST", tmp_path)
    assert lanzar_app.main(["--sin-navegador"]) == 1
    assert "frontend/dist/index.html" in capsys.readouterr().out


def test_cargar_firma_local_acepta_utf8_de_windows(monkeypatch, tmp_path):
    monkeypatch.setenv("VISTOBUENO_FIRMA", "")
    archivo = tmp_path / "firma.txt"
    archivo.write_bytes("\ufeffMaría Torres\r\n".encode("utf-8"))
    lanzar_app.load_local_signature(archivo)
    assert os.environ["VISTOBUENO_FIRMA"] == "María Torres"


def test_cargar_firma_local_respeta_el_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("VISTOBUENO_FIRMA", "Firma configurada")
    archivo = tmp_path / "firma.txt"
    archivo.write_text("Firma local", encoding="utf-8")
    lanzar_app.load_local_signature(archivo)
    assert os.environ["VISTOBUENO_FIRMA"] == "Firma configurada"


def test_cargar_firma_local_es_opcional(monkeypatch, tmp_path):
    monkeypatch.delenv("VISTOBUENO_FIRMA", raising=False)
    lanzar_app.load_local_signature(tmp_path / "firma.txt")
    assert "VISTOBUENO_FIRMA" not in os.environ


def test_cargar_firma_local_usa_la_primera_linea(monkeypatch, tmp_path):
    monkeypatch.setenv("VISTOBUENO_FIRMA", "")
    archivo = tmp_path / "firma.txt"
    archivo.write_text("\n  \nMaría Torres\nSegunda línea\n", encoding="utf-8")
    lanzar_app.load_local_signature(archivo)
    assert os.environ["VISTOBUENO_FIRMA"] == "María Torres"


def test_main_firma_invalida(monkeypatch, tmp_path, capsys):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    firma = tmp_path / "firma.txt"
    firma.write_bytes(b"\xff\xfe")
    monkeypatch.setattr(lanzar_app, "FRONTEND_DIST", tmp_path)
    monkeypatch.setattr(lanzar_app, "LOCAL_SIGNATURE", firma)
    monkeypatch.setenv("VISTOBUENO_FIRMA", "")
    assert lanzar_app.main(["--sin-navegador"]) == 1
    assert "firma.txt" in capsys.readouterr().out
