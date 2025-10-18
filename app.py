from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import pandas as pd
import asyncio
import os
from pathlib import Path
from datetime import datetime
import zipfile
from sat_navigator import SATNavigator
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import traceback
import calendar



from sqlalchemy import create_engine, Column, Integer, String, Float, MetaData, Table, Text
from sqlalchemy.orm import sessionmaker

# IMPORTAR EL NUEVO MÓDULO
from xml_processor import extraer_productos_de_zip

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['DATABASE'] = 'sqlite:///sat_data.db'

# Crear carpetas si no existen
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# Formato esperado del Excel
COLUMNAS_REQUERIDAS = [
    'usuario',
    'password', 
    'mes',
    'año'
]


# --- Configuración de la base de datos ---
engine = create_engine(app.config['DATABASE'], echo=False)
metadata = MetaData()

# Definir tabla para almacenar datos de los XML
xml_table = Table(
    'xml_data', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('Archivo', String(500)),
    Column('DTE_ID', String(200)),
    Column('TipoDocumento', String(50)),
    Column('FechaHoraEmision', String(50)),
    Column('CodigoMoneda', String(10)),
    Column('NombreEmisor', String(500)),
    Column('NombreComercial', String(500)),
    Column('NIT_Emisor', String(50)),
    Column('CodigoEstablecimiento', String(50)),
    Column('DireccionEmisor', Text),
    Column('NombreReceptor', String(500)),
    Column('NIT_Receptor', String(50)),
    Column('DireccionReceptor', Text),
    Column('NumeroAutorizacion_Serie', String(50)),
    Column('NumeroAutorizacion_Numero', String(50)),
    Column('NumeroAutorizacion_Texto', String(200)),
    Column('FechaHoraCertificacion', String(50)),
    Column('NIT_Certificador', String(50)),
    Column('Nombre_Certificador', String(500)),
    Column('Linea_Numero', String(10)),
    Column('BienOServicio', String(50)),
    Column('Descripcion', Text),
    Column('Cantidad', Float),
    Column('UnidadMedida', String(50)),
    Column('PrecioUnitario', Float),
    Column('Precio', Float),
    Column('Descuento', Float),
    Column('Total', Float),
    Column('Impuestos', Text),
    Column('fecha_carga', String(50))  # Timestamp de cuándo se cargó
)

# Crear la tabla si no existe
metadata.create_all(engine)
Session = sessionmaker(bind=engine)


# ==========================================
# NUEVOS ENDPOINTS PARA PROCESAMIENTO XML
# ==========================================

@app.route('/procesar-xml', methods=['POST'])
def procesar_xml():
    """
    Endpoint para subir un ZIP con XMLs, procesarlos y guardarlos en la BD
    """
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se subió ningún archivo'}), 400
    
    archivo = request.files['archivo']
    
    if archivo.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    if not archivo.filename.lower().endswith('.zip'):
        return jsonify({'error': 'Solo se permiten archivos ZIP'}), 400
    
    try:
        # Guardar archivo temporalmente
        filename = secure_filename(archivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        archivo.save(filepath)
        
        print(f"\n📦 Procesando ZIP: {filename}")
        
        # Extraer datos del ZIP
        df, errores = extraer_productos_de_zip(filepath)
        
        if df.empty:
            return jsonify({
                'error': 'No se encontraron datos válidos en el ZIP',
                'errores': errores
            }), 400
        
        # Agregar timestamp de carga
        df['fecha_carga'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Guardar en base de datos
        registros_insertados = guardar_en_bd(df)
        
        # Limpiar archivo temporal
        try:
            os.remove(filepath)
        except:
            pass
        
        return jsonify({
            'success': True,
            'registros_procesados': len(df),
            'registros_insertados': registros_insertados,
            'archivos_xml': df['Archivo'].nunique(),
            'errores': errores if errores else None,
            'resumen': {
                'total_items': len(df),
                'emisores_unicos': df['NIT_Emisor'].nunique(),
                'receptores_unicos': df['NIT_Receptor'].nunique(),
                'monto_total': float(df['Total'].sum()),
                'moneda': df['CodigoMoneda'].mode()[0] if len(df) > 0 else 'N/A'
            }
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Error al procesar XML: {str(e)}'}), 500


def guardar_en_bd(df: pd.DataFrame) -> int:
    """
    Guarda el DataFrame en la base de datos SQLite
    
    Args:
        df: DataFrame con los datos procesados
        
    Returns:
        Número de registros insertados
    """
    try:
        # Usar to_sql de pandas para insertar
        registros = df.to_sql(
            'xml_data',
            engine,
            if_exists='append',  # agregar a registros existentes
            index=False,
            chunksize=1000  # insertar en lotes para mejor performance
        )
        
        print(f"✅ {len(df)} registros guardados en la BD")
        return len(df)
        
    except Exception as e:
        print(f"❌ Error guardando en BD: {str(e)}")
        traceback.print_exc()
        raise


@app.route('/consultar-xml', methods=['GET'])
def consultar_xml():
    """
    Endpoint para consultar datos guardados en la BD
    Query params:
    - nit_emisor: filtrar por NIT emisor
    - nit_receptor: filtrar por NIT receptor
    - fecha_desde: filtrar desde fecha (YYYY-MM-DD)
    - fecha_hasta: filtrar hasta fecha (YYYY-MM-DD)
    - limit: número máximo de registros (default 100)
    """
    try:
        session = Session()
        
        # Construir query base
        query = session.query(xml_table)
        
        # Aplicar filtros opcionales
        nit_emisor = request.args.get('nit_emisor')
        if nit_emisor:
            query = query.filter(xml_table.c.NIT_Emisor == nit_emisor)
        
        nit_receptor = request.args.get('nit_receptor')
        if nit_receptor:
            query = query.filter(xml_table.c.NIT_Receptor == nit_receptor)
        
        fecha_desde = request.args.get('fecha_desde')
        if fecha_desde:
            query = query.filter(xml_table.c.FechaHoraEmision >= fecha_desde)
        
        fecha_hasta = request.args.get('fecha_hasta')
        if fecha_hasta:
            query = query.filter(xml_table.c.FechaHoraEmision <= fecha_hasta)
        
        # Límite de registros
        limit = int(request.args.get('limit', 100))
        query = query.limit(limit)
        
        # Ejecutar query
        resultados = query.all()
        
        # Convertir a lista de diccionarios
        data = []
        for row in resultados:
            data.append(dict(row._mapping))
        
        session.close()
        
        return jsonify({
            'success': True,
            'total_registros': len(data),
            'registros': data
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Error al consultar: {str(e)}'}), 500


@app.route('/exportar-xml', methods=['GET'])
def exportar_xml():
    """
    Exporta los datos de la BD a Excel
    Acepta los mismos filtros que /consultar-xml
    """
    try:
        session = Session()
        
        # Construir query (misma lógica que consultar_xml)
        query = session.query(xml_table)
        
        nit_emisor = request.args.get('nit_emisor')
        if nit_emisor:
            query = query.filter(xml_table.c.NIT_Emisor == nit_emisor)
        
        nit_receptor = request.args.get('nit_receptor')
        if nit_receptor:
            query = query.filter(xml_table.c.NIT_Receptor == nit_receptor)
        
        fecha_desde = request.args.get('fecha_desde')
        if fecha_desde:
            query = query.filter(xml_table.c.FechaHoraEmision >= fecha_desde)
        
        fecha_hasta = request.args.get('fecha_hasta')
        if fecha_hasta:
            query = query.filter(xml_table.c.FechaHoraEmision <= fecha_hasta)
        
        # Ejecutar query
        resultados = query.all()
        
        # Convertir a DataFrame
        data = [dict(row._mapping) for row in resultados]
        df = pd.DataFrame(data)
        
        session.close()
        
        if df.empty:
            return jsonify({'error': 'No hay datos para exportar'}), 404
        
        # Guardar Excel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f"datos_xml_{timestamp}.xlsx"
        excel_path = os.path.join(app.config['DOWNLOAD_FOLDER'], excel_filename)
        
        df.to_excel(excel_path, index=False, engine='openpyxl')
        
        return send_file(
            excel_path,
            as_attachment=True,
            download_name=excel_filename
        )
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Error al exportar: {str(e)}'}), 500


@app.route('/estadisticas-xml', methods=['GET'])
def estadisticas_xml():
    """
    Devuelve estadísticas generales de los datos en la BD
    """
    try:
        session = Session()
        
        # Contar registros totales
        total_registros = session.query(xml_table).count()
        
        # Obtener datos para estadísticas
        query = session.query(xml_table)
        df = pd.read_sql(query.statement, engine)
        
        session.close()
        
        if df.empty:
            return jsonify({
                'success': True,
                'total_registros': 0,
                'mensaje': 'No hay datos en la base de datos'
            })
        
        stats = {
            'success': True,
            'total_registros': total_registros,
            'total_facturas': df['DTE_ID'].nunique(),
            'emisores_unicos': int(df['NIT_Emisor'].nunique()),
            'receptores_unicos': int(df['NIT_Receptor'].nunique()),
            'monto_total': float(df['Total'].sum()),
            'monto_promedio': float(df['Total'].mean()),
            'cantidad_total_items': float(df['Cantidad'].sum()),
            'rango_fechas': {
                'desde': df['FechaHoraEmision'].min(),
                'hasta': df['FechaHoraEmision'].max()
            },
            'top_emisores': df.groupby('NombreComercial')['Total'].sum().nlargest(5).to_dict(),
            'top_productos': df.groupby('Descripcion')['Cantidad'].sum().nlargest(10).to_dict()
        }
        
        return jsonify(stats)
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Error al calcular estadísticas: {str(e)}'}), 500
    




def calcular_fechas_del_mes(mes, año):
    """
    Calcula el primer y último día de un mes dado, considerando años bisiestos
    
    Args:
        mes: Número del mes (1-12)
        año: Año completo (ej: 2025)
    
    Returns:
        Tupla con (fecha_inicio, fecha_fin) en formato DD/MM/YYYY
    """
    # Validar mes
    if not 1 <= mes <= 12:
        raise ValueError(f"Mes inválido: {mes}. Debe estar entre 1 y 12")
    
    # Validar año
    if not 1900 <= año <= 2100:
        raise ValueError(f"Año inválido: {año}. Debe estar entre 1900 y 2100")
    
    # Primer día del mes siempre es 1
    dia_inicio = 1
    
    # Último día del mes (considera años bisiestos automáticamente)
    dia_fin = calendar.monthrange(año, mes)[1]
    
    # Formatear a DD/MM/YYYY
    fecha_inicio = f"{dia_inicio:02d}/{mes:02d}/{año}"
    fecha_fin = f"{dia_fin:02d}/{mes:02d}/{año}"
    
    return fecha_inicio, fecha_fin


def validar_excel(filepath):
    """Valida que el Excel tenga las columnas correctas y procesa los datos"""
    try:
        df = pd.read_excel(filepath)
        
        # Normalizar nombres de columnas
        df.columns = df.columns.str.lower().str.strip()
        
        # Verificar columnas requeridas
        columnas_faltantes = set(COLUMNAS_REQUERIDAS) - set(df.columns)
        
        if columnas_faltantes:
            return False, f"Faltan columnas: {', '.join(columnas_faltantes)}"
        
        # Validar que no haya filas vacías
        if df.empty:
            return False, "El archivo no contiene datos"
        
        # ===== PROCESAR MES Y AÑO =====
        print("\n📅 Calculando fechas desde mes/año...")
        errores = []
        
        # Crear nuevas columnas para las fechas
        df['fecha_inicio'] = ''
        df['fecha_fin'] = ''
        
        for idx, row in df.iterrows():
            fila_num = idx + 2  # +2 porque Excel empieza en 1 y tiene header
            
            try:
                # Leer y validar mes
                mes = row['mes']
                if pd.isna(mes):
                    raise ValueError("Mes vacío")
                mes = int(mes)
                
                # Leer y validar año
                año = row['año']
                if pd.isna(año):
                    raise ValueError("Año vacío")
                año = int(año)
                
                # Ajustar año si es corto (ej: 25 → 2025)
                if año < 100:
                    año = 2000 + año if año <= 30 else 1900 + año
                
                # Calcular fechas
                fecha_inicio, fecha_fin = calcular_fechas_del_mes(mes, año)
                
                # Guardar en el DataFrame
                df.at[idx, 'fecha_inicio'] = fecha_inicio
                df.at[idx, 'fecha_fin'] = fecha_fin
                
                # Mostrar info
                mes_nombre = calendar.month_name[mes] if 1 <= mes <= 12 else str(mes)
                print(f"   ✓ Fila {fila_num}: {mes_nombre} {año} → {fecha_inicio} al {fecha_fin}")
                
            except Exception as e:
                error_msg = f"Fila {fila_num}: {str(e)}"
                errores.append(error_msg)
                print(f"   ✗ {error_msg}")
        
        # Si hubo errores, reportarlos
        if errores:
            return False, "Errores al procesar fechas:\n" + "\n".join(errores)
        
        # ===== VALIDAR OTROS CAMPOS =====
        
        # # Validar tipo_operacion
        # tipos_validos = ['ambos', 'emitidos', 'recibidos']
        # df['tipo_operacion'] = df['tipo_operacion'].str.strip().str.lower()
        
        # for idx, tipo in enumerate(df['tipo_operacion']):
        #     if tipo not in tipos_validos:
        #         df.at[idx, 'tipo_operacion'] = tipo.capitalize()
        
        # # Validar formato
        # formatos_validos = ['excel', 'pdf', 'xml']
        # df['formato'] = df['formato'].str.strip().str.lower()
        
        # for idx, formato in enumerate(df['formato']):
        #     if formato not in formatos_validos:
        #         return False, f"Fila {idx+2}: formato '{formato}' no válido. Use: excel, pdf, xml"
        
        # Normalizar usuario (quitar espacios, guiones, puntos)
        df['usuario'] = df['usuario'].astype(str).str.replace(r'[^\d]', '', regex=True)
        
        # Verificar que no haya usuarios vacíos
        if df['usuario'].str.len().min() < 5:
            return False, "Hay usuarios con menos de 5 dígitos (inválidos)"
        
        print(f"\n✅ Archivo validado: {len(df)} empresa(s) lista(s) para procesar")
        
        return True, df
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error al leer archivo: {str(e)}"

def procesar_fechas(fecha_str):
    """
    Convierte fecha normalizada de DD/MM/AAAA a MM/DD/AAAA para el sistema SAT
    
    Args:
        fecha_str: Fecha en formato DD/MM/AAAA
    
    Returns:
        Fecha en formato MM/DD/AAAA
    """
    try:
        partes = str(fecha_str).split("/")
        if len(partes) != 3:
            raise ValueError(f"Formato incorrecto: {fecha_str}")
        return f"{partes[1]}/{partes[0]}/{partes[2]}"
    except Exception as e:
        raise ValueError(f"Error al procesar fecha {fecha_str}: {str(e)}")


async def procesar_empresa_async(datos):
    """Procesa una sola empresa de forma asíncrona"""
    nav = None
    try:
        print(f"\n{'='*60}")
        print(f"🏢 PROCESANDO: {datos['usuario']}")
        print(f"{'='*60}")
        
        # Crear navegador
        nav = SATNavigator()
        await nav.iniciar(headless=False)  # Modo headless para servidor
        
        # Login
        await nav.ir_a_login()
        await nav.hacer_login(datos['usuario'], datos['password'])
        await asyncio.sleep(2)
        
        # Procesar fechas
        fecha_inicio = procesar_fechas(datos['fecha_inicio'])
        fecha_fin = procesar_fechas(datos['fecha_fin'])
        
        # Ejecutar flujo
        archivos = await nav.flujo_descarga_automatico(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo_operacion="Ambos",#datos['tipo_operacion'],#TODO: descomentar cuando se agregue al excel
            formato_descarga="Excel",#datos['formato'],#TODO: descomentar cuando se agregue al excel
            navegar_desde_inicio=True
        )
        
        resultado = {
            'usuario': datos['usuario'],
            'status': 'success',
            'archivos': archivos or [],
            'mensaje': f"✅ Procesado correctamente - {len(archivos or [])} archivo(s)"
        }
        
        print(f"✅ {datos['usuario']}: COMPLETADO")
        return resultado
        
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        print(f"❌ {datos['usuario']}: {error_msg}")
        traceback.print_exc()
        
        return {
            'usuario': datos['usuario'],
            'status': 'error',
            'archivos': [],
            'mensaje': error_msg
        }
        
    finally:
        if nav:
            try:
                await nav.cerrar()
            except:
                pass


def procesar_empresa_sync(datos):
    """Wrapper sincrónico para multiprocessing"""
    return asyncio.run(procesar_empresa_async(datos))


async def procesar_secuencial(empresas_data):
    """Procesa empresas una por una"""
    resultados = []
    
    for idx, datos in enumerate(empresas_data, 1):
        print(f"\n📊 Procesando empresa {idx}/{len(empresas_data)}")
        resultado = await procesar_empresa_async(datos)
        resultados.append(resultado)
    
    return resultados

def agrupar_por_usuario(empresas_data):
    """
    Agrupa registros por usuario/password para procesarlos en una sola sesión
    
    Returns:
        Lista de diccionarios con {usuario, password, periodos}
    """
    from collections import defaultdict
    
    grupos = defaultdict(list)
    
    for empresa in empresas_data:
        key = (empresa['usuario'], empresa['password'])
        grupos[key].append({
            'fecha_inicio': empresa['fecha_inicio'],
            'fecha_fin': empresa['fecha_fin'],
            'mes': empresa.get('mes', ''),
            'año': empresa.get('año', ''),
            'tipo_operacion': empresa.get('tipo_operacion', 'Ambos'),
            'formato': empresa.get('formato', 'excel')
        })
    
    # Convertir a lista
    resultado = []
    for (usuario, password), periodos in grupos.items():
        resultado.append({
            'usuario': usuario,
            'password': password,
            'periodos': periodos
        })
    
    return resultado


async def procesar_empresa_optimizado_async(datos):
    """Procesa una empresa con múltiples períodos en una sola sesión"""
    nav = None
    try:
        usuario = datos['usuario']
        periodos = datos['periodos']
        
        print(f"\n{'='*60}")
        print(f"🏢 PROCESANDO: {usuario}")
        print(f"📅 Períodos a procesar: {len(periodos)}")
        print(f"{'='*60}")
        
        # Crear navegador
        nav = SATNavigator()
        await nav.iniciar(headless=False)
        
        # Login UNA SOLA VEZ
        await nav.ir_a_login()
        await nav.hacer_login(usuario, datos['password'])
        await asyncio.sleep(2)
        

        if not await nav.verificar_pagina_cargada():
            raise Exception("La página no cargó correctamente después del login")        
        
        # Convertir fechas a formato SAT
        periodos_procesados = []
        for periodo in periodos:
            fecha_inicio = procesar_fechas(periodo['fecha_inicio'])
            fecha_fin = procesar_fechas(periodo['fecha_fin'])
            
            periodos_procesados.append({
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'tipo_operacion': periodo.get('tipo_operacion', 'Ambos'),
                'formato': periodo.get('formato', 'excel')
            })
        
        # Descargar TODOS los períodos en una sola sesión
        archivos = await nav.descargar_multiples_periodos(
            periodos=periodos_procesados,
            navegar_primera_vez=True
        )
        
        resultado = {
            'usuario': usuario,
            'status': 'success',
            'archivos': archivos or [],
            'periodos_procesados': len(periodos),
            'mensaje': f"✅ {len(periodos)} período(s) procesado(s) - {len(archivos or [])} archivo(s)"
        }
        
        print(f"✅ {usuario}: COMPLETADO - {len(periodos)} períodos")
        return resultado
        
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        print(f"❌ {usuario}: {error_msg}")
        traceback.print_exc()
        
        return {
            'usuario': datos['usuario'],
            'status': 'error',
            'archivos': [],
            'periodos_procesados': 0,
            'mensaje': error_msg
        }
        
    finally:
        if nav:
            try:
                await nav.cerrar()
            except:
                pass


async def procesar_secuencial_optimizado(empresas_agrupadas):
    """Procesa empresas agrupadas una por una"""
    resultados = []
    
    for idx, datos in enumerate(empresas_agrupadas, 1):
        print(f"\n📊 Procesando usuario {idx}/{len(empresas_agrupadas)}")
        resultado = await procesar_empresa_optimizado_async(datos)
        resultados.append(resultado)
    
    return resultados


def procesar_paralelo(empresas_data, max_workers=3):
    """Procesa empresas en paralelo usando multiprocessing"""
    print(f"\n🚀 MODO PARALELO: {max_workers} procesos simultáneos")
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        resultados = list(executor.map(procesar_empresa_sync, empresas_data))
    
    return resultados


@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')


@app.route('/validar', methods=['POST'])
def validar():
    """Endpoint para validar archivo sin procesarlo"""
    
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se subió ningún archivo'}), 400
    
    archivo = request.files['archivo']
    
    if archivo.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    try:
        filename = secure_filename(archivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        archivo.save(filepath)
        
        valido, resultado = validar_excel(filepath)
        
        if not valido:
            return jsonify({'error': resultado}), 400
        
        df = resultado
        
        validacion_info = {
            'valido': True,
            'total_filas': len(df),
            'columnas': list(df.columns),
            'empresas': []
        }
        
        for idx, row in df.iterrows():
            empresa_info = {
                'fila': idx + 2,
                'usuario': row['usuario'],
                'mes': int(row['mes']),
                'año': int(row['año']),
                'fecha_inicio': row['fecha_inicio'],
                'fecha_fin': row['fecha_fin'],
                #'tipo_operacion': row['tipo_operacion'].capitalize(),
                #'formato': row['formato']
            }
            validacion_info['empresas'].append(empresa_info)
        
        return jsonify(validacion_info)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al validar: {str(e)}'}), 500
    

@app.route('/plantilla')
def descargar_plantilla():
    """Descarga plantilla Excel de ejemplo"""
    # Crear DataFrame de ejemplo
    df = pd.DataFrame({
        'usuario': ['12345678', '87654321'],
        'password': ['password123', 'password456'],
        'mes': [9, 8],
        'año': [2025, 2024],
        #'tipo_operacion': ['Ambos', 'Emitidos'],
        #'formato': ['excel', 'pdf']
    })
    
    # Guardar temporal
    plantilla_path = os.path.join(app.config['UPLOAD_FOLDER'], 'plantilla_sat.xlsx')
    df.to_excel(plantilla_path, index=False)
    
    return send_file(
        plantilla_path,
        as_attachment=True,
        download_name='plantilla_sat.xlsx'
    )



@app.route('/procesar', methods=['POST'])
def procesar():
    """Endpoint principal para procesar el archivo"""
    
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se subió ningún archivo'}), 400
    
    archivo = request.files['archivo']
    modo = request.form.get('modo', 'secuencial')
    
    if archivo.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    if not archivo.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'Solo se permiten archivos Excel (.xlsx, .xls)'}), 400
    
    try:
        filename = secure_filename(archivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        archivo.save(filepath)
        
        valido, resultado = validar_excel(filepath)
        
        if not valido:
            return jsonify({'error': resultado}), 400
        
        df = resultado
        empresas_data = df.to_dict('records')
        
        # AGRUPAR POR USUARIO/PASSWORD
        empresas_agrupadas = agrupar_por_usuario(empresas_data)
        
        print(f"\n📋 Registros originales: {len(empresas_data)}")
        print(f"👥 Usuarios únicos: {len(empresas_agrupadas)}")
        
        # Mostrar agrupación
        for grupo in empresas_agrupadas:
            print(f"   • {grupo['usuario']}: {len(grupo['periodos'])} período(s)")
        
        # Procesar (solo secuencial por ahora, paralelo con sesiones es complejo)
        resultados = asyncio.run(procesar_secuencial_optimizado(empresas_agrupadas))
        
        # Comprimir archivos
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"sat_reportes_{timestamp}.zip"
        zip_path = os.path.join(app.config['DOWNLOAD_FOLDER'], zip_filename)
        
        archivos_totales = []
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for resultado in resultados:
                if resultado['archivos']:
                    for archivo in resultado['archivos']:
                        if os.path.exists(archivo):
                            zipf.write(archivo, os.path.basename(archivo))
                            archivos_totales.append(archivo)
        
        # Limpiar
        for archivo in archivos_totales:
            try:
                os.remove(archivo)
            except:
                pass
        
        return jsonify({
            'success': True,
            'resultados': resultados,
            'zip_file': zip_filename,
            'total_usuarios': len(empresas_agrupadas),
            'total_periodos': sum(r.get('periodos_procesados', 0) for r in resultados),
            'exitosos': sum(1 for r in resultados if r['status'] == 'success'),
            'errores': sum(1 for r in resultados if r['status'] == 'error')
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Error al procesar: {str(e)}'}), 500

@app.route('/descargar/<filename>')
def descargar(filename):
    """Descarga el archivo ZIP con los reportes"""
    filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'Archivo no encontrado'}), 404
    
    return send_file(filepath, as_attachment=True)


# if __name__ == '__main__':
#     # Para desarrollo
#     app.run(host='0.0.0.0', port=5000, debug=True)
    
#     # Para producción usar gunicorn:
#     # gunicorn -w 4 -b 0.0.0.0:5000 app:app


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
