# Servidor de Impresión Fiscal y No Fiscal (Multiplataforma)

Este proyecto es un servidor de impresión basado en Flask (Python) diseñado para actuar como un puente robusto entre una aplicación web (como un sistema POS) y las impresoras USB locales.

Maneja dos tipos de impresión de forma concurrente:
1.  **Impresión Fiscal:** Para impresoras fiscales (probado con modelos TFHKA) para emitir facturas, notas de crédito y reportes X/Z.
2.  **Impresión No Fiscal:** Para impresoras térmicas de recibos (tickeras) para imprimir comandas de cocina, notas de entrega, recibos de pago y diagnósticos.

La característica principal de este servidor es su capacidad para ser **multiplataforma** (detecta automáticamente Windows/Linux) y **multi-caja** (gestiona múltiples impresoras fiscales desde una sola instancia).

## 🚀 Características Principales

* **Impresión Fiscal y No Fiscal:** Maneja ambos mundos de impresión desde una sola API.
* **Detección Automática de SO:** El mismo script funciona en Windows y Linux sin necesidad de cambios. Adapta automáticamente las rutas (`C:\` vs. `/home/`) y los comandos de ejecución (`IntTFHKA.exe` vs. `tfinulx`).
* **Arquitectura Multi-Caja (UUID):** Permite gestionar múltiples impresoras fiscales conectadas al mismo servidor. Cada impresora se identifica por un `terminalUUID` único, lo que permite al POS centralizado dirigir impresiones a cajas específicas.
* **Manejo de Concurrencia:** Utiliza un sistema de `Lock` por cada impresora fiscal para evitar que dos solicitudes intenten imprimir en la misma impresora al mismo tiempo, previniendo corrupción de datos.
* **Sincronización Robusta:** Fuerza la sincronización de archivos con el disco (`fsync` / `sync`) antes de enviar a imprimir, evitando problemas de caché del SO (crítico en Linux) donde la impresora podría leer un archivo de comandos vacío o incompleto.
* **API RESTful Sencilla:** Se controla todo mediante endpoints JSON simples.

---

## 📋 Requisitos Previos

Asegúrate de tener lo siguiente instalado en el equipo que actuará como servidor de impresión.

### 1. Software
* [Python 3.x](https://www.python.org/downloads/)
* Las siguientes librerías de Python (instálalas con `pip`):
    ```bash
    pip install Flask Flask-CORS pyusb python-escpos
    ```

### 2. Controladores (Drivers)

#### Para Impresora Fiscal (Windows y Linux)
* Necesitarás el **ejecutable** proporcionado por el fabricante para la comunicación.
    * **En Windows:** Generalmente un archivo `.exe` como `IntTFHKA.exe` o `Tfhka.exe`.
    * **En Linux:** Un binario compilado, como `tfinulx`.

#### Para Impresora No Fiscal (Tickera)
* **En Linux:** Generalmente funciona sin drivers adicionales (`pyusb` la detecta).
* **En Windows (¡IMPORTANTE!):** La impresora térmica estándar instala un driver de Windows que *bloquea* el acceso de `pyusb`. Es **necesario** usar la herramienta [**Zadig**](https://zadig.akeo.ie/) para reemplazar el driver de la impresora por `libusb-win32` o `libusbK`. Sin este paso, la impresión no fiscal fallará en Windows.

---

## ⚙️ Configuración

La configuración se divide en dos partes: editar las constantes en el script y organizar la estructura de carpetas.

### 1. Configuración del Script

Abre el archivo `.py` y ajusta las siguientes variables en la sección de configuración:

```python
# --- CONFIGURACIÓN PARA IMPRESORA NO FISCAL (USB DIRECTO) ---
# ¡Obligatorio! Encuentra estos valores en el Administrador de Dispositivos (Win) o con `lsusb` (Linux)
VENDOR_ID = 0x0483
PRODUCT_ID = 0x5743
ANCHO_TICKET = 42

# --- CONFIGURACIÓN DE RUTAS DINÁMICAS (FISCAL) ---
# ¡Obligatorio! Ajusta estos valores según tu SO.
# El script detecta el SO, solo necesitas asegurarte de que estas rutas
# y ejecutables sean correctos para cada entorno.

if SISTEMA_OPERATIVO == "Windows":
    EXECUTABLE_FISCAL = "IntTFHKA.exe" 
    BASE_FISCAL_PATH = "C:\\ServidorFiscal" 
else:
    EXECUTABLE_FISCAL = "tfinulx"
    USER = "zante" # Cambia esto a tu usuario de Linux si es diferente
    BASE_FISCAL_PATH = f"/home/{USER}"
```

### 2. Estructura de Carpetas (Clave del Multi-Caja)

Este servidor está diseñado para que `BASE_FISCAL_PATH` sea la **carpeta contenedora** de todas tus impresoras. El sistema funciona asignando un **UUID (Identificador Único Universal)** a cada caja/impresora.

Tu aplicación POS deberá enviar este `terminalUUID` en cada solicitud a la API. El servidor usará ese UUID para encontrar la carpeta correcta y el ejecutable correspondiente.

**REGLA DE ORO:** Cada impresora fiscal debe tener su propia subcarpeta dentro de `BASE_FISCAL_PATH`, y el nombre de esa carpeta debe ser el `terminalUUID` de esa caja.

#### Ejemplo de Estructura en Windows

Si `BASE_FISCAL_PATH` es `C:\ServidorFiscal`:

```
C:\ServidorFiscal\
|
+--- 761beb8e-117b-4afe-bb3f-f71b1c75bf38\  <-- UUID Caja 1
|    |
|    +--- IntTFHKA.exe
|    +--- (otros .dll o archivos requeridos por el driver)
|
+--- a2b8e1f0-55d4-4a2e-83a0-9f8e2a1b9c4d\  <-- UUID Caja 2
|    |
|    +--- IntTFHKA.exe
|
+--- f4c1e9f2-8c4b-4f1e-a8d2-9b3e1f2a0d5c\  <-- UUID Caja 3
     |
     +--- IntTFHKA.exe
```

#### Ejemplo de Estructura en Linux

Si `BASE_FISCAL_PATH` es `/home/zante`:

```
/home/zante/
|
+--- 761beb8e-117b-4afe-bb3f-f71b1c75bf38/  <-- UUID Caja 1
|    |
|    +--- tfinulx
|
+--- a2b8e1f0-55d4-4a2e-83a0-9f8e2a1b9c4d/  <-- UUID Caja 2
|    |
|    +--- tfinulx
|
+--- f4c1e9f2-8c4b-4f1e-a8d2-9b3e1f2a0d5c/  <-- UUID Caja 3
     |
     +--- tfinulx
```
**Nota sobre Linux:** Asegúrate de que el archivo `tfinulx` tenga permisos de ejecución:
`chmod +x /home/zante/761beb8e-117b-4afe-bb3f-f71b1c75bf38/tfinulx`

---

## ▶️ Ejecución del Servidor

Una vez configurado, simplemente ejecuta el script con Python:

```bash
python servidor_impresion_adaptado.py
```

El servidor se iniciará en `http://0.0.0.0:5000` y estará listo para recibir solicitudes de tu aplicación POS.

---

## 🔌 API Endpoints

### Impresión Fiscal

#### `POST /imprimir-factura-fiscal`
Envía una factura fiscal.

* **Body (JSON):**
    ```json
    {
      "terminalUUID": "761beb8e-117b-4afe-bb3f-f71b1c75bf38",
      "cliente": {
        "razon_social": "Cliente de Prueba",
        "rif": "V123456789"
      },
      "items": [
        {
          "descripcion": "Producto 1",
          "cantidad": 1.0,
          "precio_unitario_con_iva": 10.0,
          "tasa_iva": 16.0
        },
        {
          "descripcion": "Producto 2 Exento",
          "cantidad": 2.0,
          "precio_unitario_con_iva": 5.0,
          "tasa_iva": 0.0
        }
      ],
      "pagos": [
        { "slot_fiscal": 1, "monto": 20.0 }
      ]
    }
    ```

#### `POST /imprimir-reporte-fiscal`
Imprime un reporte X o Z.

* **Body (JSON):**
    ```json
    {
      "terminalUUID": "761beb8e-117b-4afe-bb3f-f71b1c75bf38",
      "tipo": "X" 
    }
    ```
    (Usar `"tipo": "Z"` para el Reporte Z)

#### `GET /estado-impresora-fiscal/<terminal_uuid>`
Consulta el estado de la impresora fiscal (papel, errores, etc.).

* **Ejemplo de URL:** `http://localhost:5000/estado-impresora-fiscal/761beb8e-117b-4afe-bb3f-f71b1c75bf38`
* **Respuesta Exitosa:**
    ```json
    {
      "status_code": 4,
      "status_descripcion": "En modo fiscal y en espera.",
      "error_code": 0,
      "error_descripcion": "No hay error."
    }
    ```

#### `POST /test-fiscal/<terminal_uuid>`
Envía un comando de diagnóstico simple (Comando `D`) a la impresora fiscal.

* **Ejemplo de URL:** `http://localhost:5000/test-fiscal/761beb8e-117b-4afe-bb3f-f71b1c75bf38`

### Impresión No Fiscal (Tickera)

#### `GET /diagnostico`
Intenta conectarse a la impresora no fiscal (definida por `VENDOR_ID` y `PRODUCT_ID`). Útil para verificar la conexión y el driver (Zadig).

#### `POST /imprimir-factura`
Imprime una Nota de Entrega o Recibo de Pago no fiscal.

* **Body (JSON):** (Revisa el código para ver la estructura completa del JSON esperado).

#### `POST /imprimir-comanda`
Imprime una comanda de cocina.

* **Body (JSON):** (Revisa el código para ver la estructura completa del JSON esperado).

---

## ⚠️ Solución de Problemas Comunes

1.  **Error (No Fiscal): `¡Tickera USB no encontrada!`**
    * **En Windows:** No has usado **Zadig** para instalar el driver `libusb`. Este es el error más común.
    * **En Linux/Windows:** Verifica que `VENDOR_ID` y `PRODUCT_ID` en el script coincidan exactamente con los de tu impresora.

2.  **Error (Fiscal): `EJECUTABLE NO ENCONTRADO`**
    * Verifica que la variable `BASE_FISCAL_PATH` sea correcta.
    * Asegúrate de que la carpeta con el nombre `terminalUUID` que envías desde el POS existe dentro de `BASE_FISCAL_PATH`.
    * Asegúrate de que el archivo `IntTFHKA.exe` (o `tfinulx`) esté **dentro** de esa carpeta UUID.

3.  **Error (Fiscal): `Timeout: La impresora... no respondió`**
    * La impresora está desconectada o apagada.
    * **En Windows:** El puerto COM configurado en el driver fiscal no es el correcto.
    * **En Linux:** El usuario que ejecuta Python no tiene permisos para acceder al puerto serial/USB (ej. `/dev/ttyUSB0`). Añade tu usuario al grupo `dialout`: `sudo usermod -a -G dialout $USER` (y reinicia la sesión).

4.  **Error (Fiscal): `El archivo fue procesado... Retorno: 0` o `Fallo en SendFileCmd... se esperaban X, se enviaron 0`**
    * Este es el error de caché del SO. La versión del script en este repositorio ya incluye `fsync` y `sync` para prevenirlo. Si ves este error, asegúrate de estar usando la última versión del script.
