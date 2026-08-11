# Documento de Diseño de Arquitectura: Chatbot FastAPI + MongoDB

## 1. Visión General del Sistema
El objetivo de este proyecto es construir un servicio de Chatbot conversacional robusto, escalable, mantenible y de fácil despliegue, cumpliendo con los requerimientos del Code Challenge.

El sistema permite a los usuarios iniciar conversaciones, enviar mensajes a un Modelo de Lenguaje (LLM) y mantener el historial conversacional persistido de forma segura en MongoDB.

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
|  | (Serves UI / Web) |   | (/api/v1/chat,...) |   | Error Handling |  |
|  +-------------------+   +--------------------+   +----------------+  |
|                                    |                                  |
|                         +----------------------+                      |
|                         |  LLM Service Layer   |                      |
|                         | (Strategy Pattern)   |                      |
|                         +----------------------+                      |
|                               /          \                            |
|             (API Key Valid)  /            \ (No API Key)              |
|                             v              v                          |
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
                                     |
                               Async Driver
                                     v
+-----------------------------------------------------------------------+
|                          MongoDB Database                             |
|            (Colecciones: conversations, messages)                    |
+-----------------------------------------------------------------------+
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
  * **Routers / Endpoints:** Manejo de rutas REST (`/api/v1/conversations`, `/api/v1/chat`).
  * **Service Layer:** Aislamiento de lógica de negocio y comunicación con servicios externos/LLM.
  * **Repositories / DAOs:** Gestión de consultas a la base de datos a través del driver asíncrono.

### 3.3. Integración con LLM (Strategy Pattern & Fallback)
* **Proveedor Principal:** OpenRouter (SDK de OpenAI apuntado a `https://openrouter.ai/api/v1`).
* **Manejo de Fallback / Graceful Degradation:**
  * Si la variable de entorno `OPENROUTER_API_KEY` no está configurada, el sistema instanciará dinámicamente un `MockLLMService`.
  * **Beneficio:** Evita que la aplicación explote al iniciar (`docker compose up`) sin la clave, ofreciendo una experiencia en modo demo fluida para el evaluador.

### 3.4. Persistencia (MongoDB)
* **Driver:** `Motor` (Driver oficial asíncrono de MongoDB para Python) o `Beanie` (ODM asíncrono sobre Pydantic).
* **Garantía:** Conexiones no bloqueantes que preservan el Event Loop de FastAPI.

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
* **Índices:** Índice compuesto en `{ conversation_id: 1, timestamp: 1 }` para acelerar el recuperado del historial en orden cronológico.

---

## 5. Decisiones Técnicas y Trade-offs

| Decisión | Elección | Alternativa descartada | Razón / Trade-off |
| :--- | :--- | :--- | :--- |
| **Versión de Python** | Python 3.12 / 3.13 | Python 3.14 | 3.14 es muy reciente/experimental; no todos los paquetes tienen wheels C precompiladas para Linux/Docker. |
| **Driver de Mongo** | Motor (Async) | PyMongo (Sync) | PyMongo bloquea el Event Loop de FastAPI, degradando drásticamente el throughput. |
| **Servido de Frontend** | Servido por FastAPI | Contenedor Nginx independiente | Reduce la complejidad de `docker-compose.yml` de 3 a 2 contenedores sin perder funcionalidad. |
| **Resiliencia API Key** | Strategy Pattern (Mock LLM) | Lanza excepción en startup | Garantiza que `docker compose up` funcione *out-of-the-box* sin credenciales obligatorias. |
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
│   ├── core/               # Configuración (Pydantic Settings), logging
│   ├── db/                 # Conexión a Mongo (Motor client & events)
│   ├── models/             # Esquemas Pydantic y modelos de BD
│   ├── services/           # Lógica de LLM (OpenRouter & Mock Provider)
│   ├── static/             # Archivos estáticos del Frontend (HTML, CSS, JS)
│   └── main.py             # Entrada principal de FastAPI
├── tests/                  # Tests unitarios e integración (Pytest)
├── .env.example            # Plantilla de variables de entorno
├── DESIGN.md               # Documento de diseño arquitectónico
├── README.md               # Instrucciones de uso, setup y decisiones
├── Dockerfile              # Construcción optimizada del backend
├── docker-compose.yml      # Orchestration de Backend + MongoDB
├── pyproject.toml          # Configuración de dependencias, Ruff y Pytest
└── requirements.txt
```

---

## 7. Enlaces y Referencias
* **Brainstorming Inicial & Discusión:** [Ver Conversación](https://gemini.google.com/app/6a9d7e68a0a20cfe?hl=es_419)
* **Diagrama Arquitectónico (Excalidraw):** *(Pendiente de adjuntar por el autor)*.