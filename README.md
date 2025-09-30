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


# Manual de Flags para Impresoras Fiscales The Factory HKA

## 1. ¿Qué son los Flags?

Los "Flags" (o Banderas) son configuraciones internas que controlan el comportamiento de la impresora fiscal. Permiten activar, desactivar o modificar funcionalidades específicas, como el cálculo de impuestos (IGTF), el formato de los precios o la impresión de códigos de barras.

Cada Flag se identifica con un número de 2 dígitos y se le asigna un valor, también de 2 dígitos.

## 2. ¿Cómo se programa un Flag?

Para programar un Flag, se utiliza el comando `PJ` seguido del número del Flag y el valor que se le quiere asignar.

**Formato del Comando:**
`PJ<NumeroFlag><ValorFlag>`

* **`NumeroFlag`**: El identificador del Flag (2 dígitos).
* **`ValorFlag`**: El valor de configuración que se le asignará (2 dígitos).

**Ejemplo Práctico:**
Para activar el modo IGTF, se debe poner el **Flag 50** en el valor **01**. El comando a enviar sería:

```

PJ5001

````

Este comando se envía a la impresora a través de la utilidad `IntTfhka.exe` (o `Tfinulx` en Linux):
```bash
# En Windows
IntTFHKA SendCmd(PJ5001)

# En Linux
./Tfinulx SendCmd(PJ5001)
````

-----

## 3\. Guía de Flags Esenciales

A continuación se detallan los Flags más importantes para la integración de un sistema de punto de venta.

### Flag 50 - Impuesto a las Grandes Transacciones Financieras (IGTF)

Este es el Flag más importante para cumplir con la normativa fiscal venezolana sobre pagos en divisas.

  * **Descripción**: Habilita o deshabilita el cálculo e impresión del IGTF. 
  * **Valores**:
      * `00`: **Desactivado**. La impresora no calculará IGTF. Los medios de pago del 20 al 24 (reservados para divisas) estarán bloqueados. El cierre de factura se hace con los comandos `1xx` normales.
      * `01`: **Activado**. La impresora calculará automáticamente el IGTF cuando se usen los medios de pago del 20 al 24. **Es obligatorio cerrar TODOS los documentos fiscales (facturas, notas de crédito, etc.) con el comando `199`**, sin importar si la venta se pagó en bolívares o divisas.
  * **Comando para Activar**:
    ```
    PJ5001
    ```

### Flag 21 - Formato de Montos y Precios

Este Flag define cómo la impresora interpreta los números en los comandos de productos, específicamente la cantidad de dígitos enteros y decimales. Es crucial para evitar errores de formato en los precios.

  * **Descripción**: Cambia la precisión de los precios unitarios de los productos.
  * **Valores Comunes**:
      * `00`: **Estándar**. El precio se interpreta como 8 enteros y 2 decimales (Ej: `12345678.99`). Este es el valor por defecto y el más compatible.
      * `01`: El precio se interpreta como 7 enteros y 3 decimales.
      * `02`: El precio se interpreta como 6 enteros y 4 decimales.
  * **Comando para modo estándar**:
    ```
    PJ2100
    ```
  * **Observación**: Para la mayoría de las integraciones, se recomienda mantener este Flag en `00` para asegurar la compatibilidad.

### Flag 30 - Impresión de Códigos de Barras

Controla si el número legible por humanos se imprime junto al código de barras.

  * **Descripción**: Define la visualización del número asociado a un código de barras.
  * **Valores**:
      * `00`: Imprime el código de barras **sin** el número debajo.
      * `01`: Imprime el código de barras **con** el número asociado debajo. 
  * **Comando para imprimir con número**:
    ```
    PJ3001
    ```

### Flag 43 - Tipo de Código de Barras

Selecciona el formato del código de barras a imprimir.

  * **Descripción**: Define la simbología del código de barras.
  * **Valores Comunes**:
      * `00`: EAN-13
      * `02`: Code 128 
      * `03`: Code 39 
      * `04`: Código QR
  * **Comando para seleccionar QR**:
    ```
    PJ4304
    ```

### Flag 63 - Formato de Reportes y Status

Este es un Flag avanzado que modifica la longitud de los datos que la impresora devuelve al solicitar reportes (como el Reporte X) o estados (como el Status S2).

  * **Descripción**: Controla si las respuestas de la impresora usan un formato de datos "reducido" (legacy) o "ampliado" (moderno, con campos más largos para IGTF).
  * **Valores Clave (Modo IGTF)**:
      * `16` y `18`: Formato **reducido** con campos para IGTF.
      * `17` y `19`: Formato **ampliado** con campos para IGTF.
  * **Observación**: Para nuevas integraciones, se recomienda usar los valores de formato ampliado (`17` o `19`) ya que proporcionan campos más grandes y son más robustos a futuro. Sin embargo, esto requiere que el software que lee la respuesta de la impresora esté preparado para procesar una cadena de texto más larga.
  * **Comando para modo ampliado con IGTF**:
    ```
    PJ6317
    ```

-----

**Nota Final**: La cantidad y función de los Flags puede variar ligeramente entre modelos de impresora. Esta guía cubre los más comunes y esenciales basados en la documentación V8.5.0.
