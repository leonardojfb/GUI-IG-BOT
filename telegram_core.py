"""
📡 TELEGRAM_CORE.PY - Módulo de Integración con Telegram usando Pyrogram
Gestiona la creación de infraestructura de Telegram para Virtual Assistants
"""

import asyncio
from pyrogram import Client
from database import DatabaseManager

# ==================== CONFIGURACIÓN ====================
# Credenciales de Telegram (del bot)
TOKEN = "8787705820:AAGIeKGzhxHZgUmbbH9G9EgK5Y7M11J-MWM"
CHAT_ID = "-1003749971714"

# IMPORTANTE: Reemplaza estos valores con tus credenciales reales de Telegram
# Obtenlas en: https://my.telegram.org/apps
API_ID = 12345678  # Reemplazar con tu API_ID real
API_HASH = "0123456789abcdef0123456789abcdef"  # Reemplazar con tu API_HASH real

# ==================== FUNCIONES ASÍNCRONAS ====================
async def create_va_infrastructure(va_name: str) -> dict:
    """
    Crea la infraestructura completa de Telegram para un Virtual Assistant.
    
    Proceso:
    1. Inicia sesión en Telegram con Pyrogram
    2. Crea un Supergrupo con nombre "[VA] {va_name} - Operaciones"
    3. Guarda el ID del grupo en la base de datos (tabla virtual_assistants)
    
    Args:
        va_name (str): Nombre del Virtual Assistant
        
    Returns:
        dict: Información del grupo creado
            {
                'success': bool,
                'group_id': str (chat_id del supergrupo),
                'group_title': str,
                'group_link': str (opcional, si es público),
                'error': str (solo si success=False)
            }
    """
    result = {
        'success': False,
        'group_id': None,
        'group_title': None,
        'group_link': None,
        'error': None
    }
    
    # Crear cliente de Pyrogram
    # session_name será el nombre del archivo .session que se creará
    app = Client(
        name=f"va_{va_name.lower().replace(' ', '_')}_session",
        api_id=API_ID,
        api_hash=API_HASH
    )
    
    try:
        # Iniciar el cliente
        await app.start()
        
        # Título del grupo
        group_title = f"📦 [VA] {va_name} - Operaciones"
        
        # Crear supergrupo
        # description es opcional pero útil para identificar el grupo
        group = await app.create_supergroup(
            title=group_title,
            description=f"Grupo de coordinación de operaciones para el Virtual Assistant: {va_name}"
        )
        
        # Obtener el ID del chat (será negativo para supergrupos)
        group_id = str(group.id)
        
        # Actualizar la base de datos
        db = DatabaseManager()
        db.update_va_telegram_group(va_name, group_id)
        db.close()
        
        # Poblar resultado exitoso
        result['success'] = True
        result['group_id'] = group_id
        result['group_title'] = group_title
        
        # Si el grupo tiene username (es público), obtener el link
        if hasattr(group, 'username') and group.username:
            result['group_link'] = f"https://t.me/{group.username}"
        
        print(f"✅ Grupo de Telegram creado exitosamente para VA: {va_name}")
        print(f"   📝 Título: {group_title}")
        print(f"   🆔 ID: {group_id}")
        
    except Exception as e:
        result['error'] = str(e)
        print(f"❌ Error al crear grupo de Telegram para VA {va_name}: {e}")
    
    finally:
        # Detener el cliente
        await app.stop()
    
    return result


async def create_account_topic(va_name: str, account_username: str) -> dict:
    """
    Crea un Topic (tema/hilo) dentro del grupo del VA para una cuenta específica.
    
    Args:
        va_name (str): Nombre del Virtual Assistant (debe tener grupo creado)
        account_username (str): Username de la cuenta virtual
        
    Returns:
        dict: Información del topic creado
            {
                'success': bool,
                'topic_id': int,
                'topic_name': str,
                'error': str (solo si success=False)
            }
    """
    result = {
        'success': False,
        'topic_id': None,
        'topic_name': None,
        'error': None
    }
    
    # Obtener el ID del grupo del VA desde la base de datos
    db = DatabaseManager()
    
    # Primero necesitamos obtener el tg_group_id del VA
    # (Nota: Necesitarías añadir un método get_va_by_name en DatabaseManager para esto)
    # Por ahora, asumimos que el grupo existe
    
    app = Client(
        name=f"va_{va_name.lower().replace(' ', '_')}_session",
        api_id=API_ID,
        api_hash=API_HASH
    )
    
    try:
        await app.start()
        
        # Aquí iría la lógica para crear el topic usando:
        # chat = await app.get_chat(group_id)
        # topic = await app.create_forum_topic(chat_id=group_id, name=f"🔹 {account_username}")
        
        # Nota: Esta funcionalidad requiere que el grupo tenga habilitados los Topics
        # y permisos adecuados
        
        result['error'] = "Funcionalidad de Topics pendiente de implementación completa"
        
    except Exception as e:
        result['error'] = str(e)
    
    finally:
        await app.stop()
        db.close()
    
    return result


# ==================== FUNCIONES SÍNCRONAS (WRAPPERS) ====================
def create_va_group_sync(va_name: str) -> dict:
    """
    Wrapper síncrono para crear grupo de Telegram de un VA.
    Puede ser llamado desde tkinter u otros contextos síncronos.
    
    Args:
        va_name (str): Nombre del Virtual Assistant
        
    Returns:
        dict: Resultado de la operación (igual que create_va_infrastructure)
    """
    return asyncio.run(create_va_infrastructure(va_name))


def create_account_topic_sync(va_name: str, account_username: str) -> dict:
    """
    Wrapper síncrono para crear topic de cuenta.
    
    Args:
        va_name (str): Nombre del Virtual Assistant
        account_username (str): Username de la cuenta virtual
        
    Returns:
        dict: Resultado de la operación
    """
    return asyncio.run(create_account_topic(va_name, account_username))


# ==================== UTILIDADES ====================
async def get_me_info() -> dict:
    """
    Obtiene información del usuario autenticado en Telegram.
    Útil para verificar que las credenciales funcionan correctamente.
    
    Returns:
        dict: Información del usuario o error
    """
    result = {'success': False, 'user': None, 'error': None}
    
    app = Client(
        name="test_session",
        api_id=API_ID,
        api_hash=API_HASH
    )
    
    try:
        await app.start()
        me = await app.get_me()
        
        result['success'] = True
        result['user'] = {
            'id': me.id,
            'first_name': me.first_name,
            'username': me.username,
            'phone': me.phone_number
        }
        
    except Exception as e:
        result['error'] = str(e)
    
    finally:
        await app.stop()
    
    return result


def test_telegram_credentials() -> bool:
    """
    Verifica que las credenciales de Telegram sean válidas.
    
    Returns:
        bool: True si las credenciales funcionan, False si hay error
    """
    result = asyncio.run(get_me_info())
    
    if result['success']:
        print("✅ Credenciales de Telegram válidas")
        print(f"   Usuario: {result['user']['first_name']} (@{result['user']['username']})")
        return True
    else:
        print(f"❌ Error de credenciales: {result['error']}")
        return False


# ==================== PUNTO DE ENTRADA PARA PRUEBAS ====================
if __name__ == "__main__":
    print("🔧 Módulo telegram_core.py cargado")
    print("=" * 60)
    
    # Test 1: Verificar credenciales
    print("\n1️⃣ Verificando credenciales de Telegram...")
    if test_telegram_credentials():
        print("   ✓ Credenciales OK")
    else:
        print("   ✗ Por favor verifica API_ID y API_HASH en telegram_core.py")
        print("   📍 Obtén tus credenciales en: https://my.telegram.org/apps")
    
    # Test 2: Crear grupo de prueba (descomentar para ejecutar)
    # print("\n2️⃣ Creando grupo de prueba...")
    # resultado = create_va_group_sync("VA_Test")
    # if resultado['success']:
    #     print(f"   ✓ Grupo creado: {resultado['group_title']}")
    #     print(f"   🆔 ID: {resultado['group_id']}")
    # else:
    #     print(f"   ✗ Error: {resultado['error']}")
    
    print("\n" + "=" * 60)
    print("🎯 Para usar este módulo desde tu GUI:")
    print("   from telegram_core import create_va_group_sync")
    print("   resultado = create_va_group_sync('Nombre_VA')")
