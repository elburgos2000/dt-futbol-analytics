from typing import Dict, Any, Tuple
import database

def process_match_result(partido_id: str, resultado_real: str) -> Tuple[bool, str]:
    resultado_real = resultado_real.upper().strip()
    if resultado_real not in ["1", "X", "2"]:
        return False, "Resultado inválido. Debe ser '1' (Gana Equipo A), 'X' (Empate) o '2' (Gana Equipo B)."
        
    record = database.register_result(partido_id, resultado_real)
    if not record:
        return False, f"No se encontró ningún registro de predicción para el partido_id '{partido_id}'."
        
    prediccion = record["prediccion"]
    eq_a = record["equipo_a"]
    eq_b = record["equipo_b"]
    raw_data = record["raw_data"]
    acierto = record["acierto"]
    
    if acierto == 1:
        msg = (
            f"🎯 **[FEEDBACK LOOP - RESULTADO REGISTRADO]**\n\n"
            f"• Partido ID: `{partido_id}` ({eq_a} vs {eq_b})\n"
            f"• Predicción: **{prediccion}** | Resultado Real: **{resultado_real}**\n"
            f"• Estado: ✅ **ACIERTO CONFIRMADO**\n\n"
            f"_Resumen Táctico:_ El modelo detectó las dinámicas del encuentro con precisión quirúrgica. "
            f"Se mantienen los pesos actuales del sistema."
        )
        return True, msg
        
    # Auto-análisis en caso de fallo (Feedback Loop)
    weights = database.get_feature_weights()
    stats_a = raw_data["equipo_a"]
    stats_b = raw_data["equipo_b"]
    
    # Identificar la métrica que más desfavoreció el resultado real
    new_weights = weights.copy()
    reason = ""
    
    metrics = ["distancia", "part_goles", "prep", "faltas", "conv"]
    
    if resultado_real == "X":
        # El partido terminó en empate no previsto
        # Aumentar peso de la paridad en preparación y control de faltas
        new_weights["prep"] = round(new_weights.get("prep", 1.0) * 1.08, 3)
        new_weights["faltas"] = round(new_weights.get("faltas", 1.0) * 1.05, 3)
        reason = "Falta de peso en la neutralización del juego de medio campo (Prep) y faltas tácticas que forzaron el empate."
    elif resultado_real == "1":
        # Ganó Equipo A inesperadamente. Ver en qué superaba A a B.
        best_diff_metric = max(metrics, key=lambda m: stats_a[m] - stats_b[m])
        new_weights[best_diff_metric] = round(new_weights.get(best_diff_metric, 1.0) * 1.10, 3)
        reason = f"Sesgo de subestimación en la variable '{best_diff_metric}' a favor de {eq_a}."
    elif resultado_real == "2":
        # Ganó Equipo B inesperadamente. Ver en qué superaba B a A.
        best_diff_metric = max(metrics, key=lambda m: stats_b[m] - stats_a[m])
        new_weights[best_diff_metric] = round(new_weights.get(best_diff_metric, 1.0) * 1.10, 3)
        reason = f"Sesgo de subestimación en la variable '{best_diff_metric}' a favor de {eq_b}."
        
    analisis_text = f"Fallo de predicción ({prediccion} vs {resultado_real}). {reason}"
    
    # Guardar nuevos pesos y registro de feedback
    database.update_feature_weights(new_weights, partido_id, prediccion, resultado_real, analisis_text)
    
    msg = (
        f"⚠️ **[FEEDBACK LOOP - AUTO-ANÁLISIS DE FALLO]**\n\n"
        f"• Partido ID: `{partido_id}` ({eq_a} vs {eq_b})\n"
        f"• Predicción: **{prediccion}** | Resultado Real: **{resultado_real}**\n"
        f"• Estado: ❌ **ERRÓNEA**\n\n"
        f"📊 **Auto-Análisis de Inferencia:**\n"
        f"_{reason}_\n\n"
        f"⚙️ **Ajuste de Pesos Aplicado:**\n"
        + "\n".join([f"  - `{m}`: {weights.get(m, 1.0):.2f} ➔ {new_weights.get(m, 1.0):.2f}" for m in metrics])
        + "\n\n_La lógica predictiva ha sido recalibrada para el siguiente partido._"
    )
    
    return True, msg
