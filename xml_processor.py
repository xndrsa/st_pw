# # import zipfile
# # import xml.etree.ElementTree as ET
# # import pandas as pd
# # from io import BytesIO

# # # === CONFIGURACIÓN ===
# # zip_path = r"C:\Users\alex0\Downloads\consulta (4).zip"

# # # === FUNCIÓN PRINCIPAL ===
# # def extraer_productos_de_zip(zip_path):
# #     rows = []

# #     with zipfile.ZipFile(zip_path, "r") as z:
# #         for file_name in z.namelist():
# #             if not file_name.lower().endswith(".xml"):
# #                 continue

# #             with z.open(file_name) as f:
# #                 tree = ET.parse(f)
# #                 root = tree.getroot()

# #                 ns = {
# #                     "dte": "http://www.sat.gob.gt/dte/fel/0.2.0"
# #                 }

# #                 # Extraer datos generales
# #                 emisor = root.find(".//dte:Emisor", ns)
# #                 receptor = root.find(".//dte:Receptor", ns)
# #                 datos = root.find(".//dte:DatosGenerales", ns)

# #                 empresa = emisor.attrib.get("NombreComercial") if emisor is not None else ""
# #                 nit_emisor = emisor.attrib.get("NITEmisor") if emisor is not None else ""
# #                 cliente = receptor.attrib.get("NombreReceptor") if receptor is not None else ""
# #                 fecha = datos.attrib.get("FechaHoraEmision") if datos is not None else ""

# #                 # Extraer productos
# #                 for item in root.findall(".//dte:Item", ns):
# #                     descripcion = item.findtext("dte:Descripcion", default="", namespaces=ns)
# #                     cantidad = item.findtext("dte:Cantidad", default="", namespaces=ns)
# #                     unidad = item.findtext("dte:UnidadMedida", default="", namespaces=ns)
# #                     precio_unit = item.findtext("dte:PrecioUnitario", default="", namespaces=ns)
# #                     total = item.findtext("dte:Total", default="", namespaces=ns)

# #                     rows.append({
# #                         "Archivo": file_name,
# #                         "Fecha": fecha,
# #                         "Empresa": empresa,
# #                         "NIT Emisor": nit_emisor,
# #                         "Cliente": cliente,
# #                         "Descripción": descripcion,
# #                         "Cantidad": float(cantidad) if cantidad else 0,
# #                         "Unidad": unidad,
# #                         "Precio Unitario": float(precio_unit) if precio_unit else 0,
# #                         "Total": float(total) if total else 0
# #                     })

# #     # Crear DataFrame
# #     df = pd.DataFrame(rows)
# #     return df

# # # === USO ===
# # df_productos = extraer_productos_de_zip(zip_path)

# # # Mostrar los primeros registros
# # print(df_productos.head())

# # # Guardar a CSV
# # df_productos.to_csv("productos_facturas.csv", index=False, delimiter=";")


# """
# extraer_productos_dte_zip.py
# Lee un .zip con muchos XML (DTE guatemaltecos) y devuelve un DataFrame con
# todos los productos y metadatos solicitados.
# """

# import zipfile
# import xml.etree.ElementTree as ET
# import pandas as pd
# from typing import Optional

# # --- Ajusta esta ruta al nombre de tu zip ---
# ZIP_PATH = r"C:\Users\alex0\Downloads\consulta (5).zip"

# # --- Namespaces usados en los XML DTE ---
# NS = {
#     "dte": "http://www.sat.gob.gt/dte/fel/0.2.0"
# }

# def safe_text(parent: Optional[ET.Element], tag: str, ns=NS) -> str:
#     """Devuelve el texto del tag (con namespace) o cadena vacía si no existe."""
#     if parent is None:
#         return ""
#     el = parent.find(tag, ns)
#     return (el.text or "").strip() if el is not None and el.text is not None else ""

# def format_address(addr_elem: Optional[ET.Element], ns=NS) -> str:
#     """Construye una dirección legible a partir de DireccionEmisor/DireccionReceptor."""
#     if addr_elem is None:
#         return ""
#     parts = []
#     for t in ("Direccion", "Municipio", "Departamento", "CodigoPostal", "Pais"):
#         v = safe_text(addr_elem, f"dte:{t}", ns)
#         if v:
#             parts.append(v)
#     return ", ".join(parts)

# def to_float_safe(value: str) -> float:
#     """Convierte a float manejando cadenas vacías o comas como separador decimal."""
#     if value is None:
#         return 0.0
#     s = str(value).strip()
#     if s == "":
#         return 0.0
#     s = s.replace(",", ".")
#     try:
#         return float(s)
#     except Exception:
#         return 0.0

# def parse_xml_tree(root: ET.Element, file_name: str):
#     """Extrae filas (una por item) desde un XML (ElementTree root)."""
#     rows = []

#     # Emisor / Receptor / DatosGenerales
#     emisor = root.find(".//dte:Emisor", NS)
#     receptor = root.find(".//dte:Receptor", NS)
#     datos_generales = root.find(".//dte:DatosGenerales", NS)
#     certificacion = root.find(".//dte:Certificacion", NS)
#     numero_aut = root.find(".//dte:Certificacion/dte:NumeroAutorizacion", NS)
#     dte_elem = root.find(".//dte:DTE", NS)

#     # Emisor datos
#     nombre_emisor = emisor.attrib.get("NombreEmisor") if emisor is not None else ""
#     nombre_comercial = emisor.attrib.get("NombreComercial") if emisor is not None else nombre_emisor
#     nit_emisor = emisor.attrib.get("NITEmisor") if emisor is not None else ""
#     codigo_establecimiento = emisor.attrib.get("CodigoEstablecimiento") if emisor is not None else ""

#     direccion_emisor = format_address(root.find(".//dte:DireccionEmisor", NS), NS)

#     # Receptor datos
#     nombre_receptor = receptor.attrib.get("NombreReceptor") if receptor is not None else ""
#     nit_receptor = receptor.attrib.get("IDReceptor") if receptor is not None else ""  # en DTE GT suele ir en IDReceptor
#     direccion_receptor = format_address(root.find(".//dte:DireccionReceptor", NS), NS)

#     # Datos Generales
#     tipo_documento = datos_generales.attrib.get("Tipo") if datos_generales is not None else ""
#     fecha_emision = datos_generales.attrib.get("FechaHoraEmision") if datos_generales is not None else ""
#     codigo_moneda = datos_generales.attrib.get("CodigoMoneda") if datos_generales is not None else ""

#     # Certificacion / NumeroAutorizacion
#     numaut_serie = numero_aut.attrib.get("Serie") if numero_aut is not None else ""
#     numaut_numero = numero_aut.attrib.get("Numero") if numero_aut is not None else ""
#     numaut_text = (numero_aut.text or "").strip() if numero_aut is not None and numero_aut.text else ""
#     fecha_certificacion = safe_text(certificacion, "dte:FechaHoraCertificacion", NS) if certificacion is not None else ""
#     nit_certificador = safe_text(certificacion, "dte:NITCertificador", NS) if certificacion is not None else ""
#     nombre_certificador = safe_text(certificacion, "dte:NombreCertificador", NS) if certificacion is not None else ""

#     dte_id = dte_elem.attrib.get("ID") if dte_elem is not None else ""

#     # Recorremos cada Item
#     for item in root.findall(".//dte:Item", NS):
#         numero_linea = item.attrib.get("NumeroLinea", "")
#         bien_o_servicio = item.attrib.get("BienOServicio", "")  # 'B' o 'S'
#         # transformar en algo legible
#         if bien_o_servicio == "B":
#             bof = "Bien"
#         elif bien_o_servicio == "S":
#             bof = "Servicio"
#         else:
#             bof = bien_o_servicio

#         cantidad = safe_text(item, "dte:Cantidad", NS)
#         unidad = safe_text(item, "dte:UnidadMedida", NS)
#         descripcion = safe_text(item, "dte:Descripcion", NS)
#         precio_unitario = safe_text(item, "dte:PrecioUnitario", NS)
#         precio = safe_text(item, "dte:Precio", NS)  # precio (cantidad * precio_unitario usual)
#         descuento = safe_text(item, "dte:Descuento", NS)
#         total = safe_text(item, "dte:Total", NS)

#         # Impuestos por item (agregamos como cadena JSON-like si existen)
#         impuestos_list = []
#         for imp in item.findall(".//dte:Impuesto", NS):
#             nombre = safe_text(imp, "dte:NombreCorto", NS)
#             monto_gravable = safe_text(imp, "dte:MontoGravable", NS)
#             monto_impuesto = safe_text(imp, "dte:MontoImpuesto", NS)
#             impuestos_list.append({
#                 "nombre": nombre,
#                 "monto_gravable": monto_gravable,
#                 "monto_impuesto": monto_impuesto
#             })

#         rows.append({
#             # metadatos del archivo/registro
#             "Archivo": file_name,
#             "DTE_ID": dte_id,
#             "TipoDocumento": tipo_documento,
#             "FechaHoraEmision": fecha_emision,
#             "CodigoMoneda": codigo_moneda,
#             # emisor
#             "NombreEmisor": nombre_emisor,
#             "NombreComercial": nombre_comercial,
#             "NIT_Emisor": nit_emisor,
#             "CodigoEstablecimiento": codigo_establecimiento,
#             "DireccionEmisor": direccion_emisor,
#             # receptor
#             "NombreReceptor": nombre_receptor,
#             "NIT_Receptor": nit_receptor,
#             "DireccionReceptor": direccion_receptor,
#             # certificacion / autorizacion
#             "NumeroAutorizacion_Serie": numaut_serie,
#             "NumeroAutorizacion_Numero": numaut_numero,
#             "NumeroAutorizacion_Texto": numaut_text,
#             "FechaHoraCertificacion": fecha_certificacion,
#             "NIT_Certificador": nit_certificador,
#             "Nombre_Certificador": nombre_certificador,
#             # item / producto
#             "Linea_Numero": numero_linea,
#             "BienOServicio": bof,
#             "Descripcion": descripcion,
#             "Cantidad": to_float_safe(cantidad),
#             "UnidadMedida": unidad,
#             "PrecioUnitario": to_float_safe(precio_unitario),
#             "Precio": to_float_safe(precio),
#             "Descuento": to_float_safe(descuento),
#             "Total": to_float_safe(total),
#             # impuestos (si existen) - lo guardamos como lista (puedes serializar si prefieres string)
#             "Impuestos": impuestos_list
#         })

#     return rows

# def extraer_productos_de_zip(zip_path: str) -> pd.DataFrame:
#     """Abre el ZIP, procesa todos los XML y devuelve un DataFrame con todas las filas."""
#     all_rows = []
#     with zipfile.ZipFile(zip_path, "r") as z:
#         for member in z.namelist():
#             # saltar directorios y archivos no-xml
#             if member.endswith('/') or not member.lower().endswith(".xml"):
#                 continue
#             try:
#                 with z.open(member) as f:
#                     tree = ET.parse(f)
#                     root = tree.getroot()
#                     rows = parse_xml_tree(root, member)
#                     all_rows.extend(rows)
#             except Exception as e:
#                 # Si quieres, puedes loggear o recolectar errores en una lista para revisar después.
#                 print(f"ERROR procesando {member}: {e}")

#     df = pd.DataFrame(all_rows)
#     # si quieres serializar la columna 'Impuestos' a JSON-string:
#     if "Impuestos" in df.columns:
#         df["Impuestos"] = df["Impuestos"].apply(lambda x: (pd.io.json.dumps(x) if x else "[]") if not pd.isna(x) else "[]")

#     return df

# # # -------------------------
# # # EJEMPLO DE USO
# # # -------------------------


# # df = extraer_productos_de_zip(ZIP_PATH)


# #     # Guardar a CSV y a Excel
# # df.to_csv("productos_todos_v2.csv", index=False, encoding="utf-8", sep=";")

    


"""
xml_processor.py
Procesa archivos ZIP con XMLs de DTE guatemaltecos y los convierte a DataFrame
"""

import zipfile
import xml.etree.ElementTree as ET
import pandas as pd
from typing import Optional

# --- Namespaces usados en los XML DTE ---
NS = {
    "dte": "http://www.sat.gob.gt/dte/fel/0.2.0"
}

def safe_text(parent: Optional[ET.Element], tag: str, ns=NS) -> str:
    """Devuelve el texto del tag (con namespace) o cadena vacía si no existe."""
    if parent is None:
        return ""
    el = parent.find(tag, ns)
    return (el.text or "").strip() if el is not None and el.text is not None else ""

def format_address(addr_elem: Optional[ET.Element], ns=NS) -> str:
    """Construye una dirección legible a partir de DireccionEmisor/DireccionReceptor."""
    if addr_elem is None:
        return ""
    parts = []
    for t in ("Direccion", "Municipio", "Departamento", "CodigoPostal", "Pais"):
        v = safe_text(addr_elem, f"dte:{t}", ns)
        if v:
            parts.append(v)
    return ", ".join(parts)

def to_float_safe(value: str) -> float:
    """Convierte a float manejando cadenas vacías o comas como separador decimal."""
    if value is None:
        return 0.0
    s = str(value).strip()
    if s == "":
        return 0.0
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0

def parse_xml_tree(root: ET.Element, file_name: str):
    """Extrae filas (una por item) desde un XML (ElementTree root)."""
    rows = []

    # Emisor / Receptor / DatosGenerales
    emisor = root.find(".//dte:Emisor", NS)
    receptor = root.find(".//dte:Receptor", NS)
    datos_generales = root.find(".//dte:DatosGenerales", NS)
    certificacion = root.find(".//dte:Certificacion", NS)
    numero_aut = root.find(".//dte:Certificacion/dte:NumeroAutorizacion", NS)
    dte_elem = root.find(".//dte:DTE", NS)

    # Emisor datos
    nombre_emisor = emisor.attrib.get("NombreEmisor") if emisor is not None else ""
    nombre_comercial = emisor.attrib.get("NombreComercial") if emisor is not None else nombre_emisor
    nit_emisor = emisor.attrib.get("NITEmisor") if emisor is not None else ""
    codigo_establecimiento = emisor.attrib.get("CodigoEstablecimiento") if emisor is not None else ""

    direccion_emisor = format_address(root.find(".//dte:DireccionEmisor", NS), NS)

    # Receptor datos
    nombre_receptor = receptor.attrib.get("NombreReceptor") if receptor is not None else ""
    nit_receptor = receptor.attrib.get("IDReceptor") if receptor is not None else ""
    direccion_receptor = format_address(root.find(".//dte:DireccionReceptor", NS), NS)

    # Datos Generales
    tipo_documento = datos_generales.attrib.get("Tipo") if datos_generales is not None else ""
    fecha_emision = datos_generales.attrib.get("FechaHoraEmision") if datos_generales is not None else ""
    codigo_moneda = datos_generales.attrib.get("CodigoMoneda") if datos_generales is not None else ""

    # Certificacion / NumeroAutorizacion
    numaut_serie = numero_aut.attrib.get("Serie") if numero_aut is not None else ""
    numaut_numero = numero_aut.attrib.get("Numero") if numero_aut is not None else ""
    numaut_text = (numero_aut.text or "").strip() if numero_aut is not None and numero_aut.text else ""
    fecha_certificacion = safe_text(certificacion, "dte:FechaHoraCertificacion", NS) if certificacion is not None else ""
    nit_certificador = safe_text(certificacion, "dte:NITCertificador", NS) if certificacion is not None else ""
    nombre_certificador = safe_text(certificacion, "dte:NombreCertificador", NS) if certificacion is not None else ""

    dte_id = dte_elem.attrib.get("ID") if dte_elem is not None else ""

    # Recorremos cada Item
    for item in root.findall(".//dte:Item", NS):
        numero_linea = item.attrib.get("NumeroLinea", "")
        bien_o_servicio = item.attrib.get("BienOServicio", "")
        
        if bien_o_servicio == "B":
            bof = "Bien"
        elif bien_o_servicio == "S":
            bof = "Servicio"
        else:
            bof = bien_o_servicio

        cantidad = safe_text(item, "dte:Cantidad", NS)
        unidad = safe_text(item, "dte:UnidadMedida", NS)
        descripcion = safe_text(item, "dte:Descripcion", NS)
        precio_unitario = safe_text(item, "dte:PrecioUnitario", NS)
        precio = safe_text(item, "dte:Precio", NS)
        descuento = safe_text(item, "dte:Descuento", NS)
        total = safe_text(item, "dte:Total", NS)

        # Impuestos por item
        impuestos_list = []
        for imp in item.findall(".//dte:Impuesto", NS):
            nombre = safe_text(imp, "dte:NombreCorto", NS)
            monto_gravable = safe_text(imp, "dte:MontoGravable", NS)
            monto_impuesto = safe_text(imp, "dte:MontoImpuesto", NS)
            impuestos_list.append({
                "nombre": nombre,
                "monto_gravable": monto_gravable,
                "monto_impuesto": monto_impuesto
            })

        rows.append({
            "Archivo": file_name,
            "DTE_ID": dte_id,
            "TipoDocumento": tipo_documento,
            "FechaHoraEmision": fecha_emision,
            "CodigoMoneda": codigo_moneda,
            "NombreEmisor": nombre_emisor,
            "NombreComercial": nombre_comercial,
            "NIT_Emisor": nit_emisor,
            "CodigoEstablecimiento": codigo_establecimiento,
            "DireccionEmisor": direccion_emisor,
            "NombreReceptor": nombre_receptor,
            "NIT_Receptor": nit_receptor,
            "DireccionReceptor": direccion_receptor,
            "NumeroAutorizacion_Serie": numaut_serie,
            "NumeroAutorizacion_Numero": numaut_numero,
            "NumeroAutorizacion_Texto": numaut_text,
            "FechaHoraCertificacion": fecha_certificacion,
            "NIT_Certificador": nit_certificador,
            "Nombre_Certificador": nombre_certificador,
            "Linea_Numero": numero_linea,
            "BienOServicio": bof,
            "Descripcion": descripcion,
            "Cantidad": to_float_safe(cantidad),
            "UnidadMedida": unidad,
            "PrecioUnitario": to_float_safe(precio_unitario),
            "Precio": to_float_safe(precio),
            "Descuento": to_float_safe(descuento),
            "Total": to_float_safe(total),
            "Impuestos": impuestos_list
        })

    return rows

def extraer_productos_de_zip(zip_path: str) -> pd.DataFrame:
    """
    Abre el ZIP, procesa todos los XML y devuelve un DataFrame con todas las filas.
    
    Args:
        zip_path: Ruta al archivo ZIP
        
    Returns:
        DataFrame con todos los registros procesados
    """
    all_rows = []
    errores = []
    
    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.namelist():
            if member.endswith('/') or not member.lower().endswith(".xml"):
                continue
            try:
                with z.open(member) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    rows = parse_xml_tree(root, member)
                    all_rows.extend(rows)
            except Exception as e:
                errores.append(f"Error en {member}: {str(e)}")
                print(f"ERROR procesando {member}: {e}")

    df = pd.DataFrame(all_rows)
    
    # Serializar columna Impuestos a JSON
    if "Impuestos" in df.columns and len(df) > 0:
        df["Impuestos"] = df["Impuestos"].apply(
            lambda x: pd.io.json.dumps(x) if x else "[]"
        )

    return df, errores