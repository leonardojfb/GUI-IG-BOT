# Control plane, Vault local y analitica de contenido

**Estado:** aprobado para planificacion; aun no implementado.

## Objetivo

Agregar un backend central que sirva a la futura pagina web y a la GUI de
escritorio, sin mover todavia el procesamiento multimedia fuera de la PC del
usuario. El sistema debe permitir control remoto seguro, licencias, usuarios,
roles, catalogo de contenido, Vault local e historial de rendimiento cargado
manualmente.

El resultado no pretende hacer imposible modificar un cliente local. Protege
las operaciones privilegiadas trasladandolas al servidor y manteniendo el
cliente limitado a operaciones autorizadas.

## Alcance inicial

- Dashboard web para propietarios, administradores y operadores autorizados.
- API central con PostgreSQL como fuente de verdad para datos sincronizados.
- GUI Windows como agente instalado que aplica cambios locales y reporta su
  resultado.
- Gestion remota de cuentas, categorias, VA, tandas, horarios, configuracion
  no secreta de Telegram y operaciones permitidas del Vault.
- Vault de originales local a cada instalacion, con deduplicacion por hash.
- Historial inmutable que una contenido, variantes, asignaciones, entregas y
  metricas manuales.
- Licencias, instalaciones y capacidades revocables.

## Fuera del alcance inicial

- Procesar Forge o editar videos en el servidor.
- Enviar los videos de usuario a la nube de forma obligatoria.
- Exponer una carpeta, SQLite o una consola de comandos de la PC a Internet.
- Ejecutar comandos de shell, rutas arbitrarias o SQL enviados por la web.
- Inferir automaticamente metricas o afirmar causalidad entre una edicion y
  un resultado.
- Crear el backend, modificar la GUI o migrar SQLite durante esta etapa de
  especificacion.

## Alternativas evaluadas

### A. Control central + Vault local + respaldo cloud opcional (elegida)

El servidor contiene identidad, control, catalogo e historial. Cada GUI
conserva los originales y procesa localmente. La nube se incorpora despues,
por decision explicita del propietario, como replica del contenido.

Ventajas: no hay subida masiva inicial, los archivos grandes siguen siendo
locales y la web puede controlar instalaciones sin abrir puertos entrantes.
Limitacion: una accion sobre un archivo espera a que la instalacion que posee
el archivo este conectada.

### B. Vault solo local y sin servidor

Es barato y simple, pero no ofrece control remoto, roles, licencias revocables
ni respaldo verificable. Se descarta.

### C. Vault cloud obligatorio desde el primer lanzamiento

Permite uso entre maquinas desde el inicio, pero agrega costos, esperas de
carga, retencion de datos y superficie de seguridad antes de validar el flujo
de control. Se posterga.

## Arquitectura elegida

```text
Dashboard web ------------------+
                                | HTTPS
GUI Windows (agente) -----------+--> API central (FastAPI)
                                      |-- PostgreSQL: fuente de verdad
                                      |-- autenticacion, roles y licencias
                                      |-- cola de comandos y auditoria
                                      |-- catalogo, linaje y metricas
                                      +-- relay/worker Telegram futuro

GUI Windows
  |-- organizador.db: proyeccion operativa existente y cache local
  |-- vault.db: indice local de archivos y replicas
  +-- %LOCALAPPDATA%\MetodoIG\Vault: originales y derivados locales
```

La API se implementara en Python/FastAPI porque el agente actual tambien usa
Python. El dashboard es otro cliente HTTPS de esa API; su framework visual no
forma parte de esta especificacion. PostgreSQL es la fuente de verdad de los
datos sincronizados. `organizador.db` sigue siendo necesaria para que la GUI
opere localmente y no sera reemplazada en bloque.

La GUI nunca se conecta directamente a PostgreSQL ni recibe una credencial de
la base. El dashboard tampoco accede a SQLite ni al sistema de archivos de una
PC.

## Limites de confianza y conectividad

Cada instalacion inicia conexiones HTTPS salientes. No abre puertos entrantes
ni acepta conexiones directas desde el dashboard.

1. Tras el login, la GUI registra una instalacion y crea una clave de
   dispositivo. La clave privada se protege con Windows DPAPI; la publica se
   registra en el backend.
2. El backend entrega un access token de corta duracion y un refresh token
   protegido con DPAPI. Cada comando se asocia a organizacion, instalacion,
   actor, capacidad y expiracion.
3. La GUI consulta `GET /agent/commands` mediante long polling de hasta 25
   segundos y confirma el resultado con `POST /agent/commands/{id}/result`.
4. El dashboard recibe los cambios de estado desde el backend. Ningun comando
   se muestra como aplicado hasta que la instalacion lo confirma.

Una instalacion sin conexion puede continuar solo con el comportamiento local
autorizado para su periodo offline. Los comandos remotos quedan `pending`; no
se simula aplicacion inmediata.

## Roles y capacidades

Todas las entidades pertenecen a una `organization`. Los roles iniciales son:

| Rol | Alcance |
| --- | --- |
| Owner | Gestiona organizacion, licencias, instalaciones, roles y toda la operacion. |
| Admin | Gestiona datos operativos y usuarios, pero no transfiere propiedad ni maneja firma. |
| Operator | Gestiona cuentas, tandas, horarios, Vault y metricas dentro de capacidades concedidas. |
| Viewer | Solo consulta catalogo, estado, historial y analitica. |

El backend calcula permisos desde la identidad validada; nunca acepta un rol,
`user_id` u `organization_id` enviado por el dashboard o la GUI como prueba de
autorizacion. Las capacidades de licencia limitan adicionalmente acciones como
numero de instalaciones, Vault, gestion de cuentas y control remoto.

## Modelo de datos central

Las tablas iniciales se agrupan por limite funcional:

| Grupo | Entidades |
| --- | --- |
| Identidad | `organizations`, `users`, `memberships`, `roles`, `sessions` |
| Licencias | `licenses`, `installations`, `device_public_keys`, `capabilities`, `revocations`, `license_events` |
| Control | `command_requests`, `command_results`, `state_snapshots`, `sync_outbox`, `audit_events` |
| Operacion | `accounts`, `virtual_assistants`, `categories`, `schedules`, `tandas`, `telegram_settings` |
| Contenido | `media_assets`, `asset_replicas`, `media_variants`, `media_relations`, `media_events` |
| Resultados | `deliveries`, `metric_snapshots`, `metric_definitions`, `analysis_views` |

Cada registro sincronizable tiene `id` UUID, `organization_id`, `created_at`,
`updated_at`, `version`, `deleted_at` y el actor que produjo el ultimo cambio.
Las mutaciones incluyen la version esperada: ante conflicto, el servidor
rechaza el cambio con un resultado explicito en lugar de sobrescribir datos.

## Comandos remotos permitidos

El backend usa una allowlist tipada. Cada comando tiene UUID, instalacion
destino, payload validado, idempotency key, vencimiento y estado
`pending | claimed | applied | failed | expired | cancelled`.

El MVP permite:

- Alta, edicion, baja logica y reasignacion de cuentas, categorias y VA.
- Alta, edicion y activacion de tandas, calendarios y horarios.
- Sincronizacion de configuracion no secreta de Telegram.
- Consultar estado local, capacidad de disco y resumen operativo.
- Importar un archivo elegido por el usuario localmente al Vault.
- Reutilizar un `media_id` existente para una accion permitida de la GUI.
- Solicitar eliminacion logica de un asset o de una variante, con confirmacion
  explicita y conservacion de la auditoria.

No existen comandos genericos de archivos, shell, Python, SQL ni rutas
absolutas. La GUI solo opera dentro de sus raices permitidas: Vault, directorio
operativo de la aplicacion y temporales propios. Cualquier ruta de importacion
se elige en la GUI local, se normaliza y se valida antes de copiar.

Los secretos de Telegram no se sincronizan como configuracion ordinaria. Hasta
definir el relay de Telegram en el hardening, el backend solo maneja metadatos
no secretos; ninguna orden web devuelve ni registra un token.

## Vault local

El Vault es local por defecto y usa una raiz administrada por la aplicacion:

```text
%LOCALAPPDATA%\MetodoIG\Vault\objects\<sha256[0:2]>\<sha256>.<extension>
```

Al importar un archivo, la GUI calcula SHA-256 mientras lo copia a un temporal
privado y lo mueve atomica y definitivamente al Vault. Si ya existe el mismo
hash, crea solo una nueva referencia logica. `vault.db` registra el hash,
tamano, MIME detectado, fecha, instalacion propietaria, ruta relativa y estado
de replica. Nunca acepta una ruta remota como identidad del archivo.

`media_assets` describe el original. `media_variants` enlaza cada edicion,
Forge o copia derivada con el original. `asset_replicas` empieza con
`storage=local` y deja preparada una futura replica `storage=cloud`, siempre
opt-in. El respaldo cloud no se activa ni se disena como obligatorio en este
MVP.

## Linaje, historial y metricas manuales

`media_events` es append-only. Registra importacion, deduplicacion, edicion,
Forge, reutilizacion, tanda, asignacion, calendarizacion, envio, reintento,
fallo, cambio manual y eliminacion logica. Cada evento incluye actor,
instalacion, timestamp, recurso afectado, accion, resultado y correlation ID;
nunca incluye tokens, cookies o rutas absolutas innecesarias.

`deliveries` enlaza una variante con cuenta, tanda, fecha, estado y envio. Las
metricas se cargan manualmente como snapshots fechados sobre esa entrega:
vistas, likes, comentarios, compartidos, guardados, seguidores ganados y notas
del operador. Se conserva fuente `manual`, actor y hora de carga.

El dashboard presenta comparaciones por contenido, variante, atributos de
edicion, tipo de cuenta, categoria, VA y periodo. Muestra muestras, promedios,
medianas y tendencias; etiqueta resultados con poca muestra y no afirma que un
cambio causo un resultado sin evidencia experimental.

## Sincronizacion y consistencia

El servidor es la fuente de verdad de identidad, licencias, comandos,
catalogo, historial y configuracion compartida. La GUI mantiene proyecciones
locales para operar y muestra el ultimo estado confirmado.

Una edicion hecha en el dashboard crea una mutacion versionada y un comando
para la instalacion destino. Una edicion hecha localmente entra en un outbox
durable, se envia con una idempotency key y recibe un snapshot versionado. Ante
conflicto, no hay last-write-wins silencioso: el dashboard muestra ambas
versiones y exige que un operador elija.

El estado inmediato significa "recibido y propagado"; el estado "aplicado"
requiere confirmacion de la GUI. El objetivo de conexion es reflejar ordenes en
menos de 30 segundos cuando la GUI esta abierta y conectada.

## Respaldo cloud posterior

La futura replica se agrega a traves de una interfaz de almacenamiento, no
cambiando el modelo de contenido. Al habilitarla por organizacion, el agente
sube los objetos por hash a almacenamiento de objetos con URLs de carga cortas;
el backend conserva solo metadatos y autorizacion. La descarga requiere una
capacidad autorizada y se verifica contra hash. Retencion, costo, regiones y
recuperacion se definen antes de habilitarla.

## Orden de entrega

1. **Control plane:** baseline de seguridad, API, PostgreSQL, identidad,
   instalaciones, roles, licencias, auditoria y canal de comandos sin acciones
   peligrosas.
2. **Sincronizacion operativa:** proyecciones de cuentas, VA, tandas, horarios
   y configuracion no secreta; UI web y confirmacion desde GUI.
3. **Vault local y linaje:** indice local, importacion segura, deduplicacion,
   referencias y eventos de contenido.
4. **Metricas manuales:** entregas, formularios, snapshots y vistas analiticas.
5. **Hardening de la GUI:** secretos/Telegram, SQLite, compilacion, updater,
   firma e integridad segun `SECURITYPLAN.md`.
6. **Respaldo cloud opcional:** solo tras validar el Vault local y autorizar
   costos, retencion y recuperacion.

Cada etapa se implementa en una rama y PR de alcance unico, con migraciones
reversibles, pruebas negativas de autorizacion y rollback documentado.

## Criterios de aceptacion del MVP de arquitectura

- Un Owner puede crear una instalacion y revocarla; una instalacion revocada no
  recibe capacidades ni comandos.
- Un Viewer no puede mutar datos; un usuario de otra organizacion recibe 403 o
  404 y nunca ve sus recursos.
- Una orden duplicada no duplica una modificacion ni una accion de archivo.
- El dashboard distingue `pending`, `applied` y `failed` mediante confirmacion
  real del agente.
- Un original duplicado no se copia dos veces en el Vault.
- Toda variante y entrega puede recorrerse hasta su original y sus metricas
  manuales sin mostrar secretos.
- La GUI no expone un puerto entrante, no ejecuta comandos arbitrarios y no
  entrega tokens de Telegram al dashboard.
- La app existente sigue iniciando mediante `launcher.py -> gui_premium_v7.py`.

## Riesgos residuales declarados

- Un usuario con control total de una PC puede inspeccionar archivos y memoria
  mientras la GUI tiene acceso a contenido local.
- Sin respaldo cloud, la perdida de la PC puede perder originales del Vault.
- La disponibilidad remota depende de que la GUI este abierta y conectada.
- Las metricas manuales dependen de disciplina de carga y no prueban causalidad.
- Las operaciones de Telegram siguen requiriendo una decision de arquitectura
  del plan de seguridad; el relay no se construye dentro de este diseño.
