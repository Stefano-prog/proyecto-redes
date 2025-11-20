from flask import Flask, render_template, request, jsonify
import hashlib
import itertools
import string
import time
import os
from datetime import datetime
from multiprocessing import Pool, cpu_count
import math

app = Flask(__name__)

def md5_hex_bytes(b):
    return hashlib.md5(b).hexdigest()

def sha256_hex_bytes(b):
    return hashlib.sha256(b).hexdigest()

def probar_chunk(args):
    """
    Función que se ejecuta en cada proceso.
    Prueba un chunk de combinaciones.
    """
    objetivo_hex, charset, length, start_idx, end_idx, algoritmo = args
    hash_func = md5_hex_bytes if algoritmo == 'md5' else sha256_hex_bytes
    
    intentos_locales = 0
    combinaciones = itertools.product(charset, repeat=length)
    
    # Saltar al índice de inicio
    for _ in range(start_idx):
        next(combinaciones, None)
    
    # Probar combinaciones en el rango asignado
    for i, combo in enumerate(combinaciones):
        if i >= (end_idx - start_idx):
            break
        intentos_locales += 1
        candidato = ''.join(combo)
        if hash_func(candidato.encode('utf-8')) == objetivo_hex:
            return candidato, intentos_locales
    
    return None, intentos_locales

def fuerza_bruta_multinucleo(objetivo_hex, charset, max_len, algoritmo='md5', num_cores=None):
    """
    Implementación con multiprocessing para usar múltiples núcleos.
    """
    if num_cores is None:
        num_cores = cpu_count()
    
    intentos_totales = 0
    t0 = time.time()
    timestamp_inicio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"🔥 Usando {num_cores} núcleos para la búsqueda")
    
    for length in range(1, max_len + 1):
        # Calcular el número total de combinaciones para esta longitud
        total_combos = len(charset) ** length
        print(f"📊 Longitud {length}: {total_combos:,} combinaciones posibles")
        
        # Dividir el trabajo entre los núcleos
        chunk_size = math.ceil(total_combos / num_cores)
        tasks = []
        
        for i in range(num_cores):
            start_idx = i * chunk_size
            end_idx = min((i + 1) * chunk_size, total_combos)
            
            if start_idx >= total_combos:
                break
            
            tasks.append((
                objetivo_hex,
                charset,
                length,
                start_idx,
                end_idx,
                algoritmo
            ))
        
        # Ejecutar en paralelo
        with Pool(processes=num_cores) as pool:
            resultados = pool.map(probar_chunk, tasks)
        
        # Procesar resultados
        for resultado, intentos in resultados:
            intentos_totales += intentos
            if resultado is not None:
                timestamp_fin = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return resultado, intentos_totales, time.time() - t0, timestamp_inicio, timestamp_fin
    
    timestamp_fin = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return None, intentos_totales, time.time() - t0, timestamp_inicio, timestamp_fin

def fuerza_bruta_simple(objetivo_hex, charset, max_len, algoritmo='md5'):
    """
    Implementación de un solo núcleo (original).
    """
    intentos = 0
    t0 = time.time()
    timestamp_inicio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    hash_func = md5_hex_bytes if algoritmo == 'md5' else sha256_hex_bytes
    
    for L in range(1, max_len + 1):
        for combo in itertools.product(charset, repeat=L):
            intentos += 1
            candidato = ''.join(combo)
            if hash_func(candidato.encode('utf-8')) == objetivo_hex:
                timestamp_fin = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return candidato, intentos, time.time() - t0, timestamp_inicio, timestamp_fin
    
    timestamp_fin = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return None, intentos, time.time() - t0, timestamp_inicio, timestamp_fin

@app.route('/')
def main():
    return render_template('index.html', num_cores=cpu_count())

@app.route('/generar', methods=['POST'])
def generar_hash():
    """
    Endpoint para generar hashes desde un texto
    """
    try:
        data = request.get_json()
        texto = data['texto']
        algoritmo = data.get('algoritmo', 'md5')
        incluir_timestamp = data.get('incluir_timestamp', False)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Hash normal (sin timestamp)
        texto_bytes = texto.encode('utf-8')
        if algoritmo == 'md5':
            hash_normal = md5_hex_bytes(texto_bytes)
        elif algoritmo == 'sha256':
            hash_normal = sha256_hex_bytes(texto_bytes)
        else:
            return jsonify({'error': 'Algoritmo no soportado'}), 400
        
        # Hash con timestamp (si está habilitado)
        hash_con_timestamp = None
        texto_con_timestamp = None
        if incluir_timestamp:
            texto_con_timestamp = f"{texto}_{timestamp}"
            texto_timestamp_bytes = texto_con_timestamp.encode('utf-8')
            if algoritmo == 'md5':
                hash_con_timestamp = md5_hex_bytes(texto_timestamp_bytes)
            elif algoritmo == 'sha256':
                hash_con_timestamp = sha256_hex_bytes(texto_timestamp_bytes)
        
        print(f"\n=== Hash Generado ===")
        print(f"Texto: {texto}")
        print(f"Algoritmo: {algoritmo.upper()}")
        print(f"Hash normal: {hash_normal}")
        if incluir_timestamp:
            print(f"Texto con timestamp: {texto_con_timestamp}")
            print(f"Hash con timestamp: {hash_con_timestamp}")
        print(f"Timestamp: {timestamp}")
        
        return jsonify({
            'texto': texto,
            'algoritmo': algoritmo.upper(),
            'hash': hash_normal,
            'timestamp': timestamp,
            'longitud': len(hash_normal),
            'incluir_timestamp': incluir_timestamp,
            'texto_con_timestamp': texto_con_timestamp,
            'hash_con_timestamp': hash_con_timestamp
        })
        
    except Exception as e:
        print(f"❌ Error al generar hash: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/crack', methods=['POST'])
def crack():
    try:
        data = request.get_json()
        objetivo = data['hash'].lower().strip()
        max_len = int(data['maxLen'])
        charset_options = data['charset']
        algoritmo = data.get('algoritmo', 'md5')
        usar_multinucleo = data.get('multinucleo', True)
        num_cores = data.get('num_cores', None)
        
        # Construir charset
        charset = ""
        if 'lowercase' in charset_options:
            charset += string.ascii_lowercase
        if 'uppercase' in charset_options:
            charset += string.ascii_uppercase
        if 'digits' in charset_options:
            charset += string.digits
        
        modo = "MULTINÚCLEO" if usar_multinucleo else "SIMPLE"
        print(f"\n=== Búsqueda {algoritmo.upper()} - Modo {modo} ===")
        print(f"Hash objetivo: {objetivo}")
        print(f"Charset: {charset}")
        print(f"Longitud máxima: {max_len}")
        print(f"Algoritmo: {algoritmo.upper()}")
        if usar_multinucleo:
            cores = num_cores if num_cores else cpu_count()
            print(f"Núcleos a usar: {cores}")
        print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Seleccionar modo de ejecución
        if usar_multinucleo:
            encontrado, intentos, tiempo, timestamp_inicio, timestamp_fin = fuerza_bruta_multinucleo(
                objetivo, charset, max_len, algoritmo, num_cores
            )
        else:
            encontrado, intentos, tiempo, timestamp_inicio, timestamp_fin = fuerza_bruta_simple(
                objetivo, charset, max_len, algoritmo
            )
        
        if encontrado:
            print(f"✅ ENCONTRADO: '{encontrado}'")
            print(f"Intentos: {intentos:,}")
            print(f"Tiempo: {tiempo:.2f}s")
        else:
            print(f"❌ No encontrado")
            print(f"Intentos: {intentos:,}")
            print(f"Tiempo: {tiempo:.2f}s")
        
        return jsonify({
            'encontrado': encontrado is not None,
            'texto': encontrado,
            'intentos': intentos,
            'tiempo': tiempo,
            'timestamp_inicio': timestamp_inicio,
            'timestamp_fin': timestamp_fin,
            'algoritmo': algoritmo.upper(),
            'modo': modo
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    print(f"💻 CPU disponibles: {cpu_count()} núcleos")
    app.run(debug=True, host='0.0.0.0', port=5000)

#prueba que se guardo
