# Archivo: servidor_fiscal.py
# Servidor de impresión para impresoras fiscales The Factory HKA
# Maneja facturación estándar, pagos mixtos y IGTF.
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import traceback
import re

# --- Configuración General ---
app = Flask(__name__)
CORS(app)
INTTFHKA_PATH = "C:\\IntTFHKA\\IntTfhka.exe"
COMANDOS_DIR = "C:\\IntTFHKA"

# --- CONFIGURACIÓN DE IMPUESTOS ---
# Slots de pago que la impresora considera como Divisa y que activan el IGTF.
IGTF_SLOTS = [20, 21, 22, 23, 24]

#=============================================================================
# FUNCIÓN CENTRAL DE COMUNICACIÓN
#=============================================================================
def ejecutar_comando_fiscal(comando_str, lineas_esperadas=None):
    """
    Ejecuta un comando en IntTfhka.exe y valida la respuesta.
    - Para SendFileCmd, valida que el número de líneas procesadas coincida.
    - Para otros, valida que la respuesta contenga "TRUE".
    """
    print(f"Ejecutando: {comando_str}")
    comando_completo = f'"{INTTFHKA_PATH}" {comando_str}'
    try:
        resultado_proceso = subprocess.run(
            comando_completo, shell=True, capture_output=True, text=True,
            cwd=COMANDOS_DIR, encoding="cp1252", timeout=30
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
                    if "Error: 128" in salida_texto:
                        raise Exception(f"Error de Comunicación (128) después de procesar {lineas_procesadas} de {lineas_esperadas} líneas. Revise el último comando enviado en el log.")
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
        
        # Determina si se usó un pago en divisa para añadir el comando de cierre 199.
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
            
            # Si el precio es 0, se asigna 0.01 y se marca como exento.
            if precio_con_iva <= 0.0:
                precio_con_iva = 0.01
                tasa_iva = 0.0

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
            comandos_para_archivo.append('101') # Cierre por defecto.
        elif len(pagos) == 1:
            # Si solo hay un pago, se usa el comando totalizador '1xx'.
            pago = pagos[0]; slot = int(pago.get('slot_fiscal', 1))
            comandos_para_archivo.append(f"1{slot:02d}")
        else:
            # Para pagos mixtos: N-1 pagos parciales ('2xx') y el último como totalizador ('1xx').
            for i, pago in enumerate(pagos):
                slot = int(pago.get('slot_fiscal', 1))
                if i < len(pagos) - 1: # Pagos parciales
                    monto = float(pago.get('monto', 0))
                    monto_fmt = f"{monto:.2f}".replace('.', '').zfill(12)
                    comandos_para_archivo.append(f"2{slot:02d}{monto_fmt}")
                else: # Último pago, es totalizador
                    comandos_para_archivo.append(f"1{slot:02d}")

        # --- D. Comando de Cierre Obligatorio 199 para IGTF ---
        if se_uso_pago_igtf:
            comandos_para_archivo.append('199')

        # --- E. Escribir y Enviar el Archivo ---
        nombre_archivo_final = "factura_actual.txt"
        with open(os.path.join(COMANDOS_DIR, nombre_archivo_final), "w", encoding="cp1252") as f:
            f.write("\n".join(comandos_para_archivo))
        
        # Log para depuración: Muestra el contenido del archivo de comandos.
        print(f"\n--- Contenido de '{nombre_archivo_final}' ---")
        for cmd in comandos_para_archivo: print(cmd)
        print("-------------------------------------------\n")

        # Se envía el archivo a la impresora, pasando el número de líneas para validación.
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
    print("Iniciando servidor de impresión fiscal en [http://0.0.0.0:5000](http://0.0.0.0:5000)")
    print(f"Lógica de IGTF activa para slots: {IGTF_SLOTS}")
    app.run(host='0.0.0.0', port=5000, debug=True)
