# Servidor de Impresión Fiscal The Factory HKA en Python

Este proyecto es un servidor web intermediario, escrito en Python con Flask, que permite a cualquier sistema de punto de venta (POS) comunicarse con las impresoras fiscales de The Factory HKA a través de su utilidad `IntTfhka.exe` (para Windows) o `Tfinulx` (para Linux).

El servidor expone un endpoint HTTP simple que recibe los datos de una factura en formato JSON y los traduce a la secuencia de comandos correcta para la impresora fiscal, incluyendo el manejo avanzado de **pagos mixtos** y el cálculo automático del **IGTF**.

-----

## Requisitos

  * Python 3.7 o superior.
  * Flask: `pip install Flask`.
  * La utilidad de comunicación proporcionada por The Factory HKA (`IntTfhka.exe` para Windows o `Tfinulx` para Linux).
  * Una impresora fiscal The Factory HKA compatible con IGTF.

-----

## Instalación y Configuración

1.  **Estructura de Carpetas**:

      * **Windows**: Crea una carpeta llamada `IntTFHKA` en la raíz de tu disco `C:\`. La ruta debe ser `C:\IntTFHKA`.
      * **Linux**: Crea una carpeta llamada `IntTFHKA` en el directorio de tu usuario. La ruta sería `/home/tu_usuario/IntTFHKA`.

2.  **Archivos de The Factory**: Coloca la utilidad (`IntTfhka.exe` o `Tfinulx`) y todos sus archivos asociados dentro de la carpeta que creaste.

3.  **Servidor Python**: Coloca el archivo del servidor (`servidor_fiscal.py`) dentro de esa misma carpeta.

      * **Importante**: Asegúrate de que las variables de ruta dentro del archivo `servidor_fiscal.py` (`INTTFHKA_PATH` y `COMANDOS_DIR`) coincidan con la ruta de tu sistema operativo.

4.  **Configurar Puerto COM**: Crea un archivo de texto llamado `Puerto.dat` en la misma carpeta. Dentro de este archivo, escribe únicamente el puerto al que está conectada tu impresora (ej. `COM3` en Windows, o `/dev/ttyS0` o `/dev/ttyUSB0` en Linux).

-----

## Configuración de la Impresora Fiscal (¡Importante\!)

Antes de usar el servidor, debes enviar dos comandos de configuración a tu impresora. Puedes hacerlo una sola vez desde la línea de comandos, ubicado en la carpeta de la utilidad.

### 1\. Activar Modo IGTF

Para que la impresora pueda procesar pagos en divisas y el comando de cierre `199`, debes activar el **Flag 50**.

**Comando en Windows:**

```bash
IntTFHKA SendCmd(PJ5001)
```

**Comando en Linux:**

```bash
./Tfinulx SendCmd(PJ5001)
```

### 2\. Personalizar Nombres de Métodos de Pago

Puedes cambiar los nombres por defecto de los "slots" de pago para que sean más descriptivos en los recibos. Se usa el comando `PE`.

**Ejemplos:**

```bash
# Cambiar Slot 01 a "PAGO MOVIL BS"
IntTFHKA SendCmd(PE01PAGO MOVIL BS)

# Cambiar Slot 20 a "EFECTIVO DIVISA"
IntTFHKA SendCmd(PE20EFECTIVO DIVISA)
```

-----

## Código del Servidor (`servidor_fiscal.py`)

El código fuente del servidor Python debe colocarse en esta carpeta. Su función principal es recibir las peticiones JSON y generar el archivo `factura_actual.txt` que se enviará a la impresora.

-----

## Cómo Usar el Servidor

1.  **Ejecutar el Servidor**: Abre una terminal en la carpeta de instalación (`C:\IntTFHKA` o `/home/tu_usuario/IntTFHKA`) y ejecuta el comando:

    ```bash
    python servidor_fiscal.py
    ```

    El servidor comenzará a escuchar en el puerto 5000, accesible desde tu red local.

2.  **Enviar Datos de Factura**: Desde tu sistema POS (Flutter, web, etc.), envía una petición `POST` al endpoint `/imprimir-factura-fiscal`. El cuerpo de la petición debe ser un JSON con la estructura que se muestra a continuación.

### Ejemplo de Payload JSON

Este es un ejemplo de un cuerpo JSON para una venta con dos productos y un pago mixto (parte en divisa y parte en bolívares).

**Nota Importante**: Todos los montos en el payload (`precio_unitario_con_iva` y `monto` de pago) deben estar expresados en **Bolívares (Bs.)**. Tu aplicación cliente es responsable de hacer la conversión de USD a Bs antes de enviar los datos.

```json
{
  "cliente": {
    "rif": "V12345678",
    "razon_social": "Cliente de Ejemplo"
  },
  "items": [
    {
      "descripcion": "PRODUCTO CON IVA 16%",
      "cantidad": 2.0,
      "precio_unitario_con_iva": 116.00,
      "tasa_iva": 16.0
    },
    {
      "descripcion": "PRODUCTO EXENTO",
      "cantidad": 1.0,
      "precio_unitario_con_iva": 50.00,
      "tasa_iva": 0.0
    }
  ],
  "pagos": [
    {
      "monto": 100.00,
      "slot_fiscal": 20
    },
    {
        "monto": 182.00,
        "slot_fiscal": 1
    }
  ]
}
```

-----

## Lógica Clave de la Impresión Fiscal

  * **Arquitectura de Archivo Único**: El servidor genera un archivo de texto (`factura_actual.txt`) con la secuencia completa de comandos (cliente, items, subtotal, pagos) y lo envía a la impresora con una sola instrucción (`SendFileCmd`), lo que garantiza transacciones atómicas.
  * **Manejo de IGTF**: El IGTF es calculado **automáticamente por la impresora**. El servidor solo necesita detectar si se usó un método de pago de divisa (slots 20-24) para añadir el comando de cierre obligatorio `199` al final de la secuencia.
  * **Manejo de Pagos Mixtos**: Para ventas con más de un método de pago, el servidor genera comandos de pago parcial (`2xx`) para los N-1 primeros pagos y un comando de pago totalizador (`1xx`) para el último, seguido del cierre `199` si aplica.
