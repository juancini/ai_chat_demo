# 🤖 AI Chatbot Service — FastAPI + MongoDB

Un service backend conversacional, robusto, escalable y listo para producción construido para el **Code Challenge**. Integre modelos de lenguaje (vía OpenRouter con fallback automático en modo Mock) y mantiene la persistencia de conversaciones en MongoDB.

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![MongoDB](https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

---

## 🚀 Cómo levantarlo y probarlo

El proyecto está diseñado para funcionar **out-of-the-box** inmediatamente después de clonar el repositorio, sin necesidad de configuraciones previas ni archivos adicionales.

### Paso 1: Clonar el repositorio
```bash
git clone https://github.com/juancini/ai_chat_demo.git
cd ai_chat_demo
```

### Paso 2: (Opcional) Configurar la API Key de OpenRouter
Si deseas probar la respuesta en vivo con modelos de AI reales (como Meta Llama 3.3 70B Free):
1. Copia la plantilla de entorno:
   ```bash
   cp .env.example .env
   ```
2. Edita `.env` y agrega tu clave de OpenRouter:
   ```env
   OPENROUTER_API_KEY=sk-or-v1-tu-clave-aqui
   ```

> 💡 **¿Sin API Key? ¡No hay problema!** Si ejecutas el proyecto sin configurar una API Key, el sistema activará automáticamente el **Modo Mock LLM**. Podrás interactuar con la interfaz, probar la creación de chats, el guardado de historial en MongoDB y la eliminación de conversaciones sin que la aplicación falle ni lance errores.

### Paso 3: Iniciar con Docker Compose
```bash
docker compose up --build
```

### Paso 4: Abrir la aplicación
Abre tu navegador e ingresa a:
👉 **[http://localhost:8000](http://localhost:8000)**

* **Documentación interactiva de la API (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Métricas en formato OpenMetrics/Prometheus**: [http://localhost:8000/metrics](http://localhost:8000/metrics)
* **Servidor y Dashboard de Prometheus**: [http://localhost:9090](http://localhost:9090)

---

## 📊 Métricas y Observabilidad (Prometheus)

El backend integra recolectores de **Prometheus** (`prometheus_client`) para monitorear el consumo de recursos, rendimiento y uso del chatbot:

* **Consumo de Tokens**:
  * `chat_llm_prompt_tokens_total`: Total de tokens de prompt (input) enviados al LLM.
  * `chat_llm_completion_tokens_total`: Total de tokens de respuesta (output) generados por el LLM.
  * `chat_llm_tokens_total`: Total combinado de tokens consumidos (desglosado por `provider` y `model`).
* **Métricas de Conversaciones y Mensajes**:
  * `chat_conversations_created_total`: Cantidad total de chats creados.
  * `chat_conversations_deleted_total`: Cantidad total de chats eliminados.
  * `chat_messages_total`: Mensajes procesados (etiquetados por `role`: `user` vs `assistant`).
* **Métricas de Latencia y Rendimiento**:
  * `chat_llm_request_duration_seconds`: Histograma de tiempo de respuesta del LLM.
  * `chat_llm_time_to_first_token_seconds`: Latencia hasta el primer token en respuestas streaming (TTFT).
  * `chat_http_request_duration_seconds`: Histograma de latencia de solicitudes HTTP.

> 💡 **Prometheus vs Datadog**: Elegimos incluir Prometheus y exponer `/metrics` para un manejo de métricas y monitoreo local auto-contenido, simple y sin costo. A diferencia de APM SaaS como Datadog, no requiere credenciales externas, agentes pesados ni configuraciones complejas para probar en un clone limpio.

---

## 🧪 Pruebas de Persistencia e Historial

1. Abre [http://localhost:8000](http://localhost:8000) y envía un par de mensajes en un chat nuevo.
2. Verifica en la barra lateral que la conversación aparece guardada con su título autogenerado.
3. Reinicia los contenedores desde tu terminal:
   ```bash
   docker compose restart
   ```
4. Recarga la página web: **Tus conversaciones y mensajes continuarán intactos**, gracias al volumen de persistencia configurado en MongoDB (`mongodb_data`).
5. Abre [http://localhost:9090](http://localhost:9090) para explorar las métricas recolectadas por Prometheus.


---

## 🛠️ Decisiones de Arquitectura y Trade-Offs

### 1. ¿Qué decidí incluir?
* **Arquitectura Limpia & Desacoplada (FastAPI + Pydantic V2)**: Separación clara entre capas: Routers REST (`app/api`), Lógica de Negocio (`app/services`), Esquemas (`app/models`) y Acceso a Datos (`app/db`).
* **Strategy Pattern para LLMs (`BaseLLMService`)**:
  * `OpenRouterLLMService`: Utiliza `httpx` asíncrono para enviar requests a la API compatible con OpenAI de OpenRouter.
  * `MockLLMService`: Fallback inteligente cuando no hay `OPENROUTER_API_KEY` configurada.
* **Persistencia Asíncrona con MongoDB (`Motor`)**: Utilización de drivers 100% asíncronos para evitar bloquear el Event Loop de FastAPI y garantizar alto throughput bajo concurrencia.
* **Indexación Compuesta en MongoDB (Detalle Crucial de Escalabilidad)**:
  * `db.messages.create_index([("conversation_id", 1), ("timestamp", 1)])`
  * **Por qué existe**: A medida que la cantidad de mensajes crece en la base de datos, consultar el historial (`.find({"conversation_id": conv_id}).sort("timestamp", 1)`) sin un índice compuesto obligaría a MongoDB a realizar un escaneo completo de colección ($O(N)$) y una costosa etapa de ordenamiento en memoria. El índice compuesto garantiza lecturas B-Tree instantáneas en $O(\log N)$ ordenadas cronológicamente.
* **Backend 100% Stateless (Escalabilidad Horizontal)**:
  * No se almacena estado de chat o sesión en memoria de FastAPI. Toda la información conversacional se recupera y persiste dinámicamente en MongoDB.
  * **Beneficio**: Permite escalar horizontalmente el backend (`docker compose up --scale backend=3`) detrás de un balanceador de carga sin romper las sesiones de los usuarios ni requerir *sticky sessions*.
* **Streaming de Respuestas vía Server-Sent Events (SSE)**:
  * Implementación con FastAPI `StreamingResponse` y `text/event-stream` para enviar tokens en tiempo real al frontend a medida que son entregados por OpenRouter (o Mock). Esto reduce drásticamente el *Time To First Token* (TTFT) y mejora la velocidad percibida por el usuario.
* **Métricas Prometheus Integradas**: Métricas de consumo de tokens, contadores de chats/mensajes y latencia expuestos en `/metrics` y monitoreados en tiempo real por el contenedor de Prometheus (`http://localhost:9090`).
* **Interfaz de usuario fluida (HTML5 + CSS Glassmorphic + JS)**: Interfaz minimalista pero cuidada con soporte para Markdown (código, tablas, formato), servida directamente por FastAPI sin requerir servidores web auxiliares.

### 2. ¿Qué dejé afuera a propósito? (y por qué)
* **Contenedor Nginx independiente**: 
  * *Razón*: El enunciado busca mantener el stack simple y funcional. Servir los archivos estáticos desde FastAPI mediante `fastapi.staticfiles.StaticFiles` reduce la complejidad del proyecto sin degradar la experiencia de usuario.
* **Sistema de Autenticación de Usuarios (JWT / OAuth2)**:
  * *Razón*: Para un Code Challenge, agregar autenticación añade fricción innecesaria al evaluador para probar la app. La app está centrada en la interacción conversacional y persistencia.
* **RAG / Vector Databases (ChromaDB / Pinecone)**:
  * *Razón*: Priorizamos el principio [KISS](https://en.wikipedia.org/wiki/KISS_principle) :"Preferimos algo chico, prolijo y bien pensado antes que algo grande y a medio terminar".

### 3. ¿Qué habría hecho distinto con más tiempo?
* **Búsqueda Full-Text sobre mensajes**: Implementar índices de texto en MongoDB para buscar términos clave dentro del historial de conversaciones.
* **Batería de tests con Testcontainers**: Usar un contenedor real de MongoDB efímero durante los tests de integración en lugar de mocks.


---

## 🤖 Uso de Inteligencia Artificial & Criterio Técnico

Durante el desarrollo de este challenge me apoyé en herramientas de IA (Google Antigravity CLI / Gemini 3.6 Flash) para acelerar el maquetado, generar esquemas de Pydantic y agilizar la escritura de tests.

### Caso donde rechacé una propuesta de la IA (Criterio de Ingeniería)

* **Propuesta inicial de la IA**: 
  Durante la fase inicial de diseño, la IA sugirió:
  1. Agregar un tercer contenedor Nginx en `docker-compose.yml` para actuar como reverse proxy.
  2. Lanzar una excepción explícita en la startup (`raise ValueError("OPENROUTER_API_KEY is required")`) deteniendo el servidor backend si no se detectaba una clave de API configurada.

* **Por qué decidí RECHAZARLO**:
  1. **Nginx**: Añadía sobrecarga estructural innecesaria para un proyecto mono-nodo de evaluación. FastAPI maneja archivos estáticos eficientemente para este alcance.
  2. **Exception en Startup**: El enunciado del challenge indicaba explícitamente:
     > *"Pensá qué debería pasar si alguien levanta el proyecto sin configurar la key: que el stack explote con un stacktrace no es una gran experiencia."*
     Rechacé el `raise ValueError` y en su lugar implementé el **Pattern Strategy con `MockLLMService`**. De esta manera, el usuario que clona e invoca `docker compose up` obtiene una aplicación totalmente operativa de inmediato, visualizando un indicador en la UI de que el sistema está funcionando en "Modo Mock".

---

## ⚙️ Ejecución de Linter y Tests Locales

Si deseas correr los tests y linters fuera de Docker:

```bash
# Crear entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Ejecutar Linter (Ruff)
ruff check .

# Ejecutar Tests (Pytest)
pytest -v
```

---

## 📝 Licencia & Autor
Desarrollado para el Code Challenge por **Juan Ignacio Mancini**.
