import sqlite3
import json
import os
from typing import Dict, Any, List, Optional, Tuple

DB_NAME = os.getenv("DB_PATH", "dt_futbol.db")

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partido_id TEXT UNIQUE,
            equipo_a TEXT NOT NULL,
            equipo_b TEXT NOT NULL,
            raw_data TEXT NOT NULL,
            prediccion TEXT NOT NULL,
            confianza REAL,
            factor_determinante TEXT,
            resultado_real TEXT DEFAULT NULL,
            acierto INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feature_weights (
            metric_name TEXT PRIMARY KEY,
            weight REAL NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partido_id TEXT NOT NULL,
            prediccion TEXT NOT NULL,
            resultado_real TEXT NOT NULL,
            analisis_sesgo TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracked_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partido_id TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            equipo_a TEXT NOT NULL,
            equipo_b TEXT NOT NULL,
            prediccion TEXT NOT NULL,
            status TEXT DEFAULT 'SCHEDULED',
            score_a INTEGER DEFAULT 0,
            score_b INTEGER DEFAULT 0,
            minuto INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(partido_id, chat_id)
        )
    """)
    
    default_metrics = {
        "distancia": 1.0,
        "part_goles": 1.5,
        "prep": 1.2,
        "faltas": 0.8,
        "conv": 1.8
    }
    for metric, w in default_metrics.items():
        cursor.execute("""
            INSERT OR IGNORE INTO feature_weights (metric_name, weight) VALUES (?, ?)
        """, (metric, w))
        
    conn.commit()
    conn.close()

def save_prediction(partido_id: str, equipo_a: str, equipo_b: str, raw_data: dict, prediccion: str, confianza: float, factor_determinante: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO matches (partido_id, equipo_a, equipo_b, raw_data, prediccion, confianza, factor_determinante)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (partido_id, equipo_a, equipo_b, json.dumps(raw_data), prediccion, confianza, factor_determinante))
    conn.commit()
    conn.close()

def track_matches_for_chat(chat_id: int, partido_ids: List[str]) -> Tuple[List[dict], List[str]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    tracked = []
    not_found = []
    
    for p_id in partido_ids:
        cursor.execute("SELECT partido_id, equipo_a, equipo_b, prediccion FROM matches WHERE partido_id = ?", (p_id.strip(),))
        row = cursor.fetchone()
        if row:
            p_id_match, eq_a, eq_b, pred = row
            cursor.execute("""
                INSERT OR REPLACE INTO tracked_matches (partido_id, chat_id, equipo_a, equipo_b, prediccion, status, score_a, score_b, minuto)
                VALUES (?, ?, ?, ?, ?, 'SCHEDULED', 0, 0, 0)
            """, (p_id_match, chat_id, eq_a, eq_b, pred))
            tracked.append({"partido_id": p_id_match, "equipo_a": eq_a, "equipo_b": eq_b, "prediccion": pred})
        else:
            not_found.append(p_id)
            
    conn.commit()
    conn.close()
    return tracked, not_found

def start_match_simulation(chat_id: int, partido_ids: List[str]) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    started = []
    for p_id in partido_ids:
        cursor.execute("""
            UPDATE tracked_matches
            SET status = 'START_SIMULATION'
            WHERE partido_id = ? AND chat_id = ?
        """, (p_id, chat_id))
        if cursor.rowcount > 0:
            started.append(p_id)
    conn.commit()
    conn.close()
    return started

def get_active_tracked_matches() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, partido_id, chat_id, equipo_a, equipo_b, prediccion, status, score_a, score_b, minuto
        FROM tracked_matches
        WHERE status IN ('START_SIMULATION', 'LIVE')
    """)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "partido_id": r[1],
            "chat_id": r[2],
            "equipo_a": r[3],
            "equipo_b": r[4],
            "prediccion": r[5],
            "status": r[6],
            "score_a": r[7],
            "score_b": r[8],
            "minuto": r[9]
        })
    return result

def update_tracked_match(record_id: int, status: str, score_a: int, score_b: int, minuto: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tracked_matches
        SET status = ?, score_a = ?, score_b = ?, minuto = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, score_a, score_b, minuto, record_id))
    conn.commit()
    conn.close()

def get_all_matches_in_db() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT partido_id, equipo_a, equipo_b, prediccion, resultado_real FROM matches ORDER BY id DESC LIMIT 30")
    rows = cursor.fetchall()
    conn.close()
    return [{"partido_id": r[0], "equipo_a": r[1], "equipo_b": r[2], "prediccion": r[3], "resultado_real": r[4]} for r in rows]

def register_result(partido_id: str, resultado_real: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, equipo_a, equipo_b, raw_data, prediccion FROM matches WHERE partido_id = ?", (partido_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    
    match_db_id, equipo_a, equipo_b, raw_data_str, prediccion = row
    acierto = 1 if prediccion == resultado_real else 0
    
    cursor.execute("""
        UPDATE matches SET resultado_real = ?, acierto = ? WHERE partido_id = ?
    """, (resultado_real, acierto, partido_id))
    conn.commit()
    conn.close()
    
    return {
        "partido_id": partido_id,
        "equipo_a": equipo_a,
        "equipo_b": equipo_b,
        "raw_data": json.loads(raw_data_str),
        "prediccion": prediccion,
        "resultado_real": resultado_real,
        "acierto": acierto
    }

def get_feature_weights() -> Dict[str, float]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT metric_name, weight FROM feature_weights")
    rows = cursor.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

def update_feature_weights(new_weights: Dict[str, float], partido_id: str, prediccion: str, resultado_real: str, analisis: str):
    conn = get_connection()
    cursor = conn.cursor()
    for metric, w in new_weights.items():
        cursor.execute("UPDATE feature_weights SET weight = ? WHERE metric_name = ?", (w, metric))
    cursor.execute("""
        INSERT INTO feedback_logs (partido_id, prediccion, resultado_real, analisis_sesgo)
        VALUES (?, ?, ?, ?)
    """, (partido_id, prediccion, resultado_real, analisis))
    conn.commit()
    conn.close()

def get_history_count() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM matches WHERE resultado_real IS NOT NULL")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_historical_matches() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT raw_data, resultado_real FROM matches WHERE resultado_real IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "raw_data": json.loads(r[0]),
            "resultado_real": r[1]
        })
    return result

def get_stats_summary() -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN acierto = 1 THEN 1 ELSE 0 END) FROM matches WHERE resultado_real IS NOT NULL")
    total, aciertos = cursor.fetchone()
    conn.close()
    total = total or 0
    aciertos = aciertos or 0
    tasa = (aciertos / total * 100) if total > 0 else 0.0
    return {"total": total, "aciertos": aciertos, "tasa_acierto": round(tasa, 1)}
