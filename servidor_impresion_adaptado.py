# -*- coding: latin-1 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
from escpos.printer import Usb
import usb.core
import usb.util
import subprocess
import os
import traceback
import re
from datetime import datetime
import uuid
from threading import Lock
import time
import platform # <-- Importado para detectar el sistema operativo

# --- Configuración General ---
app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN DE PLATAFORMA (SE AJUSTA AUTOMÁTICAMENTE) ---
SISTEMA_OPERATIVO = platform.system()

if SISTEMA_OPERATIVO == "Windows":
    print("-> Detectado sistema operativo Windows.")
    # IMPORTANTE: Cambia "Tfhka.exe" si tu ejecutable tiene otro nombre (ej. tfin.exe)
    EXECUTABLE_FISCAL = "IntTFHKA" 
    # IMPORTANTE: Cambia esta ruta a la carpeta base donde están las subcarpetas de las impresoras.
    BASE_FISCAL_PATH = "C:\\ServidorFiscal" 
else:
    print("-> Detectado sistema operativo Linux.")
    EXECUTABLE_FISCAL = "tfinulx"
    USER = "zante" # Mantenemos tu configuración original para Linux
    BASE_FISCAL_PATH = f"/home/{USER}"

print(f"Ruta base para impresoras fiscales: {BASE_FISCAL_PATH}")
print(f"Ejecutable fiscal a utilizar: {EXECUTABLE_FISCAL}")


# --- CONFIGURACIÓN PARA IMPRESORA NO FISCAL (USB DIRECTO) ---
# NOTA PARA WINDOWS: Si la impresora no fiscal no es detectada,
# podrías necesitar usar una herramienta como "Zadig" para reemplazar 
# el driver genérico por "libusb-win32" o "libusbK".
VENDOR_ID = 0x0483
PRODUCT_ID = 0x5743
ANCHO_TICKET = 42

# --- CONFIGURACIÓN DE IMPUESTOS (IGTF) ---
IGTF_SLOTS = [20, 21, 22, 23, 24] 
IGTF_MODE_ACTIVE = True

# --- MECANISMO DE BLOQUEO PARA IMPRESORAS FISCALES ---
printer_locks = {}
locks_dict_lock = Lock()

# --- Diccionarios de Códigos (Según el manual TFHKA) ---
STATUS_CODES = { 4: "En modo fiscal y en espera.", 5: "En modo fiscal y emisión de documentos fiscales.", 6: "En modo fiscal y emisión de documentos no fiscales." }
ERROR_CODES = { 0: "No hay error.", 1: "Fin en la entrega de papel.", 2: "Error de índole mecánico en la entrega de papel.", 100: "Error de la memoria fiscal.", 108: "Memoria fiscal llena.", 128: "Error en la comunicación.", 137: "No hay respuesta." }

# --------------------------------------------------------------------------
# --- LÓGICA PARA IMPRESORA NO FISCAL (TICKETS Y COMANDAS) ---
# --------------------------------------------------------------------------
# (Esta sección no requiere cambios, es compatible con ambos sistemas operativos)

@app.route('/diagnostico')
def diagnostico_usb():
    log = []
    log.append("--- INICIANDO DIAGNÓSTICO USB (TICKERA NO FISCAL) ---")
    dev = None
    try:
        log.append(f"Buscando dispositivo: VENDOR_ID=0x{VENDOR_ID:04x}, PRODUCT_ID=0x{PRODUCT_ID:04x}")
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if dev is None:
            log.append("[ERROR CRÍTICO]: ¡Tickera USB no encontrada!")
            log.append("-> CONSEJO WINDOWS: Asegúrese de haber instalado el driver correcto (ej. con Zadig).")
            return jsonify({"status": "error", "log": log}), 500

        log.append("¡Dispositivo encontrado!")

        try:
            if dev.is_kernel_driver_active(0):
                log.append("Kernel driver activo. Intentando desvincular...")
                dev.detach_kernel_driver(0)
                log.append("Kernel driver desvinculado con éxito.")
        except usb.core.USBError as e:
            log.append(f"No se pudo desvincular el kernel driver (esto es normal en Windows): {e}")

        dev.set_configuration()
        log.append("Configuración establecida con éxito.")

        return jsonify({"status": "ok", "log": log}), 200

    except Exception as e:
        log.append(f"Error inesperado: {e}")
        return jsonify({"status": "error", "log": log}), 500
    finally:
        if dev is not None:
            usb.util.dispose_resources(dev)

@app.route('/imprimir-factura', methods=['POST'])
def imprimir_factura_no_fiscal():
    p = None
    try:
        ticket_data = request.get_json()
        if not ticket_data: return jsonify({"error": "No se recibieron datos"}), 400
        p = Usb(VENDOR_ID, PRODUCT_ID, timeout=0, in_ep=0x81, out_ep=0x01)

        comercio_info = ticket_data.get('comercio', {})
        pedido_info = ticket_data.get('pedido', {})
        tipo_recibo = ticket_data.get('tipo_recibo', 'venta')
        moneda_principal_simbolo = 'Bs' if ticket_data.get('moneda_principal') == 'Bs' else '$'

        p.set(align='center', font='a', height=2, width=1); p.text(f"{comercio_info.get('nombre', 'Mi Negocio')}\n")
        p.set(align='center', font='a'); p.text(f"RIF: {comercio_info.get('rif', 'J-00000000-0')}\n")
        p.set(align='center', font='b', height=2, width=2); p.text("NOTA DE ENTREGA\n" if tipo_recibo != 'pago_cuota' else "RECIBO DE PAGO\n")
        p.set(align='left', font='a', height=1, width=1); p.text("-" * ANCHO_TICKET + "\n")
        p.text(f"Fecha: {pedido_info.get('fecha')}\n")
        atendido_por = pedido_info.get('cajero') or pedido_info.get('mesero')
        if atendido_por: p.text(f"Atendido por: {atendido_por}\n")
        if pedido_info.get('cliente_nombre'): p.text(f"Cliente: {pedido_info.get('cliente_nombre')}\n")
        if pedido_info.get('cliente_cedula'): p.text(f"CI/RIF: {pedido_info.get('cliente_cedula')}\n")
        p.text("-" * ANCHO_TICKET + "\n"); p.text(format_line("Cant. Descripcion", "Total", ANCHO_TICKET) + "\n"); p.text("-" * ANCHO_TICKET + "\n")
        for item in ticket_data.get('items', []):
            desc_linea = f"{item['cantidad']} {item['descripcion']}"
            total_formateado = f"{item.get('total_item', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            total_linea = f"{moneda_principal_simbolo} {total_formateado}"
            p.text(format_line(desc_linea, total_linea, ANCHO_TICKET) + "\n")
        p.text("-" * ANCHO_TICKET + "\n")
        totales = ticket_data.get('totales', {})
        p.set(align='right', font='b')
        subtotal_formateado = f"{totales.get('subtotal', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        p.text(format_line("SUBTOTAL:", f"{moneda_principal_simbolo} {subtotal_formateado}", ANCHO_TICKET) + "\n")
        total_principal_formateado = f"{totales.get('total_a_pagar', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        p.set(font='b', height=2, width=2); p.text(format_line(f"TOTAL {moneda_principal_simbolo}:", total_principal_formateado, ANCHO_TICKET) + "\n")
        p.set(font='a', height=1, width=1); p.text("\n"); p.set(align='center', font='a'); p.text("Gracias por su preferencia!\n\n"); p.cut()
        return jsonify({"message": f"Recibo ({tipo_recibo}) impreso"}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error en impresora de boletas: {str(e)}"}), 500
    finally:
        if p: p.close()

def format_line(left_text, right_text, width):
    left_text = str(left_text); right_text = str(right_text)
    spacing = width - len(left_text) - len(right_text)
    return f"{left_text}{' ' * max(0, spacing)}{right_text}"

@app.route('/imprimir-comanda', methods=['POST'])
def imprimir_comanda():
    p = None
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "No se recibieron datos para la comanda"}), 400

        p = Usb(VENDOR_ID, PRODUCT_ID, timeout=0, in_ep=0x81, out_ep=0x01)

        pedido_info = data.get('pedido', {})
        items = data.get('items', [])

        p.set(align='center', font='a', bold=True, height=2, width=2)
        p.text(f"PEDIDO #{pedido_info.get('id', 'N/A')}\n")
        p.set(align='left', font='a', bold=True, height=2, width=1)
        mesa = pedido_info.get('mesa')
        if mesa and mesa != 'Por asignar':
             p.text(f"MESA: {str(mesa).upper()}\n")
        else:
             p.text(f"PARA: {str(pedido_info.get('tipo_servicio', 'Llevar')).upper()}\n")
        p.set(align='left', font='a', height=1, width=1)
        mesero = pedido_info.get('mesero', 'N/A')
        p.text(f"MESERO: {str(mesero).upper()}\n")
        cliente_nombre = pedido_info.get('cliente_nombre')
        if cliente_nombre and str(cliente_nombre).strip():
            p.text(f"CLIENTE: {str(cliente_nombre).upper()}\n")
        p.text("-" * ANCHO_TICKET + "\n")

        for item in items:
            p.set(align='left', font='a', bold=True, height=2, width=1)
            p.text(f"{item.get('cantidad', 1)}x {str(item.get('descripcion', 'PRODUCTO')).upper()}\n")
            p.set(align='left', font='b', bold=False, height=1, width=1)
            opciones = item.get('opciones_seleccionadas', [])
            if opciones:
                for opcion in opciones:
                    cantidad_op = opcion.get('cantidad', 1)
                    nombre_op = str(opcion.get('nombre', '?')).upper()
                    texto_op = f"{cantidad_op}x {nombre_op}" if cantidad_op > 1 else f"› {nombre_op}"
                    p.text(f"  {texto_op}\n")
            adicionales = item.get('adicionales', [])
            if adicionales:
                for adicional in adicionales:
                    cantidad_ad = adicional.get('cantidad', 1)
                    nombre_ad = str(adicional.get('nombre', '?')).upper()
                    texto_ad = f"+{cantidad_ad}x {nombre_ad}" if cantidad_ad > 1 else f"+ {nombre_ad}"
                    p.text(f"  {texto_ad}\n")
            removidos = item.get('removidos', [])
            if removidos:
                nombres_removidos = [str(r.get('nombre', '?')).upper() for r in removidos]
                texto_rem = "- " + ", ".join(nombres_removidos)
                if len(texto_rem) > ANCHO_TICKET - 2:
                    p.text(f"  - SIN: {', '.join(nombres_removidos)}\n")
                else:
                    p.text(f"  {texto_rem}\n")
            observacion = item.get('observacion')
            if observacion and str(observacion).strip():
                p.text(f"  >> {str(observacion).strip().upper()}\n")

        p.set(align='left', font='a', height=1, width=1)
        p.text("-" * ANCHO_TICKET + "\n")
        p.set(align='center', font='b')
        p.text(datetime.now().strftime("%d/%m/%Y %I:%M %p") + "\n\n\n")
        p.cut()
        return jsonify({"message": "Comanda impresa completa en mayúsculas"}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error en impresora de comandas: {str(e)}"}), 500
    finally:
        if p: p.close()


# ----------------------------------------------------------------
# --- LÓGICA PARA IMPRESORA FISCAL (MULTI-PLATAFORMA) ---
# ----------------------------------------------------------------

def ejecutar_comando_fiscal(comando_base, argumento, fiscal_dir, lineas_esperadas=None, retry_delay=0.3):
    # La ruta al ejecutable usa la variable de configuración global
    tfin_path = os.path.join(fiscal_dir, EXECUTABLE_FISCAL)
    
    # --- CAMBIO CLAVE PARA COMPATIBILIDAD CON WINDOWS ---
    if SISTEMA_OPERATIVO == "Windows":
        # Para Windows, el formato es SendCmd(D) o SendFileCmd(ruta_archivo)
        comando_para_ejecutable = f"{comando_base}({argumento})"
        comando_completo = [tfin_path, comando_para_ejecutable]
    else:
        # Para Linux, el formato es [ejecutable, comando, argumento]
        comando_completo = [tfin_path, comando_base, argumento]
    # --- FIN DEL CAMBIO ---

    print(f"Ejecutando en [{fiscal_dir}]: {' '.join(comando_completo)}")
    
    intentos_maximos = 3 
    last_exception = None

    for intento in range(1, intentos_maximos + 1):
        try:
            resultado_proceso = subprocess.run(
                comando_completo, capture_output=True, text=True, cwd=fiscal_dir,
                encoding="latin-1", timeout=45
            )
            salida_stdout = resultado_proceso.stdout.strip()
            salida_stderr = resultado_proceso.stderr.strip()
            print(f" > Intento {intento} - Salida STDOUT: '{salida_stdout}'")
            if salida_stderr: print(f" > Intento {intento} - Salida STDERR: '{salida_stderr}'")

            # --- NUEVA LÓGICA DE VALIDACIÓN (MULTI-PLATAFORMA) ---
            # Se agrega "exitasomente" a la lista de palabras de éxito
            if resultado_proceso.returncode == 0 or "exitosa" in salida_stdout or "correctamente" in salida_stdout or "exitasomente" in salida_stdout:
                
                if comando_base == "SendFileCmd":
                    
                    # --- Intento 1: Buscar formato Linux (Enviados X comandos) ---
                    match_enviados = re.search(r"Enviados (\d+) comandos", salida_stdout)
                    if match_enviados:
                         print(f" > Detectado formato de respuesta Linux (Enviados {match_enviados.group(1)} comandos).")

                    # --- Intento 2: Buscar formato Windows (Retorno: X, Error: 0) ---
                    if not match_enviados:
                        match_win_retorno = re.search(r"Retorno:\s*(\d+)", salida_stdout)
                        match_win_error = re.search(r"Error:\s*(\d+)", salida_stdout)
                        
                        # Si es formato Windows, verificar que sea exitoso
                        if match_win_retorno and match_win_error and "exitasomente" in salida_stdout:
                            if int(match_win_error.group(1)) == 0:
                                # ¡Éxito! Asignamos el valor de Retorno al "match"
                                match_enviados = match_win_retorno 
                                print(f" > Detectado formato de respuesta Windows (Retorno: {match_enviados.group(1)}, Error: 0).")
                            else:
                                # Es formato Windows, PERO CON ERROR
                                error_code = int(match_win_error.group(1))
                                last_exception = Exception(f"Fallo en SendFileCmd para {fiscal_dir}. El ejecutable reportó Error: {error_code}. Respuesta: {salida_stdout}")
                                raise last_exception
                        # else: (Si no es ni formato Linux ni Windows, se manejará más abajo)
                    
                    # --- LÓGICA UNIFICADA (usa 'match_enviados' de Linux o Windows) ---
                    if match_enviados:
                        comandos_enviados = int(match_enviados.group(1))
                        
                        if comandos_enviados == 0 and lineas_esperadas is not None and lineas_esperadas > 0:
                            last_exception = Exception(f"Fallo en SendFileCmd tras intento {intento}. Respuesta: {salida_stdout}")
                            if intento < intentos_maximos:
                                print(f"ADVERTENCIA: El ejecutable reportó 0 comandos enviados en intento {intento}. Reintentando...")
                                time.sleep(retry_delay) 
                                continue
                            else:
                                raise last_exception 
                        
                        elif lineas_esperadas is not None and comandos_enviados >= lineas_esperadas:
                            return {"exito": True, "mensaje": salida_stdout} 
                        
                        elif lineas_esperadas is None or lineas_esperadas == 0:
                             return {"exito": True, "mensaje": salida_stdout}
                        
                        else:
                            last_exception = Exception(f"Fallo en SendFileCmd para {fiscal_dir}. Se esperaban {lineas_esperadas}, se enviaron {comandos_enviados}. Respuesta: {salida_stdout}")
                            raise last_exception
                    
                    else: 
                        # --- FALLBACK SI NINGÚN FORMATO COINCIDIÓ ---
                        # (Esto es lo que causaba el error original)
                        if not ("exitosa" in salida_stdout or "correctamente" in salida_stdout or "exitasomente" in salida_stdout):
                            last_exception = Exception(f"Respuesta inesperada de ejecutable para SendFileCmd (formato no reconocido): {salida_stdout}")
                            raise last_exception
                        else: # Éxito genérico (sin conteo de comandos)
                            return {"exito": True, "mensaje": salida_stdout}
                
                else: # Para SendCmd, ReadFpStatus... Éxito
                    return {"exito": True, "mensaje": salida_stdout}
            
            else: # Error explícito (return code != 0 y sin palabras de éxito)
                last_exception = Exception(f"El ejecutable falló en {fiscal_dir}. STDOUT: '{salida_stdout}' | STDERR: '{salida_stderr}'")
                raise last_exception

        # --- Manejo de excepciones dentro del bucle (sin cambios) ---
        except subprocess.TimeoutExpired as e:
            raise Exception(f"Timeout: La impresora en {fiscal_dir} no respondió.") from e
        except FileNotFoundError as e:
            raise Exception(f"EJECUTABLE NO ENCONTRADO en {tfin_path}. Verifica la configuración.") from e
        except Exception as e:
            last_exception = e
            if intento < intentos_maximos:
                print(f"Error en intento {intento}: {e}. Reintentando...")
                time.sleep(retry_delay)
            else:
                print(f"Error final tras {intentos_maximos} intentos.")
                raise last_exception from e
            
    raise Exception(f"Se alcanzó el final de la función ejecutar_comando_fiscal inesperadamente para {fiscal_dir}.")

def get_and_validate_fiscal_dir(terminal_uuid):
    if not terminal_uuid: raise ValueError("El 'terminalUUID' es obligatorio.")
    # Usamos abspath para normalizar la ruta (ej. C:\zante en Windows)
    fiscal_dir = os.path.abspath(os.path.join(BASE_FISCAL_PATH, terminal_uuid))
    # Validamos que la ruta generada siga estando dentro de la ruta base permitida
    if not fiscal_dir.startswith(os.path.abspath(BASE_FISCAL_PATH)): 
        raise ValueError("Intento de acceso a ruta no válida.")
    if not os.path.isdir(fiscal_dir): 
        raise FileNotFoundError(f"El directorio para el UUID '{terminal_uuid}' no existe en '{fiscal_dir}'.")
    return fiscal_dir

@app.route('/imprimir-factura-fiscal', methods=['POST'])
def imprimir_factura_fiscal():
    data = request.get_json()
    if not data: return jsonify({"error": "No se recibieron datos"}), 400

    fiscal_dir = None
    ruta_archivo_completa = None
    impresora_lock = None
    
    try:
        terminal_uuid = data.get("terminalUUID")
        fiscal_dir = get_and_validate_fiscal_dir(terminal_uuid)

        with locks_dict_lock:
            if terminal_uuid not in printer_locks:
                printer_locks[terminal_uuid] = Lock()
        impresora_lock = printer_locks[terminal_uuid]
        
        with impresora_lock:
            print(f"\n--- [LOCK ADQUIRIDO] INICIANDO FACTURA PARA UUID [{terminal_uuid}] ---")

            nombre_archivo_comandos = "factura_actual.txt"
            ruta_archivo_completa = os.path.join(fiscal_dir, nombre_archivo_comandos)

            comandos = []
            # La lógica de generación de comandos no cambia
            cliente = data.get('cliente', {}); comandos.append(f'iS*{cliente.get("razon_social", "Consumidor Final")}'); comandos.append(f'iR*{cliente.get("rif", "V000000000")}')
            for item in data.get('items', []):
                descripcion = item.get('descripcion', 'Producto')[:40]; cantidad = float(item.get('cantidad', 0)); precio_con_iva = float(item.get('precio_unitario_con_iva', 0)); tasa_iva = float(item.get('tasa_iva', 0))
                if precio_con_iva <= 0.0: precio_con_iva = 0.01; tasa_iva = 0.0
                precio_base = precio_con_iva / (1 + (tasa_iva / 100)) if tasa_iva > 0 else precio_con_iva
                cmd_tasa_map = {16.0: '!', 8.0: '"', 31.0: '#', 0.0: ' '}; cmd_tasa = cmd_tasa_map.get(tasa_iva, ' ')
                precio_fmt = f"{precio_base:.2f}".replace('.', '').zfill(10); cantidad_fmt = f"{cantidad:.3f}".replace('.', '').zfill(8); comandos.append(f'{cmd_tasa}{precio_fmt}{cantidad_fmt}{descripcion}')
            comandos.append('3')
            pagos = data.get('pagos', []);
            if not pagos: comandos.append('101')
            elif len(pagos) == 1: comandos.append(f"1{int(pagos[0].get('slot_fiscal', 1)):02d}")
            else:
                for i, pago in enumerate(pagos):
                    slot = int(pago.get('slot_fiscal', 1)); monto = float(pago.get('monto', 0)); monto_fmt = f"{monto:.2f}".replace('.', '').zfill(12)
                    if i < len(pagos) - 1: comandos.append(f"2{slot:02d}{monto_fmt}")
                    else: comandos.append(f"1{slot:02d}")
            if IGTF_MODE_ACTIVE:
                comandos.append('199')
                print(" > Modo IGTF activo. Añadiendo comando de cierre '199'.")

            comandos_str = "\n".join(comandos)
            
            try:
                with open(ruta_archivo_completa, "w", encoding="latin-1") as f:
                    f.write(comandos_str)
                    f.flush()
                    os.fsync(f.fileno())
                
                # CAMBIO: La llamada a 'sync' es específica de Linux y se omite.
                # os.fsync() es la llamada correcta para forzar la escritura de un
                # archivo específico al disco en sistemas compatibles (incluyendo Windows).
                if SISTEMA_OPERATIVO != "Windows":
                    print(f"Archivo '{nombre_archivo_comandos}' escrito. Forzando sync de I/O del sistema (solo Linux)...")
                    subprocess.run(["sync"], check=True)
                    print("Sync de I/O completado.")
                else:
                    print(f"Archivo '{nombre_archivo_comandos}' escrito y sincronizado para Windows.")

                # Bucle de Validación (se mantiene como doble chequeo)
                max_espera_seg = 3.0
                tiempo_inicio = time.time()
                contenido_en_disco = ""
                
                while time.time() - tiempo_inicio < max_espera_seg:
                    try:
                        # CAMBIO: os.O_SYNC no está disponible en Windows. 
                        # Confiamos en el f.flush() y os.fsync() hechos previamente.
                        # El flag os.O_RDONLY es universal.
                        fd = os.open(ruta_archivo_completa, os.O_RDONLY)
                        try:
                            size = os.fstat(fd).st_size
                            contenido_en_disco_bytes = os.read(fd, size)
                            contenido_en_disco = contenido_en_disco_bytes.decode("latin-1")
                        finally:
                            os.close(fd)

                    except Exception as read_err:
                        print(f"Advertencia: Error temporal leyendo archivo para validación: {read_err}")
                        time.sleep(0.05) 
                        continue
                    
                    if contenido_en_disco == comandos_str:
                        print(f"Validación exitosa en {time.time() - tiempo_inicio:.4f}s. El contenido en disco coincide.")
                        break
                    
                    print(f"Validación en progreso... (Actual: {len(contenido_en_disco)} bytes, Esperado: {len(comandos_str)} bytes)")
                    time.sleep(0.05)
                
                if contenido_en_disco != comandos_str:
                    print(f"Error Crítico: Timeout de {max_espera_seg}s. El archivo en disco NUNCA coincidió.")
                    print(f"--- CONTENIDO ESPERADO ({len(comandos_str)} bytes) --- \n{comandos_str}")
                    print(f"--- CONTENIDO EN DISCO ({len(contenido_en_disco)} bytes) --- \n{contenido_en_disco}")
                    raise Exception(f"Fallo de validación de I/O: El archivo en disco no se actualizó a tiempo.")

            except Exception as write_err:
                print(f"ERROR escribiendo, sincronizando o validando el archivo: {write_err}")
                raise write_err

            respuesta = ejecutar_comando_fiscal("SendFileCmd", ruta_archivo_completa, fiscal_dir, lineas_esperadas=len(comandos))

            print(f"--- [LOCK LIBERADO] FACTURA PROCESADA PARA UUID [{terminal_uuid}] ---")
            return jsonify({"message": f"Factura para UUID [{terminal_uuid}] enviada.", "respuesta_impresora": respuesta.get('mensaje')}), 200

    except (ValueError, FileNotFoundError) as e:
        if impresora_lock and impresora_lock.locked(): impresora_lock.release()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        if impresora_lock and impresora_lock.locked(): impresora_lock.release()
        traceback.print_exc()
        return jsonify({"error": f"Error crítico procesando para UUID [{data.get('terminalUUID')}]: {str(e)}"}), 500

@app.route('/imprimir-reporte-fiscal', methods=['POST'])
def imprimir_reporte_fiscal():
    data = request.get_json()
    if not data: return jsonify({"error": "No se recibieron datos"}), 400
    try:
        terminal_uuid = data.get("terminalUUID"); tipo_reporte = data.get('tipo', '').upper()
        fiscal_dir = get_and_validate_fiscal_dir(terminal_uuid)
        if tipo_reporte not in ['X', 'Z']: return jsonify({"error": "Tipo de reporte no válido. Use 'X' o 'Z'."}), 400
        with locks_dict_lock:
            if terminal_uuid not in printer_locks: printer_locks[terminal_uuid] = Lock()
        impresora_lock = printer_locks[terminal_uuid]
        with impresora_lock:
            print(f"\n--- [LOCK ADQUIRIDO] REPORTE [{tipo_reporte}] PARA UUID [{terminal_uuid}] ---")
            comando_impresora = 'I0X' if tipo_reporte == 'X' else 'I0Z'
            respuesta = ejecutar_comando_fiscal("SendCmd", comando_impresora, fiscal_dir)
            print(f"--- [LOCK LIBERADO] REPORTE PROCESADO PARA UUID [{terminal_uuid}] ---")
            return jsonify({"message": f"Reporte '{tipo_reporte}' enviado a UUID [{terminal_uuid}].", "respuesta_impresora": respuesta.get('mensaje')}), 200
    except (ValueError, FileNotFoundError) as e: return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error crítico imprimiendo reporte para UUID [{data.get('terminalUUID')}]: {str(e)}"}), 500

@app.route('/estado-impresora-fiscal/<terminal_uuid>', methods=['GET'])
def estado_impresora_fiscal(terminal_uuid):
    ruta_completa_estado = None
    try:
        fiscal_dir = get_and_validate_fiscal_dir(terminal_uuid)
        
        archivo_estado = f"estado_{uuid.uuid4().hex}.txt"
        ruta_completa_estado = os.path.join(fiscal_dir, archivo_estado)
        
        ejecutar_comando_fiscal("ReadFpStatus", ruta_completa_estado, fiscal_dir)
        
        with open(ruta_completa_estado, 'r') as f: 
            linea_estado = f.read().strip()
            
        partes = linea_estado.replace(":", " ").split()
        status_code = int(partes[partes.index("Status") + 1])
        error_code = int(partes[partes.index("Error") + 1])
        
        respuesta = {
            "status_code": status_code, 
            "status_descripcion": STATUS_CODES.get(status_code, "?"), 
            "error_code": error_code, 
            "error_descripcion": ERROR_CODES.get(error_code, "?")
        }
        return jsonify(respuesta), 200
        
    except (ValueError, FileNotFoundError) as e: 
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error obteniendo estado de UUID [{terminal_uuid}]: {str(e)}"}), 500
    finally:
        if ruta_completa_estado and os.path.exists(ruta_completa_estado): 
            os.remove(ruta_completa_estado)

@app.route('/test-fiscal/<terminal_uuid>', methods=['POST'])
def test_fiscal(terminal_uuid):
    try:
        fiscal_dir = get_and_validate_fiscal_dir(terminal_uuid)
        # El comando 'D' es un comando de diagnóstico simple.
        respuesta = ejecutar_comando_fiscal("SendCmd", "D", fiscal_dir)
        return jsonify({
            "message": f"Comando de prueba enviado exitosamente a UUID [{terminal_uuid}].",
            "respuesta_impresora": respuesta.get('mensaje')
        }), 200
    except (ValueError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error en la prueba fiscal para UUID [{terminal_uuid}]: {str(e)}"}), 500

if __name__ == '__main__':
    print(f"Iniciando servidor de impresión ADAPTADO (FISCAL Y NO FISCAL) en http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
