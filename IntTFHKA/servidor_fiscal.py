# Archivo: servidor_impresion.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from escpos.printer import Usb
import usb.core
import usb.util
import subprocess
import os
import traceback
import re

# --- Configuración General ---
app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN PARA IMPRESORA NO FISCAL (USB DIRECTO) ---
VENDOR_ID = 0x1FC9
PRODUCT_ID = 0x2016
ANCHO_TICKET = 42

# --- CONFIGURACIÓN PARA IMPRESORA FISCAL (VÍA IntTfhka.exe) ---
INTTFHKA_PATH = "C:\\IntTFHKA\\IntTfhka.exe"
COMANDOS_DIR = "C:\\IntTFHKA"

# --- CONFIGURACIÓN DE IMPUESTOS ---
IGTF_SLOTS = [20, 21, 22, 23, 24] # Slots de pago considerados como Divisas

# --- Diccionarios de Códigos (Según el manual) ---
STATUS_CODES = {
    0: "Estado desconocido.", 1: "En modo prueba y en espera.", 2: "En modo prueba y emisión de documentos fiscales.", 3: "En modo prueba y emisión de documentos no fiscales.", 4: "En modo fiscal y en espera.", 5: "En modo fiscal y emisión de documentos fiscales.", 6: "En modo fiscal y emisión de documentos no fiscales.", 7: "En modo fiscal, cercana carga completa de la memoria fiscal y en espera.", 8: "En modo fiscal, cercana carga completa de la memoria fiscal y en emisión de documentos fiscales.", 9: "En modo fiscal, cercana carga completa de la memoria fiscal y en emisión de documentos no fiscales.", 10: "En modo fiscal, carga completa de la memoria fiscal y en espera.", 11: "En modo fiscal, carga completa de la memoria fiscal y en emisión de documentos fiscales.", 12: "En modo fiscal, carga completa de la memoria fiscal y en emisión de documentos no fiscales."
}
ERROR_CODES = {
    0: "No hay error.", 1: "Fin en la entrega de papel.", 2: "Error de índole mecánico en la entrega de papel.", 3: "Fin en la entrega de papel y error mecánico.", 80: "Comando invalido o valor invalido.", 84: "Tasa invalida.", 88: "No hay asignadas directivas.", 92: "Comando invalido.", 96: "Error fiscal.", 100: "Error de la memoria fiscal.", 108: "Memoria fiscal llena.", 112: "Buffer completo. (debe enviar el comando de reinicio)", 128: "Error en la comunicación.", 137: "No hay respuesta.", 144: "Error LRC.", 145: "Error interno api.", 153: "Error en la apertura del archivo."
}

# --------------------------------------------------------------------------
# --- ENDPOINTS PARA TICKERA USB NO FISCAL ---
# --------------------------------------------------------------------------

@app.route('/diagnostico')
def diagnostico_usb():
    """
    Endpoint para diagnosticar la conexión USB con la tickera no fiscal.
    """
    log = []
    log.append("--- INICIANDO DIAGNÓSTICO USB (TICKERA NO FISCAL) ---")
    dev = None
    try:
        log.append(f"Buscando dispositivo: VENDOR_ID=0x{VENDOR_ID:04x}, PRODUCT_ID=0x{PRODUCT_ID:04x}")
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if dev is None:
            log.append("[ERROR CRÍTICO]: ¡Tickera USB no encontrada!")
            return jsonify({"status": "error", "log": log}), 500
        
        log.append("¡Dispositivo encontrado!")
        
        try:
            # Desvincular el kernel driver si está activo (común en Linux)
            if dev.is_kernel_driver_active(0):
                log.append("Kernel driver activo. Intentando desvincular...")
                dev.detach_kernel_driver(0)
                log.append("Kernel driver desvinculado con éxito.")
        except usb.core.USBError as e:
            log.append(f"No se pudo desvincular el kernel driver (puede ser normal en Windows): {e}")

        dev.set_configuration()
        log.append("Configuración establecida con éxito.")
        
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]
        
        ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        
        if ep_out is None:
            log.append("[ERROR]: No se encontró Endpoint de SALIDA (OUT).")
            return jsonify({"status": "error", "log": log}), 500
        else:
            log.append(f"[ÉXITO]: Endpoint de SALIDA encontrado: {hex(ep_out.bEndpointAddress)}")
            log.append("DIAGNÓSTICO FINAL: Conexión USB con la tickera es correcta.")
            return jsonify({"status": "ok", "log": log}), 200
            
    except usb.core.USBError as e:
        log.append(f"[ERROR DE USB]: {e}")
        log.append("CONCLUSIÓN: Conflicto de drivers o permisos. Si estás en Windows, usar Zadig puede ser necesario para instalar el driver correcto (libusb).")
        return jsonify({"status": "error", "log": log}), 500
    except Exception as e:
        log.append(f"Error inesperado: {e}")
        return jsonify({"status": "error", "log": log}), 500
    finally:
        if dev is not None:
            usb.util.dispose_resources(dev)

@app.route('/imprimir-factura', methods=['POST'])
def imprimir_factura_no_fiscal():
    """Imprime una BOLETA / NOTA DE ENTREGA en la tickera normal USB."""
    p = None
    try:
        ticket_data = request.get_json()
        if not ticket_data: return jsonify({"error": "No se recibieron datos"}), 400
        p = Usb(VENDOR_ID, PRODUCT_ID, timeout=0, in_ep=0x81, out_ep=0x01)
        
        comercio_info = ticket_data.get('comercio', {})
        pedido_info = ticket_data.get('pedido', {})
        tipo_recibo = ticket_data.get('tipo_recibo', 'venta')
        moneda_principal_simbolo = 'Bs' if ticket_data.get('moneda_principal') == 'Bs' else '$'

        p.set(align='center', font='a', height=2, width=1)
        p.text(f"{comercio_info.get('nombre', 'Mi Negocio')}\n")
        p.set(align='center', font='a')
        p.text(f"RIF: {comercio_info.get('rif', 'J-00000000-0')}\n")
        p.set(align='center', font='b', height=2, width=2)
        p.text("NOTA DE ENTREGA\n" if tipo_recibo != 'pago_cuota' else "RECIBO DE PAGO\n")
        p.set(align='left', font='a', height=1, width=1)
        p.text("-" * ANCHO_TICKET + "\n")
        p.text(f"Fecha: {pedido_info.get('fecha')}\n")
        atendido_por = pedido_info.get('cajero') or pedido_info.get('mesero')
        if atendido_por: p.text(f"Atendido por: {atendido_por}\n")
        if pedido_info.get('cliente_nombre'): p.text(f"Cliente: {pedido_info.get('cliente_nombre')}\n")
        if pedido_info.get('cliente_cedula'): p.text(f"CI/RIF: {pedido_info.get('cliente_cedula')}\n")
        p.text("-" * ANCHO_TICKET + "\n")
        p.text(format_line("Cant. Descripcion", "Total", ANCHO_TICKET) + "\n")
        p.text("-" * ANCHO_TICKET + "\n")
        for item in ticket_data.get('items', []):
            desc = item['descripcion']
            desc_linea = f"{item['cantidad']} {desc}"
            total_formateado = f"{item.get('total_item', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            total_linea = f"{moneda_principal_simbolo} {total_formateado}"
            p.text(format_line(desc_linea, total_linea, ANCHO_TICKET) + "\n")
        p.text("-" * ANCHO_TICKET + "\n")
        totales = ticket_data.get('totales', {})
        p.set(align='right', font='b')
        subtotal_formateado = f"{totales.get('subtotal', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        p.text(format_line("SUBTOTAL:", f"{moneda_principal_simbolo} {subtotal_formateado}", ANCHO_TICKET) + "\n")
        total_principal = totales.get('total_a_pagar', 0)
        total_principal_formateado = f"{total_principal:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        p.set(font='b', height=2, width=2)
        p.text(format_line(f"TOTAL {moneda_principal_simbolo}:", total_principal_formateado, ANCHO_TICKET) + "\n")
        p.set(font='a', height=1, width=1)
        p.text("\n")
        p.set(align='center', font='a')
        p.text("Gracias por su preferencia!\n\n")
        p.cut()
        return jsonify({"message": f"Recibo ({tipo_recibo}) impreso correctamente"}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error en impresora de boletas: {str(e)}"}), 500
    finally:
        if p: p.close()


# ----------------------------------------------------------------
# --- ENDPOINTS PARA IMPRESORA FISCAL (ACTUALIZADOS) ---
# ----------------------------------------------------------------

@app.route('/test-fiscal', methods=['GET'])
def test_impresora_fiscal():
    try:
        respuesta = ejecutar_comando_fiscal('SendCmd(D)')
        return jsonify({"message": "Prueba fiscal exitosa.", "respuesta_impresora": respuesta}), 200
    except Exception as e:
        return jsonify({"error": f"Error en la prueba fiscal: {str(e)}"}), 500

@app.route('/estado-impresora-fiscal', methods=['GET'])
def estado_impresora_fiscal():
    try:
        # El comando S1 ahora imprime el estado y error en stdout
        respuesta_texto = ejecutar_comando_fiscal('SendCmd(S1)')
        
        # Parseamos la respuesta para extraer los códigos
        partes = respuesta_texto.replace(":", " ").split()
        status_code = int(partes[partes.index("Status") + 1])
        error_code = int(partes[partes.index("Error") + 1])

        respuesta = {
            "status_code": status_code,
            "status_descripcion": STATUS_CODES.get(status_code, "Código no documentado."),
            "error_code": error_code,
            "error_descripcion": ERROR_CODES.get(error_code, "Código no documentado.")
        }
        return jsonify(respuesta), 200

    except Exception as e:
        return jsonify({"error": f"Error obteniendo estado fiscal: {str(e)}"}), 500

def ejecutar_comando_fiscal(comando_str, lineas_esperadas=None):
    print(f"Ejecutando: {comando_str}")
    comando_completo = f'"{INTTFHKA_PATH}" {comando_str}'
    try:
        resultado_proceso = subprocess.run(
            comando_completo, shell=True, capture_output=True, text=True,
            cwd=COMANDOS_DIR, encoding="cp1252", timeout=25
        )
        salida_texto = resultado_proceso.stdout.strip()
        print(f" > Respuesta de IntTfhka: '{salida_texto}'")

        es_exitoso = False
        if "SENDFILECMD" in comando_str.upper() and lineas_esperadas is not None:
            match = re.search(r"Retorno:\s*(\d+)", salida_texto)
            if match:
                lineas_procesadas = int(match.group(1))
                if lineas_procesadas == lineas_esperadas:
                    print(f" > SendFileCmd exitoso. Se procesaron todas las {lineas_procesadas} líneas.")
                    es_exitoso = True
                else:
                    print(f" > SendFileCmd falló. Se esperaban {lineas_esperadas} líneas pero solo se procesaron {lineas_procesadas}.")
        else:
            if "TRUE" in salida_texto.upper():
                es_exitoso = True
        
        if es_exitoso:
            return salida_texto
        else:
            raise Exception(f"Comando falló. Respuesta de la impresora: '{salida_texto}'")
    except Exception as e:
        raise e

# ----------------------------------------------------------------
# --- ENDPOINT DE FACTURA FISCAL (RECONSTRUIDO) ---
# ----------------------------------------------------------------

@app.route('/imprimir-factura-fiscal', methods=['POST'])
def imprimir_factura_fiscal():
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "No se recibieron datos"}), 400

        print("\n--- INICIANDO PROCESO DE FACTURA FISCAL (LÓGICA IGTF OFICIAL CORREGIDA) ---")
        comandos_para_archivo = []
        pagos = data.get('pagos', [])
        se_uso_pago_igtf = any(int(p.get('slot_fiscal', 0)) in IGTF_SLOTS for p in pagos)

        # --- A. Comandos de Cliente e Items (sin cambios) ---
        cliente = data.get('cliente', {}); 
        comandos_para_archivo.append(f'iS*{cliente.get("razon_social", "Consumidor Final")}')
        comandos_para_archivo.append(f'iR*{cliente.get("rif", "V000000000")}')
        for item in data.get('items', []):
            descripcion = item.get('descripcion', 'Producto')[:40]
            cantidad = float(item.get('cantidad', 0))
            precio_con_iva = float(item.get('precio_unitario_con_iva', 0))
            tasa_iva = float(item.get('tasa_iva', 0))
            if precio_con_iva <= 0.0:
                precio_con_iva = 0.01; tasa_iva = 0.0
            precio_base = precio_con_iva / (1 + (tasa_iva / 100)) if tasa_iva > 0 else precio_con_iva
            cmd_tasa_map = {16.0: '!', 8.0: '"', 31.0: '#', 0.0: ' '}
            cmd_tasa = cmd_tasa_map.get(tasa_iva, ' ')
            precio_fmt = f"{precio_base:.2f}".replace('.', '').zfill(10)
            cantidad_fmt = f"{cantidad:.3f}".replace('.', '').zfill(8)
            comandos_para_archivo.append(f'{cmd_tasa}{precio_fmt}{cantidad_fmt}{descripcion}')
        
        # --- B. Comando de Subtotal ---
        comandos_para_archivo.append('3')
        print(" > Comando de subtotal '3' añadido.")

        # --- C. LÓGICA DE PAGOS CORREGIDA (SEGÚN MANUAL OFICIAL) ---
        if not pagos:
            comandos_para_archivo.append('101')
        elif len(pagos) == 1:
            pago = pagos[0]; slot = int(pago.get('slot_fiscal', 1))
            comandos_para_archivo.append(f"1{slot:02d}")
            print(f" > Un solo pago detectado. Comando totalizador: '1{slot:02d}'.")
        else: # Múltiples pagos (pago mixto)
            print(" > Múltiples pagos detectados. Secuencia: N-1 parciales + 1 final.")
            for i, pago in enumerate(pagos):
                slot = int(pago.get('slot_fiscal', 1))
                if i < len(pagos) - 1: # Si NO es el último pago, es PARCIAL
                    monto = float(pago.get('monto', 0))
                    monto_fmt = f"{monto:.2f}".replace('.', '').zfill(12)
                    comando_parcial = f"2{slot:02d}{monto_fmt}"
                    comandos_para_archivo.append(comando_parcial)
                    print(f"   > Añadido pago PARCIAL: '{comando_parcial}'")
                else: # Si ES el último pago, es TOTALIZADOR
                    comando_final = f"1{slot:02d}"
                    comandos_para_archivo.append(comando_final)
                    print(f"   > Añadido pago FINAL: '{comando_final}'")

        # --- D. COMANDO DE CIERRE OBLIGATORIO PARA IGTF ---
        if se_uso_pago_igtf:
            comandos_para_archivo.append('199')
            print(" > Se detectó pago en divisa. Añadiendo comando de cierre obligatorio '199'.")

        # --- E. Escribir y Enviar el Archivo ---
        nombre_archivo_final = "factura_actual.txt"
        with open(os.path.join(COMANDOS_DIR, nombre_archivo_final), "w", encoding="cp1252") as f:
            f.write("\n".join(comandos_para_archivo))
        
        print(f"\n--- Contenido Final de '{nombre_archivo_final}' ---")
        for cmd in comandos_para_archivo: print(cmd)
        print("-------------------------------------------\n")

        numero_de_lineas = len(comandos_para_archivo)
        respuesta_final = ejecutar_comando_fiscal(f'SendFileCmd("{nombre_archivo_final}")', lineas_esperadas=numero_de_lineas)

        print("--- PROCESO DE FACTURA FISCAL COMPLETADO CON ÉXITO ---")
        return jsonify({ "message": "Factura fiscal procesada correctamente.", "respuesta_impresora": respuesta_final }), 200
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error crítico durante el envío fiscal: {str(e)}"}), 500

    
@app.route('/imprimir-reporte-fiscal', methods=['POST'])
def imprimir_reporte_fiscal():
    try:
        data = request.get_json()
        tipo_reporte = data.get('tipo', '').upper()
        comando = 'SendCmd(I0X)' if tipo_reporte == 'X' else 'SendCmd(I0Z)'
        if tipo_reporte not in ['X', 'Z']:
            return jsonify({"error": "Tipo de reporte no válido. Use 'X' o 'Z'."}), 400
        respuesta = ejecutar_comando_fiscal(comando)
        return jsonify({"message": f"Reporte '{tipo_reporte}' enviado.", "respuesta": respuesta}), 200
    except Exception as e:
        return jsonify({"error": f"Error imprimiendo reporte: {str(e)}"}), 500

if __name__ == '__main__':
    print("Iniciando servidor de impresión en http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
