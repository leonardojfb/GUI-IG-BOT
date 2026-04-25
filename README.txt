Ecosistema Tatiana
Este flujo de trabajo automatiza la creación, organización y distribución de contenido ultra-fotorealista para Instagram, garantizando que cada cuenta reciba contenido único con metadatos de hardware real (iPhone 15 Pro) y ubicación en USA.

🛠️ Requisitos del Sistema
Procesador: Intel i5 11th Gen (Arquitectura Tiger Lake) o superior.

GPU: NVIDIA con soporte CUDA (para renderizado acelerado por hardware).

Software:

Python 3.10+.

FFmpeg y FFprobe instalados y configurados en el PATH de Windows.

📂 Estructura del Proyecto
Antes de iniciar, asegúrate de tener la siguiente jerarquía de carpetas:

parte1/: Fondos visuales (backgrounds).

parte2/promo/: Ganchos de venta y promocionales.

parte2/suicide/: Contenido viral o de "quema".

accounts_promo.txt: Lista de nombres de usuario para campañas promo.

accounts_suicide.txt: Lista de nombres de usuario para campañas suicide.

captions.txt: Base de datos de textos exportados de Telegram/WhatsApp.

🚀 Guía de Uso: Paso a Paso
Paso 1: Renderizado Inteligente (videos.py)
Este módulo fusiona las partes y quema la metadata interna.

Coloca los clips en parte1 y parte2.

Ejecuta: python videos.py.

Resultado: Se crearán videos en videos_finales/ con el estándar CATEGORIA__P1ID__P2ID.mp4. Este nombre es el fingerprint logístico.

Paso 2: Organización del Calendario (Organizador.py)
Este script balancea la carga visual para evitar repeticiones.

Ejecuta: python Organizador.py.

Lógica: El sistema distribuye los videos en carpetas Dia_1, Dia_2, etc., dentro de CALENDARIO_POSTEO.

Resultado: Cada día tendrá la mezcla óptima de Promo y Suicide sin repetir fondos (P1) en el mismo lote.

Paso 3: Despacho a Telegram (organizadortg.py)
El paso final para la entrega a los VAs y socios estratégicos.

Ejecuta: python organizadortg.py.

Memoria Persistente: El script consulta fingerprint_history.json para saber qué video ha subido cada cuenta anteriormente y nunca repetirlos.

Variabilidad: Reordena aleatoriamente los hashtags en cada post para que no existan captions 100% idénticos.

📊 Reglas de Negocio Integradas
Cuota Diaria: El sistema prioriza 4 posts (3 Reels + 1 Story) por cuenta al día.

Exclusividad Visual: Ninguna cuenta repetirá una combinación de fondo (P1) o clip (P2) en el mismo día.

Persistencia Global: Si tienes 400 videos y 10 cuentas, el sistema gestionará hasta 4,000 publicaciones únicas antes de agotar el stock total de combinaciones.

⚠️ Mantenimiento y Logs
Admin Report: Al finalizar cada corrida, el bot enviará un reporte al hilo Admin de Telegram indicando el total de enviados y si hubo necesidad de usar "Relleno de Emergencia" por falta de stock nuevo.

Ficheros de Estado:

telegram_state_v11.json: Guarda los IDs de los hilos de Telegram.

fingerprint_history.json: NO BORRAR. Contiene la memoria de qué ha publicado cada cuenta.

Nota del Arquitecto: Este flujo está diseñado para escalar la marca de Tatiana de forma orgánica, minimizando el riesgo de shadowban mediante el uso de metadatos spoofing y entropía en los textos.