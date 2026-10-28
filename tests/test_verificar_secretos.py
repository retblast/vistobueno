"""Tests del verificador de secretos SMTP (scripts/verificar_secretos.py).

El verificador es la capa estricta anti-filtración de credenciales: estos
tests prueban que BLOQUEA asignaciones con valor real y archivos .env, y que
PERMITE menciones documentales y placeholders. Los "secretos" aquí son
cadenas de prueba obviamente falsas, y este archivo está excluido del
escaneo (ver EXCLUIDOS en el script) precisamente para poder probarlo.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verificar_secretos.py"


def correr(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Ejecuta el verificador como subproceso (igual que pre-commit/CI)."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_detecta_password_con_valor_real(tmp_path):
    """Una asignación con valor no-placeholder debe salir con código 1."""
    archivo = tmp_path / "config.txt"
    archivo.write_text(
        "VISTOBUENO_SMTP_HOST=smtp.unitru.edu.pe\n"
        "VISTOBUENO_SMTP_PASSWORD=Secr3to-Institucional-XYZ\n",
        encoding="utf-8",
    )
    r = correr([str(archivo)])
    assert r.returncode == 1
    assert str(archivo) in r.stdout
    # El valor nunca se imprime (no repetir posibles secretos en logs)
    assert "Secr3to" not in r.stdout


def test_detecta_password_con_dos_puntos_y_comillas(tmp_path):
    """Formato YAML/JSON (`VAR: "valor"`) también debe bloquearse."""
    archivo = tmp_path / "config.yaml"
    archivo.write_text('VISTOBUENO_SMTP_PASSWORD: "hunter2-real"\n', encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 1


def test_detecta_password_dspace_con_valor_real(tmp_path):
    """La contraseña de la cuenta de servicio de DSpace también se bloquea."""
    archivo = tmp_path / "deploy_dspace.txt"
    archivo.write_text("VISTOBUENO_DSPACE_PASSWORD=Clave-Deposito-Real\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 1
    assert "VISTOBUENO_DSPACE_PASSWORD" in r.stdout
    # El valor nunca se imprime (no repetir posibles secretos en logs)
    assert "Clave-Deposito" not in r.stdout


def test_detecta_usuario_dspace_con_valor_real(tmp_path):
    """El usuario de la cuenta de servicio es credencial (DSPACE_API.md §8)."""
    archivo = tmp_path / "deploy_dspace.txt"
    archivo.write_text("VISTOBUENO_DSPACE_USER=cuenta-repositorio\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 1
    assert "VISTOBUENO_DSPACE_USER" in r.stdout


def test_permite_configuracion_no_sensible_dspace(tmp_path):
    """Flag, URL y colección no son credenciales: configuran, no autentican."""
    archivo = tmp_path / "servidor.md"
    archivo.write_text(
        "VISTOBUENO_DSPACE=1\n"
        "VISTOBUENO_DSPACE_URL=https://repositorio.unitru.edu.pe/server/api\n"
        "VISTOBUENO_DSPACE_COLECCION=uuid-de-coleccion\n",
        encoding="utf-8",
    )
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout


def test_permite_placeholders_dummy(tmp_path):
    """Valores dummy/prueba/test/changeme/<valor> no son secreto."""
    archivo = tmp_path / "ejemplos.txt"
    archivo.write_text(
        "VISTOBUENO_SMTP_PASSWORD=dummy\n"
        'VISTOBUENO_SMTP_PASSWORD: "prueba"\n'
        "VISTOBUENO_SMTP_PASSWORD=test\n"
        "VISTOBUENO_SMTP_PASSWORD=changeme\n"
        "VISTOBUENO_SMTP_PASSWORD=<valor>\n",
        encoding="utf-8",
    )
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout


def test_permite_autorreferencia_y_vacio(tmp_path):
    """Autorreferencias ($VAR) y asignación vacía no filtran nada."""
    archivo = tmp_path / "deploy.txt"
    archivo.write_text(
        "export NUEVA=$VISTOBUENO_SMTP_PASSWORD\nVISTOBUENO_SMTP_PASSWORD=\n",
        encoding="utf-8",
    )
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout


def test_permite_menciones_documentales(tmp_path):
    """Mencionar la variable sin asignar valor (docs/AGENTS) es válido."""
    archivo = tmp_path / "docs.md"
    archivo.write_text(
        "| `VISTOBUENO_SMTP_PASSWORD` | Contraseña SMTP — nunca al repo |\n"
        "Configure VISTOBUENO_SMTP_PASSWORD en su entorno local.\n",
        encoding="utf-8",
    )
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout


def test_bloquea_archivo_env_por_nombre(tmp_path):
    """Cualquier archivo .env o .env.* es violación por sí mismo."""
    (tmp_path / ".env").write_text("algo=1\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("VISTOBUENO_SMTP_HOST=smtp\n", encoding="utf-8")
    r = correr([str(tmp_path / ".env"), str(tmp_path / ".env.local")])
    assert r.returncode == 1
    assert ".env" in r.stdout
    assert ".env.local" in r.stdout


def test_permite_env_example_pero_escanea_su_contenido(tmp_path):
    """.env.example es plantilla documental (convención Vite), no un secret.

    El archivo en sí es válido, pero una asignación con valor REAL dentro de
    él debe detectarse igual: el contenido siempre se escanea.
    """
    bueno = tmp_path / ".env.example"
    bueno.write_text("VITE_API_URL=\n", encoding="utf-8")
    r = correr([str(bueno)])
    assert r.returncode == 0, r.stdout

    malo = tmp_path / "otro.env.example"
    malo.write_text("VISTOBUENO_SMTP_PASSWORD=Clave-De-Prueba-XYZ\n", encoding="utf-8")
    r = correr([str(malo)])
    assert r.returncode == 1
    assert "otro.env.example" in r.stdout


def test_all_escanea_arbol_completo(tmp_path, monkeypatch):
    """Modo --all (CI) detecta violaciones anidadas en el árbol."""
    (tmp_path / "deploy").mkdir()
    secreto = tmp_path / "deploy" / "provision.sh"
    secreto.write_text("VISTOBUENO_SMTP_PASSWORD=Clave-De-Prueba-XYZ\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    r = correr(["--all"])
    assert r.returncode == 1
    assert "provision.sh" in r.stdout


# ---------------------------------------------------------------------------
# Cobertura ampliada (auditoría 2026-10-26, AUD-22)
# ---------------------------------------------------------------------------


def test_detecta_nombre_generico_de_secreto(tmp_path):
    """Un nombre en mayúsculas que termina en PASSWORD también se bloquea."""
    archivo = tmp_path / "config.txt"
    archivo.write_text("DB_PASSWORD=Clave-De-Prueba-XYZ\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 1
    assert "DB_PASSWORD" in r.stdout
    assert "Clave-Real" not in r.stdout


def test_detecta_token_generico(tmp_path):
    """TOKEN en mayúsculas es un nombre de secreto, aunque no sea del proyecto."""
    archivo = tmp_path / "deploy.yml"
    archivo.write_text("GITHUB_TOKEN: ghp_abc123def456\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 1
    assert "GITHUB_TOKEN" in r.stdout


def test_detecta_clave_con_guion_bajo_interno(tmp_path):
    """AWS_SECRET_ACCESS_KEY termina en ACCESS_KEY: también es un secreto."""
    archivo = tmp_path / "aws.env.example"
    archivo.write_text("AWS_SECRET_ACCESS_KEY=AKIA-REAL-987654\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 1


def test_permite_nombre_que_no_termina_en_sufijo(tmp_path):
    """El sufijo tiene que ser la última palabra: `..._TOKEN_BUZON` no es secreto."""
    archivo = tmp_path / "api.py"
    archivo.write_text('CABECERA_TOKEN_BUZON = "X-VistoBueno-Token"\n', encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout


def test_permite_nombre_sin_separador(tmp_path):
    """`NMTOKEN` no es una variable de entorno: no se marca (límite declarado)."""
    archivo = tmp_path / "tipos.d.ts"
    archivo.write_text("NMTOKEN = 'nombre'\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout


def test_permite_lectura_del_entorno(tmp_path):
    """`os.environ.get(...)` no es un valor: es una lectura."""
    archivo = tmp_path / "config.py"
    archivo.write_text(
        "PASSWORD=os.environ.get('VISTOBUENO_SMTP_PASSWORD', '')\n",
        encoding="utf-8",
    )
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout


def test_permite_placeholder_entre_angulos(tmp_path):
    """`<mi-token>` es la convención documental de este repo."""
    archivo = tmp_path / "leeme.md"
    archivo.write_text("API_TOKEN=<mi-token>\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout


def test_detecta_url_con_credenciales(tmp_path):
    """Una URL con usuario y clave embebidos es una filtración."""
    archivo = tmp_path / "nota.md"
    archivo.write_text("Endpoint: https://usuario:clave-real@ejemplo.org/api\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 1
    assert "credenciales" in r.stdout
    assert "clave-real" not in r.stdout


def test_permite_url_con_puerto_sin_credenciales(tmp_path):
    """Una URL con puerto no lleva credenciales: no se marca."""
    archivo = tmp_path / "leeme.md"
    archivo.write_text("La API vive en http://127.0.0.1:8000/docs\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout


def test_detecta_bloque_yaml_multilinea(tmp_path):
    """El valor de un bloque YAML (`|`) está en las líneas de abajo."""
    archivo = tmp_path / "secreto.yaml"
    archivo.write_text(
        "VISTOBUENO_SMTP_PASSWORD: |\n  Clave-De-Prueba-XYZ\n",
        encoding="utf-8",
    )
    r = correr([str(archivo)])
    assert r.returncode == 1
    assert "VISTOBUENO_SMTP_PASSWORD" in r.stdout
    assert "Clave-Real" not in r.stdout


def test_permite_bloque_yaml_con_placeholder(tmp_path):
    """Un bloque YAML con placeholder no es una filtración."""
    archivo = tmp_path / "plantilla.yaml"
    archivo.write_text("VISTOBUENO_SMTP_PASSWORD: |\n  <valor>\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout


def test_detecta_secreto_en_la_segunda_linea_del_bloque(tmp_path):
    """El bloque YAML se lee entero: un placeholder arriba no tapa el secreto."""
    archivo = tmp_path / "secreto.yaml"
    archivo.write_text(
        "VISTOBUENO_SMTP_PASSWORD: |\n  <valor>\n  valorRealEnSegundaLineaDelBloque\n",
        encoding="utf-8",
    )
    r = correr([str(archivo)])
    assert r.returncode == 1
    assert "VISTOBUENO_SMTP_PASSWORD" in r.stdout
    assert "valorReal" not in r.stdout


def test_detecta_secret_key(tmp_path):
    """Un nombre que termina en SECRET_KEY es un nombre de secreto."""
    archivo = tmp_path / "cliente.yaml"
    archivo.write_text("CLIENT_SECRET_KEY: abcd1234efgh5678\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 1
    assert "CLIENT_SECRET_KEY" in r.stdout


def test_detecta_encryption_key(tmp_path):
    """Un nombre que termina en ENCRYPTION_KEY también."""
    archivo = tmp_path / "cifrado.yaml"
    archivo.write_text("ENCRYPTION_KEY: 0123456789abcdef\n", encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 1


def test_permite_valor_de_prueba_sin_excluir_el_archivo(tmp_path):
    """La forma `*-de-prueba` es un placeholder: no obliga a excluir el archivo."""
    archivo = tmp_path / "tests_de_otro_modulo.py"
    archivo.write_text('API_TOKEN = "secreto-de-prueba"\n', encoding="utf-8")
    r = correr([str(archivo)])
    assert r.returncode == 0, r.stdout
