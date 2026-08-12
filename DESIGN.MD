# Documento de Diseño de Arquitectura: Chatbot FastAPI + MongoDB

## 1. Visión General del Sistema
El objetivo de este proyecto es construir un servicio de Chatbot conversacional robusto, escalable, mantenible y de fácil despliegue, cumpliendo con los requerimientos del Code Challenge.

El sistema permite a los usuarios iniciar conversaciones, enviar mensajes a un Modelo de Lenguaje (LLM), mantener el historial conversacional persistido en MongoDB y recolectar métricas en tiempo real a través de Prometheus.

---

## 2. Arquitectura de Alto Nivel

```
+-----------------------------------------------------------------------+
|                             Navegador Web                             |
|                    (Frontend HTML5 + CSS3 + JS)                       |
+-----------------------------------------------------------------------+
                                   |
                         HTTP / REST Requests
                                   v
+-----------------------------------------------------------------------+
|                           FastAPI Backend                             |
|                                                                       |
|  +-------------------+   +--------------------+   +----------------+  |
|  |  Static File App  |   |  REST API Routers  |   | Middleware &   |  |
|  | (Serves UI / Web) |   | (/api/v1/chat,...) |   | Prometheus     |  |
|  +-------------------+   +--------------------+   +----------------+  |
|                                    |                       |          |
|                         +----------------------+           |          |
|                         |  LLM Service Layer   |           v          |
|                         | (Strategy Pattern)   |       /metrics       |
|                         +----------------------+           |          |
|                               /          \                 |          |
|             (API Key Valid)  /            \ (No API Key)   |          |
|                             v              v               |          |
|                  +--------------------+  +--------------------+       |
|                  | OpenRouter Service |  |  Mock LLM Service  |       |
|                  | (OpenAI Compatible)|  | (Fallback / Demo)  |       |
|                  +--------------------+  +--------------------+       |
|                                                                       |
|                         +----------------------+                      |
|                         | Persistence Service  |                      |
|                         |  (Motor Async Client)|                      |
|                         +----------------------+                      |
+------------------------------------|----------------------------------+
                                     |                       ^
                               Async Driver                  |
                                     v                   Scrape (15s)
+----------------------------------------+       +----------------------+
|            MongoDB Database            |       |  Prometheus Server   |
| (Colecciones: conversations, messages) |       | (Metrics Collection) |
+----------------------------------------+       +----------------------+
```

---

## 3. Componentes Principales

### 3.1. Frontend (Capas de Presentación)
* **Tecnología:** HTML5, CSS3, JavaScript Vanilla (o HTMX).
* **Estrategia de Entrega:** Servido directamente por FastAPI mediante `fastapi.staticfiles.StaticFiles`.
* **Justificación:** Mantiene la arquitectura simple (KISS principle) evitando la necesidad de un contenedor adicional para Nginx/Apache.
* **Calidad de presentación:** El parsing correcto del Markdown generado por el AI es crítico para la experiencia del usuario. Mensajes mal renderizados harán que el producto se perciba barato y poco profesional.

### 3.2. Backend (FastAPI Layer)
* **Runtime:** Python 3.12 (o 3.13-slim).
* **Framework:** FastAPI con Pydantic V2 para validación estricta de esquemas Request/Response.
* **Capas de Dominio:**
  * **Routers / Endpoints:** Manejo de rutas REST (`/api/v1/conversations`, `/api/v1/chat`, `/metrics`).
  * **Service Layer:** Aislamiento de lógica de negocio y comunicación con servicios externos/LLM.
  * **Repositories / DAOs:** Gestión de consultas a la base de datos a través del driver asíncrono.

### 3.3. Integración con LLM (Strategy Pattern & Fallback)
* **Proveedor Principal:** OpenRouter (SDK de OpenAI apuntado a `https://openrouter.ai/api/v1`).
* **Manejo de Fallback / Graceful Degradation:**
  * Si la variable de entorno `OPENROUTER_API_KEY` no está configurada, el sistema instanciará dinámicamente un `MockLLMService`.
  * **Beneficio:** Evita que la aplicación explote al iniciar (`docker compose up`) sin la clave, ofreciendo una experiencia en modo demo fluida para el evaluador.

### 3.4. Persistencia (MongoDB) & Optimización de BD
* **Driver:** `Motor` (Driver oficial asíncrono de MongoDB para Python).
* **Garantía:** Conexiones no bloqueantes que preservan el Event Loop de FastAPI.
* **Indexación Compuesta (Detalle Crucial):**
  * `db.messages.create_index([("conversation_id", 1), ("timestamp", 1)])`
  * **Razón**: A medida que la cantidad de mensajes crece en la base de datos, consultar el historial de un chat (`.find({"conversation_id": conv_id}).sort("timestamp", 1)`) sin un índice compuesto requeriría un escaneo completo de colección ($O(N)$) y una etapa de ordenamiento en memoria (que falla en MongoDB si supera 32 MB). Con el índice compuesto, MongoDB realiza una búsqueda B-Tree instantánea ($O(\log N)$) recuperando los mensajes ya ordenados cronológicamente sin consumo adicional de CPU/RAM.

### 3.5. Arquitectura Stateless & Escalabilidad Horizontal
* **Cero Estado en Memoria**: El backend FastAPI es 100% *stateless*. Toda la sesión, historial conversacional y contexto reside de manera segura en MongoDB.
* **Escalabilidad Horizontal**: Se puede escalar el backend en múltiples réplicas (`docker compose up --scale backend=3`) detrás de cualquier balanceador de carga sin necesidad de *sticky sessions* ni sincronización de memoria entre nodos.

### 3.6. Streaming de Respuestas (SSE) & UX
* **FastAPI `StreamingResponse` con Server-Sent Events (`text/event-stream`)**: Los tokens del LLM se transmiten al cliente en tiempo real a medida que son entregados por OpenRouter (o el Mock Service).
* **Mejora Percibida de Latencia**: Reduce drásticamente el *Time To First Token* (TTFT), proporcionando feedback visual inmediato al usuario en lugar de bloquear la UI esperando la respuesta completa.

### 3.7. Observabilidad y Métricas (Prometheus)
* **Biblioteca:** `prometheus_client`.
* **Endpoint de Scraping:** GET `/metrics` en formato OpenMetrics/Prometheus.
* **Métricas Recolectadas:**
  * **Uso de Tokens**: `chat_llm_prompt_tokens_total`, `chat_llm_completion_tokens_total`, `chat_llm_tokens_total` (etiquetados por `provider` y `model`).
  * **Actividad Conversacional**: `chat_conversations_created_total`, `chat_conversations_deleted_total`, `chat_messages_total` (etiquetado por `role`).
  * **Latencia & Rendimiento**: `chat_llm_request_duration_seconds`, `chat_llm_time_to_first_token_seconds` (TTFT para respuestas streaming), `chat_http_request_duration_seconds`.

---

## 4. Modelo de Datos (MongoDB Schema)

### Colección: `conversations`
Representa una sesión o hilo de chat.
```json
{
  "_id": "ObjectId(...)",
  "title": "string (ej: Resumen de reunión)",
  "created_at": "ISODate(...)",
  "updated_at": "ISODate(...)"
}
```

### Colección: `messages`
Representa un mensaje individual dentro de una conversación.
```json
{
  "_id": "ObjectId(...)",
  "conversation_id": "ObjectId(...)",
  "role": "string (user | assistant | system)",
  "content": "string",
  "timestamp": "ISODate(...)"
}
```
* **Índice Compuesto Obligatorio:** `{ conversation_id: 1, timestamp: 1 }` para garantizar lecturas en $O(\log N)$ del historial ordenado cronológicamente.

---

## 5. Decisiones Técnicas y Trade-offs

| Decisión | Elección | Alternativa descartada | Razón / Trade-off |
| :--- | :--- | :--- | :--- |
| **Versión de Python** | Python 3.12 / 3.13 | Python 3.14 | 3.14 es muy reciente/experimental; no todos los paquetes tienen wheels C precompiladas para Linux/Docker. |
| **Driver de Mongo** | Motor (Async) | PyMongo (Sync) | PyMongo bloquea el Event Loop de FastAPI, degradando drásticamente el throughput. |
| **Indexación en BD** | Índice Compuesto `{ conversation_id: 1, timestamp: 1 }` | Sin índice o índices simples separados | Evita escaneos de colección $O(N)$ y ordenamientos en memoria cuando el volumen de mensajes crece. |
| **Backend Stateless** | 100% Stateless (Datos en Mongo) | Estado de chat en memoria (dict/session) | Permite escalar horizontalmente (`docker compose up --scale backend=3`) sin romper sesiones de usuario. |
| **Streaming SSE** | Server-Sent Events (`StreamingResponse`) | Polling o Responses Sincrónicas Bloqueantes | Reduce el Time To First Token (TTFT) y mejora drásticamente la velocidad percibida. |
| **Servido de Frontend** | Servido por FastAPI | Contenedor Nginx independiente | Reduce la complejidad de `docker-compose.yml` de 3 a 2 contenedores sin perder funcionalidad. |
| **Resiliencia API Key** | Strategy Pattern (Mock LLM) | Lanza excepción en startup | Garantiza que `docker compose up` funcione *out-of-the-box* sin credenciales obligatorias. |
| **Métricas y Observabilidad** | Prometheus + `prometheus_client` (`/metrics`) | APM SaaS (ej: Datadog, New Relic) | Se agregó Prometheus para un manejo de métricas y monitoreo más sencillo y 100% auto-contenido localmente, a diferencia de Datadog que requeriría cuentas externas, agentes pesados y API Keys pagas. |
| **Health-check endpoint** | `db.command("ping")` en `/system/status` | No hay verificación de DB en el estado de salud | Permite exponer un estado de servicio fiable y devolver `503` cuando MongoDB no está disponible. |
| **CI / CD & SCA** | GitHub Actions + Ruff + Pytest | Ejecución manual local | GitHub Actions ofrece ejecuciones gratuitas ilimitadas para repos públicos. Mantiene altos estándares de calidad. |

---

## 6. Estructura del Proyecto

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml          # Pipeline de GitHub Actions (Ruff + Pytest)
├── app/
│   ├── api/                # Endpoints y controladores REST
│   │   └── v1/
│   ├── core/               # Configuración, logging, métricas Prometheus
│   │   └── metrics.py      # Definición de contadores e histogramas
│   ├── db/                 # Conexión a Mongo (Motor client & events)
│   ├── models/             # Esquemas Pydantic y modelos de BD
│   ├── services/           # Lógica de LLM (OpenRouter & Mock Provider)
│   ├── static/             # Archivos estáticos del Frontend (HTML, CSS, JS)
│   └── main.py             # Entrada principal de FastAPI + middleware métricas
├── tests/                  # Tests unitarios e integración (Pytest)
├── .env.example            # Plantilla de variables de entorno
├── prometheus.yml          # Configuración de scraping para Prometheus
├── DESIGN.md               # Documento de diseño arquitectónico
├── README.md               # Instrucciones de uso, setup y decisiones
├── Dockerfile              # Construcción optimizada del backend
├── docker-compose.yml      # Orchestration de Backend + MongoDB + Prometheus
├── pyproject.toml          # Configuración de dependencias, Ruff y Pytest
└── requirements.txt
```

---

## 7. Enlaces y Referencias
* **Brainstorming Inicial & Discusión:** [Ver Conversación](https://gemini.google.com/app/6a9d7e68a0a20cfe?hl=es_419)
* **Diagrama Arquitectónico (Excalidraw):** *(Pendiente de adjuntar por el autor)*.