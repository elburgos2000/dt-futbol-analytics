# ⚽ DT Fútbol Analytics & Tactical AI Prediction Engine

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![SQLite](https://img.shields.io/badge/Database-SQLite%203-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Telegram](https://img.shields.io/badge/Bot-Telegram%20API-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://telegram.org)
[![Docker](https://img.shields.io/badge/Deploy-Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

Sistema integral de analítica táctica deportiva, modelado predictivo probabilístico y seguimiento en tiempo real para encuentros de fútbol profesional, integrado con bot automatizado en Telegram y ciclo continuo de retroalimentación de sesgo (*Feedback Loop Engine*).

---

## 🎯 Arquitectura del Sistema

```mermaid
flowchart TD
    subgraph Ingesta_y_Normalizacion["1. Ingesta & Normalización"]
        LiveFeed["Telemetría de Partido / Feed en Vivo"] --> Normalizer["normalizer.py (Z-Score & Feature Engineering)"]
    end

    subgraph Motor_Predictivo["2. Motor Táctico & Heurística"]
        Normalizer --> TacticalEngine["tactical_engine.py (Algoritmo de Pesos Ponderados)"]
        FeatureWeights[("Pesos de Métricas: Goles, Faltas, Distancia")] --> TacticalEngine
        TacticalEngine --> Prediccion["Predicción: Probabilidad & Factor Clave"]
    end

    subgraph Persistencia_y_Tracking["3. Persistencia & Tracking"]
        Prediccion --> DB[("SQLite Database: dt_futbol.db")]
        DB --> LiveTracker["live_tracker.py (Monitor Minuto a Minuto)"]
    end

    subgraph Retroalimentacion["4. Canal de Salida & Feedback Loop"]
        LiveTracker --> TelegramBot["Telegram Bot (Notificaciones Push a Usuarios)"]
        ResultadoReal["Resultado Final del Encuentro"] --> FeedbackEngine["feedback_loop.py (Análisis de Sesgo y Reajuste)"]
        FeedbackEngine --> FeatureWeights
    end
```

---

## 🚀 Características Técnicas

- **🧠 Motor Ponderado Heurístico:** Evalúa métricas avanzadas por encuentro (tasa de conversión, distancia de recorrido, faltas tácticas, historial de goles recientes) asignando ponderaciones dinámicas parametrizadas.
- **🔄 Bucle de Aprendizaje y Feedback Continuo:** Si una predicción diverge del resultado real, el módulo `feedback_loop.py` diagnostica el sesgo cognitivo/estadístico y ajusta la tabla `feature_weights` para refinar predicciones subsecuentes.
- **⏱️ Rastreador en Vivo (Live Tracker):** Monitorea eventos minuto a minuto durante los partidos activos y despacha alertas automáticas al canal de Telegram asociado.
- **💾 Modelo Relacional Ligero:** Estructura en SQLite con índices en `partido_id`, `chat_id` y tablas dedicadas de auditoría `feedback_logs`.

---

## 🛠️ Instalación y Uso

### 1. Clonar el repositorio
```bash
git clone https://github.com/elburgos2000/dt-futbol-analytics.git
cd dt-futbol-analytics
```

### 2. Configurar entorno virtual
```bash
python -m venv .venv
# En Windows:
.venv\Scripts\activate
# En Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Variables de entorno
Copiar plantilla de configuración y asignar credenciales:
```bash
cp .env.example .env
```

### 4. Ejecución del Bot
```bash
python bot.py
```

---

## 👨‍💻 Autor

**Brayan Burgos Palomino**  
- **Rol:** Software Engineer & BI Analyst  
- **GitHub:** [@elburgos2000](https://github.com/elburgos2000)  
- **Email:** [motocrossloco@gmail.com](mailto:motocrossloco@gmail.com)  
