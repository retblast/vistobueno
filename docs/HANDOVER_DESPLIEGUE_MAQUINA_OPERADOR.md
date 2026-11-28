# Handover — despliegue en la máquina del operador

Guía para instalar y verificar VistoBueno en la PC de la biblioteca.
Complementa `README.md`, `docs/CONTRATO_API.md` y el handover de la
auditoría 2026-10-26.

> Los pasos de instalación de la máquina (Linux, macOS y Windows 11 con
> WSL2) están en [`docs/INSTALACION.md`](INSTALACION.md). Este documento
> cubre la configuración y la verificación de seguridad del despliegue.

> Este documento cubre la **instalación**. La sesión de prueba con la
> instancia real de DSpace tiene su propio kit, con el checklist de
> ejecución paso a paso: `docs/PILOTO_OPERADOR.md`.

## 1. Qué protege el despliegue

La API maneja datos personales del estudiante (DNI, ORCID, resumen),
documentos oficiales (constancias) y trabajo de CPU (validación). El
despliegue estándar es local: la app, la SPA y el userscript viven en la
misma máquina. El control se apoya en tres capas:

1. **Bind local**: `uvicorn` escucha en `127.0.0.1` (no en `0.0.0.0`).
2. **Peer loopback**: cada endpoint rechaza con `403` a un peer remoto
   que no presente el token.
3. **Header `Host`**: cada petición con un `Host` ajeno recibe `400`.
   Esta capa cierra el DNS rebinding.

## 2. Checklist de instalación

| Paso | Acción | Verificación |
|------|--------|--------------|
| 1 | Arrancar con el [lanzador](INSTALACION.md#37-crear-el-acceso-directo) | `ss -ltnp` muestra `127.0.0.1:8000` |
| 2 | No pasar `--proxy-headers` | el lanzador deshabilita las cabeceras de proxy |
| 3 | Un solo worker | no agregar `--workers` |
| 4 | Firewall: bloquear el puerto 8000 desde la red | `curl` desde otro equipo → conexión rechazada |
| 5 | Copiar el Modelo B oficial que ya tiene el operador y guardar la firma según [§3.5](INSTALACION.md#35-preparar-la-constancia-y-el-registro) | el papeleo de prueba genera la constancia y la fila del registro con la firma |
| 6 | Solo si se expone: `VISTOBUENO_API_TOKEN` + `VISTOBUENO_HOST` + el host del peer en `VISTOBUENO_HOSTS` | peer remoto sin token → `403`; con token y host listado → `200`; con token pero host no listado → `400` |

Verificación local:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs
# esperado: 200

curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Host: atacante.example" http://127.0.0.1:8000/docs
# esperado: 400
```

> **Peer remoto**: necesita las dos capas. El `Host` se comprueba antes
> que el token, así que un token válido con un `Host` no listado recibe
> `400`, no `200`. Para que entre, define `VISTOBUENO_HOSTS` con la
> dirección o el dominio del peer (el puerto se ignora) y manda el header
> `X-VistoBueno-Token` en cada petición.

## 3. Prueba manual de DNS rebinding

El chequeo de `Host` es la mitigación. Esta prueba confirma el
comportamiento en cada navegador. Se hace en la PC del operador, con la
API corriendo en `127.0.0.1:8001` (un puerto libre distinto del real).
La página y la API comparten esquema, host y puerto, así que el
navegador las considera el mismo origen.

1. Agregar una entrada al archivo de hosts (`/etc/hosts` en Linux/macOS,
   `C:\Windows\System32\drivers\etc\hosts` en Windows):

   ```
   127.0.0.2 rebind.local
   ```

2. Servir una página de prueba desde `127.0.0.2:8001`:

   ```html
   <script>
     fetch("/ficha-pendiente")
       .then((r) => r.text())
       .then((t) => {
         document.title = "LEIDO: " + t.slice(0, 80);
       });
   </script>
   ```

3. Abrir `http://rebind.local:8001/evil.html` en el navegador.

4. **Sin recargar**, cambiar la entrada del archivo de hosts a:

   ```
   127.0.0.1 rebind.local
   ```

5. Leer el título de la pestaña.

Resultado esperado con la app endurecida (Chrome, Firefox y GNOME
Web/WebKit): el título no cambia y la petición recibe `400`. Si el título
muestra la ficha, el navegador logró leer la API.

Control positivo (opcional): con `VISTOBUENO_HOSTS=*` en el entorno del
servidor, repetir los pasos. El título debe mostrar la respuesta de la
API (la ficha o el `404` de "sin ficha pendiente"). Eso demuestra que el
escape `*` desactiva el control y que el control es lo que lo bloquea.

> La variable `VISTOBUENO_HOSTS` se lee en cada petición: no hace falta
> reiniciar el servidor para alternar el control.

## 4. Actualizar el userscript

El userscript se instala en Tampermonkey desde
`tools/dspace-fill/dist/vistobueno-dspace-fill.user.js` (el CI verifica
que el `dist/` no se desvía del código fuente). Desde la versión 1.1.0
el script declara `@updateURL` y `@downloadURL` al `dist` del repositorio:
Tampermonkey ofrece la actualización sola. Si el operador tiene la
versión anterior pegada a mano, tiene que **reemplazar el script** por
el `dist` actual (copiar de nuevo el contenido en el editor de
Tampermonkey y guardar).

Para saber qué versión tiene el operador: Tampermonkey muestra la versión
en la lista de scripts instalados; el `dist` declara la suya en la línea
`@version`.

## 5. Rollback

- Si una actualización deja la API sin responder, volver al commit
  anterior y reiniciar el proceso. El estado en memoria (buzón) se
  pierde en cualquier reinicio; el operador re-valida y vuelve a preparar
  la ficha.
- Si hay que desactivar el chequeo de `Host` por una integración
  legítima, definir `VISTOBUENO_HOSTS` con el dominio exacto. No usar
  `*` en producción: deja el DNS rebinding sin mitigación.
