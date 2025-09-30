# Archivo: servidor_fiscal_linux.py
# Servidor de impresión para impresoras fiscales The Factory HKA en Linux.
# Maneja facturación, pagos mixtos, IGTF, reportes X/Z y test de conexión.
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import traceback
import re

# --- Configuración General ---
app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN PARA LINUX ---
HOME_DIR = os.path.expanduser("~")
COMANDOS_DIR = os.path.join(HOME_DIR, "IntTFHKA")
EXECUTABLE_NAME = "Tfinulx"
INTTFHKA_PATH = os.path.join(COMANDOS_DIR, EXECUTABLE_NAME)

# --- CONFIGURACIÓN DE IMPUESTOS ---
IGTF_SLOTS = [20, 21, 22, 23, 24] # Slots de pago que activan el IGTF.

#=============================================================================
# FUNCIÓN CENTRAL DE COMUNICACIÓN
#=============================================================================
def ejecutar_comando_fiscal(comando_str, lineas_esperadas=None):
    """
    Ejecuta un comando en Tfinulx y valida la respuesta.
    """
    print(f"Ejecutando: {comando_str}")
    comando_completo = f"./{EXECUTABLE_NAME} '{comando_str}'"
    try:
        resultado_proceso = subprocess.run(
            comando_completo, shell=True, capture_output=True, text=True,
            cwd=COMANDOS_DIR, encoding="utf-8", timeout=30
        )
        salida_texto = resultado_proceso.stdout.strip()
        print(f" > Respuesta de Tfinulx: '{salida_texto}'")

        if resultado_proceso.stderr:
            raise Exception(f"Error reportado por Tfinulx: {resultado_proceso.stderr.strip()}")

        es_exitoso = False
        if "SENDFILECMD" in comando_str.upper() and lineas_esperadas is not None:
            match = re.search(r"Retorno:\s*(\d+)", salida_texto)
            if match:
                lineas_procesadas = int(match.group(1))
                if lineas_procesadas == lineas_esperadas:
                    print(f" > SendFileCmd exitoso. Se procesaron todas las {lineas_procesadas} líneas.")
                    es_exitoso = True
                else:
                    if "Error: 128" in salida_texto:
                        raise Exception(f"Error de Comunicación (128) después de procesar {lineas_procesadas} de {lineas_esperadas} líneas.")
                    else:
                        raise Exception(f"Fallo en SendFileCmd. Se esperaban {lineas_esperadas} líneas pero la impresora solo procesó {lineas_procesadas}.")
        else:
            if "TRUE" in salida_texto.upper():
                es_exitoso = True
        
        if es_exitoso:
            return salida_texto
        else:
            raise Exception(f"Comando falló. Respuesta de la impresora: '{salida_texto}'")
    except Exception as e:
        raise e

#=============================================================================
# ENDPOINTS DE UTILIDAD (NUEVOS)
#=============================================================================
@app.route('/test-fiscal', methods=['GET'])
def test_impresora_fiscal():
    """
    Envía un comando simple (imprimir configuración) para verificar la conexión.
    """
    try:
        respuesta = ejecutar_comando_fiscal('SendCmd(D)')
        return jsonify({"message": "Prueba de conexión fiscal exitosa.", "respuesta_impresora": respuesta}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error en la prueba fiscal: {str(e)}"}), 500

@app.route('/imprimir-reporte-fiscal', methods=['POST'])
def imprimir_reporte_fiscal():
    """
    Emite un reporte fiscal X o Z.
    Recibe: {"tipo": "X"} o {"tipo": "Z"}
    """
    try:
        data = request.get_json()
        if not data or 'tipo' not in data:
            return jsonify({"error": "Payload incorrecto. Se esperaba {'tipo': 'X' | 'Z'}"}), 400

        tipo_reporte = data.get('tipo', '').upper()
        
        if tipo_reporte == 'X':
            comando = 'SendCmd(I0X)'
        elif tipo_reporte == 'Z':
            comando = 'SendCmd(I0Z)'
        else:
            return jsonify({"error": "Tipo de reporte no válido. Use 'X' o 'Z'."}), 400

        print(f"\n--- INICIANDO IMPRESIÓN DE REPORTE {tipo_reporte} ---")
        respuesta = ejecutar_comando_fiscal(comando)
        
        return jsonify({"message": f"Comando para Reporte '{tipo_reporte}' enviado correctamente.", "respuesta_impresora": respuesta}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error imprimiendo reporte fiscal: {str(e)}"}), 500

#=============================================================================
# ENDPOINT PRINCIPAL DE FACTURACIÓN
#=============================================================================
@app.route('/imprimir-factura-fiscal', methods=['POST'])
def imprimir_factura_fiscal():
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "No se recibieron datos"}), 400

        print("\n--- INICIANDO PROCESO DE FACTURA FISCAL (LÓGICA IGTF OFICIAL) ---")
        comandos_para_archivo = []
        pagos = data.get('pagos', [])
        se_uso_pago_igtf = any(int(p.get('slot_fiscal', 0)) in IGTF_SLOTS for p in pagos)

        # --- A. Comandos de Cliente e Items ---
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

        # --- C. Lógica de Pagos (según manual oficial) ---
        if not pagos:
            comandos_para_archivo.append('101')
        elif len(pagos) == 1:
            pago = pagos[0]; slot = int(pago.get('slot_fiscal', 1))
            comandos_para_archivo.append(f"1{slot:02d}")
        else:
            for i, pago in enumerate(pagos):
                slot = int(pago.get('slot_fiscal', 1))
                if i < len(pagos) - 1:
                    monto = float(pago.get('monto', 0)); monto_fmt = f"{monto:.2f}".replace('.', '').zfill(12)
                    comandos_para_archivo.append(f"2{slot:02d}{monto_fmt}")
                else:
                    comandos_para_archivo.append(f"1{slot:02d}")

        # --- D. Comando de Cierre Obligatorio 199 para IGTF ---
        if se_uso_pago_igtf:
            comandos_para_archivo.append('199')

        # --- E. Escribir y Enviar el Archivo ---
        nombre_archivo_final = "factura_actual.txt"
        ruta_archivo_final = os.path.join(COMANDOS_DIR, nombre_archivo_final)
        with open(ruta_archivo_final, "w", encoding="utf-8") as f:
            f.write("\n".join(comandos_para_archivo))
        
        print(f"\n--- Contenido de '{nombre_archivo_final}' ---")
        for cmd in comandos_para_archivo: print(cmd)
        print("-------------------------------------------\n")

        numero_de_lineas = len(comandos_para_archivo)
        respuesta_final = ejecutar_comando_fiscal(f'SendFileCmd("{nombre_archivo_final}")', lineas_esperadas=numero_de_lineas)

        print("--- PROCESO DE FACTURA FISCAL COMPLETADO CON ÉXITO ---")
        return jsonify({ "message": "Factura fiscal procesada correctamente.", "respuesta_impresora": respuesta_final }), 200
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error crítico durante el envío fiscal: {str(e)}"}), 500

#=============================================================================
# INICIO DEL SERVIDOR
#=============================================================================
if __name__ == '__main__':
    print("Iniciando servidor de impresión fiscal en http://0.0.0.0:5000")
    print(f"Lógica de IGTF activa para slots: {IGTF_SLOTS}")
    print(f"Directorio de trabajo: {COMANDOS_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=True)
