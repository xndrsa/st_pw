import asyncio
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from datetime import datetime
from typing import Optional
import os

class SATNavigator:
    """
    Clase para navegar e interactuar con el sistema SAT de Guatemala
    """
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.current_data = {}
        
    async def iniciar(self, headless: bool = False):
        """
        Inicia el navegador y prepara todo para la navegación
        
        Args:
            headless: Si True, ejecuta sin interfaz gráfica
        """
        print("🚀 Iniciando navegador...")
        
        self.playwright = await async_playwright().start()
        # self.browser = await self.playwright.chromium.launch(
        #     headless=headless,
        #     args=['--disable-blink-features=AutomationControlled']
        # )
        self.browser = await self.playwright.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled"
            ]
        )

        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        self.page = await self.context.new_page()
        
        # Configurar listeners para debugging
        self.page.on('console', lambda msg: print(f"📢 Console: {msg.text}"))
        self.page.on('pageerror', lambda err: print(f"❌ Error en página: {err}"))
        
        print("✅ Navegador iniciado correctamente")


    async def ir_a_login(self):
        """
        Navega a la página de login del SAT
        """
        print("🔄 Navegando a la página de login...")
        
        await self.page.goto(
            'https://farm3.sat.gob.gt/menu/login.jsf',
            wait_until='networkidle',
            timeout=30000
        )
        
        await self.page.wait_for_timeout(2000)
        print("✅ Página de login cargada")
        

    async def interactuar_con_dropdown_material(self, dropdown_id: str = None, nombre: str = None):
        """
        Abre un dropdown Material Design y permite seleccionar una opción
        
        Args:
            dropdown_id: ID del mat-select (ej: 'mat-select-0')
            nombre: Name del dropdown (ej: 'tipoOperacion')
        """
        print(f"\n📋 INTERACTUANDO CON DROPDOWN MATERIAL")
        print("-"*40)
        
        # Encontrar el dropdown
        selector = None
        if dropdown_id:
            selector = f"#{dropdown_id}"
        elif nombre:
            selector = f"mat-select[name='{nombre}']"
        else:
            print("❌ Debes proporcionar dropdown_id o nombre")
            return None
        
        try:
            # Hacer click en el dropdown para abrirlo
            dropdown = await self.page.wait_for_selector(selector, timeout=5000)
            
            if not dropdown:
                print(f"❌ No se encontró el dropdown: {selector}")
                return None
            
            print(f"✅ Dropdown encontrado: {selector}")
            
            # Click para abrir
            await dropdown.click()
            await asyncio.sleep(0.5)
            
            print("✅ Dropdown abierto")
            
            # Esperar a que aparezcan las opciones
            await self.page.wait_for_selector('mat-option', timeout=3000)
            
            # Obtener todas las opciones
            opciones = await self.page.query_selector_all('mat-option')
            
            if not opciones:
                print("❌ No se encontraron opciones")
                return None
            
            print(f"\n📝 OPCIONES DISPONIBLES ({len(opciones)}):")
            print("-"*40)
            
            opciones_data = []
            for i, opcion in enumerate(opciones):
                texto = await opcion.text_content()
                value = await opcion.get_attribute('value')
                
                if texto and texto.strip():
                    opciones_data.append({
                        'index': i,
                        'text': texto.strip(),
                        'value': value,
                        'element': opcion
                    })
                    print(f"  [{i}] {texto.strip()}")
            
            return opciones_data
            
        except Exception as e:
            print(f"❌ Error al interactuar con dropdown: {str(e)}")
            return None



    async def seleccionar_opcion_dropdown_material(self, opciones_data: list, indice: int = None, texto: str = None):
        """
        Selecciona una opción de un dropdown Material Design ya abierto
        
        Args:
            opciones_data: Lista de opciones obtenida de interactuar_con_dropdown_material
            indice: Índice de la opción a seleccionar
            texto: Texto de la opción a seleccionar
        """
        print(f"\n✅ SELECCIONANDO OPCIÓN")
        print("-"*40)
        
        if not opciones_data:
            print("❌ No hay opciones disponibles")
            return False
        
        opcion_seleccionada = None
        
        if indice is not None:
            if 0 <= indice < len(opciones_data):
                opcion_seleccionada = opciones_data[indice]
            else:
                print(f"❌ Índice {indice} fuera de rango (0-{len(opciones_data)-1})")
                return False
        
        elif texto:
            for opcion in opciones_data:
                if texto.lower() in opcion['text'].lower():
                    opcion_seleccionada = opcion
                    break
            
            if not opcion_seleccionada:
                print(f"❌ No se encontró opción con texto: {texto}")
                return False
        
        else:
            print("❌ Debes proporcionar índice o texto")
            return False
        
        try:
            # Hacer click en la opción
            await opcion_seleccionada['element'].click()
            await asyncio.sleep(0.3)
            
            print(f"✅ Opción seleccionada: {opcion_seleccionada['text']}")
            return True
            
        except Exception as e:
            print(f"❌ Error al seleccionar opción: {str(e)}")
            return False


    


    async def _obtener_pagina_principal(self):
        """
        Obtiene la página principal, incluso si estamos en un iframe
        """
        # Si self.page es un Frame (iframe), obtener la página padre
        if hasattr(self.page, 'page'):
            # Es un Frame, obtener la página principal
            return self.page.page
        elif hasattr(self, 'context') and self.context.pages:
            # Obtener la primera página del contexto
            return self.context.pages[0]
        else:
            # Asumir que ya es la página principal
            return self.page


    async def descargar_reporte(self, tipo: str = "excel"):
        """
        Descarga el reporte en el formato especificado
        """
        print(f"\n📥 DESCARGANDO REPORTE: {tipo.upper()}")
        print("-"*40)
        
        selectores_por_tipo = {
            'xml': ['fa.xml', '.xml', 'i.fa-file-code-o', '[class*="xml"]'],
            'excel': ['fa.excel', '.excel', 'i.fa-file-excel-o', '[class*="excel"]'],
            'pdf': ['fa.pdf', '.pdf', 'i.fa-file-pdf-o', '[class*="pdf"]']
        }
        
        selectores = selectores_por_tipo.get(tipo.lower())
        
        if not selectores:
            print(f"❌ Tipo '{tipo}' no válido. Use: xml, excel, pdf")
            return None
        
        contenedor_descarga = await self.page.query_selector('.iconDownload')
        
        if not contenedor_descarga:
            print("❌ No se encontró el contenedor de descargas")
            return None
        
        print("✅ Contenedor de descargas encontrado")
        
        elemento_descarga = None
        for selector in selectores:
            try:
                elemento = await contenedor_descarga.query_selector(selector)
                if elemento and await elemento.is_visible():
                    elemento_descarga = elemento
                    print(f"✅ Elemento de descarga {tipo.upper()} encontrado: {selector}")
                    break
            except:
                continue
        
        if not elemento_descarga:
            print(f"❌ No se encontró el botón de descarga para {tipo.upper()}")
            return None
        
        try:
            # Obtener página principal automáticamente
            main_page = await self._obtener_pagina_principal()
            
            print(f"⏳ Iniciando descarga de {tipo.upper()}...")
            
            async with main_page.expect_download(timeout=600000) as download_info:
                await elemento_descarga.click()
                print(f"✅ Click en botón de descarga {tipo.upper()}")
            
            download = await download_info.value
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suggested_name = download.suggested_filename
            filename = f"reporte_sat_{tipo}_{timestamp}_{suggested_name}"
            
            await download.save_as(filename)
            
            print(f"\n✅ DESCARGA EXITOSA")
            print(f"   📁 Archivo: {filename}")
            print(f"   📊 Tamaño: {os.path.getsize(filename):,} bytes")
            
            return filename
            
        except Exception as e:
            print(f"❌ Error durante la descarga: {str(e)}")
            return None


    async def hacer_login(self, usuario: str, password: str):
        """
        Realiza el login en el sistema SAT
        
        Args:
            usuario: Nombre de usuario o NIT
            password: Contraseña
        """
        # limpiar usuario, quitar todo lo que no sea número
        usuario = ''.join(filter(str.isdigit, usuario))
        self.usuario = usuario # Guardar usuario para renombrar archivos luego
        print(f"\n🔐 INTENTANDO LOGIN...")
        print(f"   Usuario: {usuario}")
        print(f"   Password: {'*' * len(password)}")
        
        try:
            # Buscar campos de usuario (puede ser NIT, usuario, etc.)
            user_selectors = [
                'input[type="text"]:visible',
                'input[name*="user"]',
                'input[name*="nit"]',
                'input[id*="user"]',
                'input[id*="nit"]',
                'input[placeholder*="NIT"]',
                'input[placeholder*="Usuario"]'
            ]
            
            user_field = None
            for selector in user_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=1000)
                    if element and await element.is_visible():
                        user_field = element
                        print(f"   ✓ Campo de usuario encontrado: {selector}")
                        break
                except:
                    continue
            
            if not user_field:
                # Buscar el primer input visible de tipo text
                user_field = await self.page.query_selector('input[type="text"]:visible')
            
            # Buscar campo de password
            pass_field = await self.page.wait_for_selector('input[type="password"]', timeout=5000)
            print("   ✓ Campo de contraseña encontrado")
            
            # Llenar los campos
            await user_field.fill(usuario)
            await asyncio.sleep(0.5)
            
            await pass_field.fill(password)
            await asyncio.sleep(0.5)
            
            print("   ✓ Credenciales ingresadas")
            
            # Buscar y hacer clic en el botón de login
            login_button = None
            button_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Entrar")',
                'button:has-text("Ingresar")',
                'button:has-text("Login")',
                'input[value="Entrar"]',
                'input[value="Ingresar"]'
            ]
            
            for selector in button_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        login_button = element
                        print(f"   ✓ Botón de login encontrado: {selector}")
                        break
                except:
                    continue
            
            if login_button:
                await login_button.click()
                print("   ✓ Botón de login clickeado")
                
                # Esperar a que la página cargue
                print("   ⏳ Esperando respuesta del servidor...")
                await self.page.wait_for_load_state('networkidle', timeout=10000)
                
                # Verificar si el login fue exitoso
                await asyncio.sleep(2)
                new_url = self.page.url
                
                if 'login' not in new_url.lower():
                    print("   ✅ LOGIN EXITOSO - Redirigido a nueva página")
                    print(f"   📍 Nueva URL: {new_url}")
                else:
                    print("   ⚠️ Posible error en login - Verificar manualmente")
                    
            else:
                print("   ❌ No se encontró el botón de login")
                
        except Exception as e:
            print(f"   ❌ Error durante el login: {str(e)}")
            raise
    

    
    async def click_opcion_menu(self, texto: str = None, indice: int = None):
        """
        Hace clic en una opción del menú por texto o índice
        
        Args:
            texto: Texto de la opción a clickear
            indice: Índice de la opción a clickear
        """
        if texto:
            selector = f'a:has-text("{texto}"), button:has-text("{texto}")'
            element = await self.page.query_selector(selector)
            if element:
                await element.click()
                print(f"   ✓ Opción '{texto}' clickeada")
                await self.page.wait_for_load_state('networkidle', timeout=10000)
                return True
        
        elif indice is not None:
            menu_items = await self.page.query_selector_all('a[role="menuitem"], .menu-item a, .nav-item a, li a')
            visible_items = []
            for item in menu_items:
                if await item.is_visible():
                    visible_items.append(item)
            
            if indice < len(visible_items):
                await visible_items[indice].click()
                text = await visible_items[indice].text_content()
                print(f"   ✓ Opción [{indice}] '{text.strip()}' clickeada")
                await self.page.wait_for_load_state('networkidle', timeout=10000)
                return True
        
        print("   ❌ No se pudo clickear la opción especificada")
        return False
    

    async def marcar_checkbox_header_tabla(self, marcar: bool = True):
        """
        Marca/desmarca el checkbox del header de la tabla (el que selecciona todos)
        
        Args:
            marcar: True para marcar, False para desmarcar
        """
        print(f"\n☑️ {'MARCANDO' if marcar else 'DESMARCANDO'} CHECKBOX DEL HEADER")
        print("-" * 40)
        
        try:
            # Buscar el checkbox en el header de la tabla
            header_checkbox = await self.page.query_selector('mat-header-row input[type="checkbox"], thead input[type="checkbox"]')
            
            if not header_checkbox:
                print("❌ No se encontró checkbox en el header")
                return False
            
            checkbox_id = await header_checkbox.get_attribute('id')
            print(f"✅ Checkbox del header encontrado: {checkbox_id}")
            
            # Verificar estado actual
            is_checked = await header_checkbox.is_checked()
            
            if is_checked == marcar:
                print(f"   ℹ️ El checkbox del header ya está {'marcado' if marcar else 'desmarcado'}")
                return True
            
            # Usar JavaScript para hacer click
            await self.page.evaluate('''(element) => {
                element.click();
                const event = new Event('change', { bubbles: true });
                element.dispatchEvent(event);
            }''', header_checkbox)
            
            await asyncio.sleep(0.5)  # Esperar a que se propaguen los cambios
            
            print(f"   ✅ Checkbox del header {'marcado' if marcar else 'desmarcado'} exitosamente")
            print(f"   ℹ️ Esto debería {'seleccionar' if marcar else 'deseleccionar'} todos los registros de la tabla")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return False


    async def click_elemento_personalizado(self, identificador: str):
        """
        Hace click en un elemento usando diferentes estrategias de búsqueda
        
        Args:
            identificador: Puede ser un ID, texto, clase o selector CSS
        """
        print(f"\n🎯 BUSCANDO ELEMENTO: {identificador}")
        print("-" * 40)
        
        estrategias = [
            # Por ID exacto
            (f"#{identificador}", "ID exacto"),
            # Por ID que contiene el texto
            (f"[id*='{identificador}']", "ID parcial"),
            # Por texto exacto
            (f"text={identificador}", "Texto exacto"),
            # Por texto que contiene
            (f":has-text('{identificador}')", "Contiene texto"),
            # Por name
            (f"[name='{identificador}']", "Name"),
            # Por clase
            (f".{identificador}", "Clase"),
            # Por value (para inputs y buttons)
            (f"[value='{identificador}']", "Value"),
            # Botón con ese ID o texto
            (f"button#{identificador}, button:has-text('{identificador}')", "Botón"),
            # Link con ese texto
            (f"a:has-text('{identificador}')", "Enlace"),
            # Cualquier elemento clickeable con ese texto
            (f"*:has-text('{identificador}'):visible", "Elemento con texto visible")
        ]
        
        elemento_encontrado = None
        estrategia_exitosa = None
        
        for selector, descripcion in estrategias:
            try:
                # Intentar encontrar el elemento
                elemento = await self.page.query_selector(selector)
                
                if elemento and await elemento.is_visible():
                    elemento_encontrado = elemento
                    estrategia_exitosa = descripcion
                    print(f"   ✅ Elemento encontrado usando: {descripcion}")
                    print(f"   📍 Selector: {selector}")
                    
                    # Obtener más información del elemento
                    tag_name = await elemento.evaluate("el => el.tagName")
                    element_id = await elemento.get_attribute('id')
                    element_class = await elemento.get_attribute('class')
                    element_text = await elemento.text_content()
                    
                    print(f"   📋 Detalles del elemento:")
                    print(f"      • Tag: {tag_name}")
                    if element_id:
                        print(f"      • ID: {element_id}")
                    if element_class:
                        print(f"      • Clase: {element_class}")
                    if element_text and element_text.strip():
                        print(f"      • Texto: {element_text.strip()[:50]}")
                    
                    break
                    
            except Exception as e:
                continue
        
        if elemento_encontrado:
            try:
                # Hacer scroll al elemento si es necesario
                await elemento_encontrado.scroll_into_view_if_needed()
                
                # Intentar hacer click
                await elemento_encontrado.click()
                print(f"\n   🎯 ¡CLICK EXITOSO!")
                
                # Esperar un momento para que la página responda
                await asyncio.sleep(1)
                
                # Verificar si la página cambió
                await self.page.wait_for_load_state('domcontentloaded', timeout=5000)
                
                new_url = self.page.url
                print(f"   📍 URL actual: {new_url}")
                
                return True
                
            except Exception as e:
                print(f"   ⚠️ El elemento fue encontrado pero no se pudo hacer click: {str(e)}")
                
                # Intentar con JavaScript como alternativa
                try:
                    print("   🔄 Intentando click con JavaScript...")
                    await self.page.evaluate("el => el.click()", elemento_encontrado)
                    print(f"   ✅ Click con JavaScript exitoso")
                    return True
                except:
                    print(f"   ❌ No se pudo hacer click ni con JavaScript")
                    return False
        else:
            print(f"   ❌ No se encontró ningún elemento con: '{identificador}'")
            print(f"\n   💡 Sugerencias:")
            print(f"      • Verifica que el ID/texto sea exacto")
            print(f"      • Usa 'Analizar página' para ver los elementos disponibles")
            print(f"      • Prueba con parte del texto o ID")
            return False
    

    async def esperar_elemento_con_retry(
        self,
        identificador: str,
        max_intentos: int = 3,
        timeout: int = 5000,
        hacer_refresh: bool = True
    ):
        """
        Espera a que un elemento aparezca, con reintentos y refresh si es necesario
        
        Args:
            identificador: ID, texto o selector del elemento
            max_intentos: Número de reintentos
            timeout: Timeout por intento en ms
            hacer_refresh: Si hacer refresh entre intentos
        
        Returns:
            El elemento encontrado o None
        """
        estrategias = [
            (f"#{identificador}", "ID exacto"),
            (f"[id*='{identificador}']", "ID parcial"),
            (f"text={identificador}", "Texto exacto"),
            (f":has-text('{identificador}')", "Contiene texto"),
            (f"button#{identificador}, button:has-text('{identificador}')", "Botón"),
        ]
        
        for intento in range(1, max_intentos + 1):
            print(f"   🔄 Intento {intento}/{max_intentos} de encontrar: {identificador}")
            
            # Intentar todas las estrategias
            for selector, descripcion in estrategias:
                try:
                    elemento = await self.page.wait_for_selector(
                        selector, 
                        timeout=timeout,
                        state='visible'
                    )
                    
                    if elemento:
                        print(f"   ✅ Elemento encontrado con: {descripcion}")
                        return elemento
                        
                except:
                    continue
            
            # Si no se encontró y no es el último intento
            if intento < max_intentos:
                if hacer_refresh:
                    print(f"   ⚠️ Elemento no encontrado, haciendo refresh...")
                    await self.page.reload(wait_until='networkidle', timeout=30000)
                    await asyncio.sleep(1)
                else:
                    print(f"   ⚠️ Esperando antes de reintentar...")
                    await asyncio.sleep(1)
        
        print(f"   ❌ Elemento '{identificador}' no encontrado después de {max_intentos} intentos")
        return None


    async def click_elemento_con_retry(
        self,
        identificador: str,
        max_intentos: int = 3,
        hacer_refresh: bool = True
    ):
        """
        Hace click en un elemento con reintentos y manejo de página en blanco
        """
        print(f"\n🎯 CLICK CON RETRY: {identificador}")
        print("-" * 40)
        
        elemento = await self.esperar_elemento_con_retry(
            identificador,
            max_intentos=max_intentos,
            hacer_refresh=hacer_refresh
        )
        
        if not elemento:
            raise Exception(f"No se pudo encontrar elemento: {identificador}")
        
        try:
            # Scroll al elemento
            await elemento.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            
            # Intentar click normal
            await elemento.click()
            print(f"   ✅ Click exitoso")
            
            # Esperar a que la página responda
            await asyncio.sleep(0.5)
            
            return True
            
        except Exception as e:
            print(f"   ⚠️ Click normal falló, intentando con JavaScript...")
            
            try:
                await self.page.evaluate("el => el.click()", elemento)
                print(f"   ✅ Click con JavaScript exitoso")
                return True
            except:
                raise Exception(f"No se pudo hacer click en: {identificador}")


    async def verificar_pagina_cargada(self, max_intentos: int = 3):
        """
        Verifica que la página no esté en blanco y la recarga si es necesario
        """
        for intento in range(max_intentos):
            try:
                # Verificar si hay contenido visible
                body_content = await self.page.evaluate(
                    "() => document.body ? document.body.innerText.trim().length : 0"
                )
                print(f"   ℹ️ Contenido de la página: {body_content} caracteres")
                print(body_content)
                
                if body_content > 80:  # Si hay más de 100 caracteres, probablemente está bien
                    return True
                
                print(f"   ⚠️ Página parece estar en blanco (intento {intento + 1}/{max_intentos})")
                
                if intento < max_intentos - 1:
                    print("   🔄 Recargando página...")
                    await self.page.reload(wait_until='networkidle', timeout=30000)
                    await asyncio.sleep(2)
            
            except Exception as e:
                print(f"   ❌ Error verificando página: {str(e)}")
                if intento < max_intentos - 1:
                    await asyncio.sleep(2)
        
        return False





    async def descargar_multiples_periodos(
        self,
        periodos: list,
        navegar_primera_vez: bool = True
    ):
        """Descarga múltiples períodos en la misma sesión"""
        
        print("\n" + "="*60)
        print(f"🚀 DESCARGANDO {len(periodos)} PERÍODOS EN MISMA SESIÓN")
        print("="*60)
        
        archivos_descargados = []
        
        for idx, periodo in enumerate(periodos, 1):
            print(f"\n📦 PERÍODO {idx}/{len(periodos)}")
            
            try:
                # Solo navegar en el primer período
                if idx == 1 and navegar_primera_vez:
                    print("\n🍔 NAVEGACIÓN INICIAL...")
                    
                    # Click en menú con retry
                    await self.click_elemento_con_retry('btnContraerMenu', max_intentos=3)
                    await asyncio.sleep(1)
                    
                    # Servicios Tributarios
                    await self.click_elemento_con_retry('Servicios Tributarios', max_intentos=2)
                    await asyncio.sleep(1.1)
                    
                    await self.click_elemento_con_retry('Servicios Tributarios', max_intentos=2)
                    await asyncio.sleep(1.1)
                    
                    # FEL
                    await self.click_elemento_con_retry(
                        'Factura Electrónica en Línea (FEL)', 
                        max_intentos=2
                    )
                    await asyncio.sleep(1.1)
                    
                    # Consultar DTE
                    await self.click_elemento_con_retry('Consultar DTE', max_intentos=2)
                    await asyncio.sleep(2)
                    
                    # Cambiar a iframe
                    print("\n🖼️ Cambiando a iframe...")
                    iframe_encontrado = False
                    for intento in range(3):
                        try:
                            await self.cambiar_a_iframe(identificador='iframeContent')
                            iframe_encontrado = True
                            print("   ✅ Iframe cargado")
                            break
                        except:
                            if intento < 2:
                                print(f"   ⚠️ Iframe no encontrado, refresh {intento+1}/3...")
                                # Volver a página principal y reintentar navegación
                                await self.page.goto(self.page.url)
                                await asyncio.sleep(2)
                            else:
                                raise Exception("No se pudo acceder al iframe después de 3 intentos")
                    
                    await asyncio.sleep(1)
                
                
                if idx > 1:
                    print(f"\n🧹 Limpiando formulario del período anterior...")
                    await self.click_elemento_con_retry('Limpiar', max_intentos=2, hacer_refresh=False)
                    await asyncio.sleep(1)
                
                # Actualizar fechas con verificación
                print(f"\n📝 Actualizando fechas del período {idx}...")
                
                # Verificar que los campos estén disponibles
                fecha_inicio_field = await self.esperar_elemento_con_retry(
                    'mat-input-7',
                    max_intentos=2,
                    hacer_refresh=False
                )

                if not fecha_inicio_field:
                    raise Exception("Campo fecha_inicio no disponible")
                
                await self.llenar_campo_texto('mat-input-7', periodo['fecha_inicio'])
                await asyncio.sleep(0.5)
                
                await self.llenar_campo_texto('mat-input-8', periodo['fecha_fin'])
                await asyncio.sleep(0.5)
                
                # Resto del flujo...
                tipos_a_descargar = []
                if periodo['tipo_operacion'] == "Ambos":
                    tipos_a_descargar = ["Emitidos", "Recibidos"]
                else:
                    tipos_a_descargar = [periodo['tipo_operacion']]
                
                for tipo_idx, tipo in enumerate(tipos_a_descargar, 1):
                    print(f"\n📦 Procesando: {tipo} ({tipo_idx}/{len(tipos_a_descargar)})")
                    
                    
                    print(f"🔄 Seleccion de tipo: {tipo}...")
                    opciones = await self.interactuar_con_dropdown_material(nombre='tipoOperacion')
                    if opciones:
                        await self.seleccionar_opcion_dropdown_material(opciones, texto=tipo)
                        await asyncio.sleep(0.5)
                    else:
                        print(f"⚠️ No se pudo cambiar a {tipo}, usando el actual")

                    # Buscar con retry
                    print(f"🔍 Buscando {tipo}...")
                    await self.click_elemento_con_retry('Buscar', max_intentos=2, hacer_refresh=False)
                    await asyncio.sleep(1)
                    
                    # Seleccionar todos
                    print(f"☑️ Seleccionando todos...")
                    await self.marcar_checkbox_header_tabla(marcar=True)
                    await asyncio.sleep(1)
                    
                    # Descargar
                    print(f"📥 Descargando {periodo['formato']}...")
                    archivo = await self.descargar_reporte(tipo=periodo['formato'])
                    #archivo = await self.descargar_reporte(tipo="xml")
                    
                    if archivo:
                        timestamp = datetime.now().strftime("%Y%m%d")
                        fi_str = periodo['fecha_inicio'].replace("/", "")
                        ff_str = periodo['fecha_fin'].replace("/", "")
                        
                        usuario = getattr(self, 'usuario', 'unknown')
                        extension = archivo.split('.')[-1]
                        nuevo_nombre = f"{usuario}_{tipo.lower()}_{fi_str}_{ff_str}.{extension}"
                        
                        try:
                            # Verificar que el archivo existe
                            if not os.path.exists(archivo):
                                print(f"⚠️ Archivo no encontrado: {archivo}")
                                archivos_descargados.append(archivo)
                                continue
                            
                            # Verificar que el nuevo nombre no existe ya
                            if os.path.exists(nuevo_nombre):
                                print(f"⚠️ Archivo destino ya existe: {nuevo_nombre}")
                                # Agregar timestamp para hacerlo único
                                ts = datetime.now().strftime("%H%M%S")
                                base, ext = os.path.splitext(nuevo_nombre)
                                nuevo_nombre = f"{base}_{ts}{ext}"
                                print(f"   → Renombrando a: {nuevo_nombre}")
                            
                            # Renombrar
                            os.rename(archivo, nuevo_nombre)
                            archivos_descargados.append(nuevo_nombre)
                            print(f"✅ Descargado: {nuevo_nombre}")
                            
                        except Exception as e:
                            # Mostrar el error específico
                            print(f"❌ Error al renombrar archivo: {str(e)}")
                            print(f"   Archivo original: {archivo}")
                            print(f"   Nuevo nombre intentado: {nuevo_nombre}")
                            # Guardar con nombre original si el renombrado falla
                            archivos_descargados.append(archivo)                    
                    
                    print(f"☐ Deseleccionando...")
                    await self.marcar_checkbox_header_tabla(marcar=False)
                    await asyncio.sleep(1)
                
                print(f"\n✅ Período {idx} completado")
                
            except Exception as e:
                print(f"❌ Error en período {idx}: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # Intentar recuperarse para el siguiente período
                if idx < len(periodos):
                    print("   🔄 Intentando recuperar sesión para siguiente período...")
                    try:
                        await self.page.reload(wait_until='networkidle')
                        await asyncio.sleep(3)
                    except:
                        print("   ❌ No se pudo recuperar, saltando períodos restantes")
                        break
        
        print("\n" + "="*60)
        print(f"✅ PROCESAMIENTO COMPLETADO")
        print(f"📁 Total archivos: {len(archivos_descargados)}")
        print("="*60)
        
        return archivos_descargados


    async def llenar_campo_texto(self, identificador: str, texto: str):
        """
        Llena un campo de texto (input, textarea) con el valor especificado
        
        Args:
            identificador: ID, name o placeholder del campo
            texto: Texto a ingresar
        """
        print(f"\n✏️ LLENANDO CAMPO DE TEXTO")
        print(f"   Campo: {identificador}")
        print(f"   Texto: {texto}")
        print("-" * 40)
        
        selectores = [
            f"#{identificador}",
            f"[name='{identificador}']",
            f"[placeholder*='{identificador}']",
            f"input#{identificador}",
            f"textarea#{identificador}",
            f"[id*='{identificador}']",
            f"input[name='{identificador}']",
            f"textarea[name='{identificador}']"
        ]
        
        campo_encontrado = None
        
        for selector in selectores:
            try:
                elemento = await self.page.query_selector(selector)
                if elemento and await elemento.is_visible():
                    campo_encontrado = elemento
                    print(f"   ✅ Campo encontrado con selector: {selector}")
                    break
            except:
                continue
        
        if campo_encontrado:
            try:
                # Limpiar el campo primero
                await campo_encontrado.click()
                await campo_encontrado.press("Control+a")
                await campo_encontrado.press("Delete")
                
                # Ingresar el texto
                await campo_encontrado.fill(texto)
                print(f"   ✅ Texto ingresado exitosamente")
                
                # Disparar evento de cambio
                await campo_encontrado.press("Tab")
                
                return True
                
            except Exception as e:
                print(f"   ❌ Error al llenar el campo: {str(e)}")
                return False
        else:
            print(f"   ❌ No se encontró el campo con identificador: {identificador}")
            return False
    
    async def cambiar_a_iframe(self, identificador: str = None, indice: int = 0):
        """
        Cambia el contexto al contenido dentro de un iframe
        
        Args:
            identificador: ID o name del iframe
            indice: Índice del iframe si no se especifica identificador
        """
        print(f"\n🔄 CAMBIANDO A IFRAME...")
        
        try:
            if identificador:
                # Buscar por ID o name
                frame = await self.page.wait_for_selector(f'iframe#{identificador}, iframe[name="{identificador}"]', timeout=5000)
                print(f"✅ Iframe encontrado: {identificador}")
            else:
                # Buscar por índice
                iframes = await self.page.query_selector_all('iframe')
                if indice < len(iframes):
                    frame = iframes[indice]
                    print(f"✅ Usando iframe índice {indice}")
                else:
                    print(f"❌ No existe iframe con índice {indice}")
                    return False
            
            # Obtener el contenido del frame
            frame_element = await frame.content_frame()
            if frame_element:
                self.page = frame_element
                print("✅ Contexto cambiado al iframe")
                print("ℹ️ Ahora puedes analizar el contenido dentro del iframe")
                return True
            else:
                print("❌ No se pudo acceder al contenido del iframe")
                return False
                
        except Exception as e:
            print(f"❌ Error al cambiar a iframe: {str(e)}")
            return False
    
    async def esperar(self, segundos: int = 2):
        """
        Espera un número de segundos
        
        Args:
            segundos: Segundos a esperar
        """
        print(f"⏳ Esperando {segundos} segundos...")
        await asyncio.sleep(segundos)
    

    async def cerrar(self):
        """Cierra el navegador y limpia recursos"""
        print("\n🔄 Cerrando navegador...")
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("✅ Navegador cerrado")
    