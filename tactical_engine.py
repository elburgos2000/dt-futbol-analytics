import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from sklearn.ensemble import RandomForestClassifier
import database

def calculate_indices(team_stats: dict, weights: Dict[str, float]) -> Tuple[float, float, float, float]:
    dist = team_stats["distancia"] * weights.get("distancia", 1.0)
    part_goles = team_stats["part_goles"] * weights.get("part_goles", 1.0)
    prep = team_stats["prep"] * weights.get("prep", 1.0)
    faltas = team_stats["faltas"] * weights.get("faltas", 1.0)
    conv = team_stats["conv"] * weights.get("conv", 1.0)
    
    # IEO: Índice de Eficiencia Ofensiva (Part. Goles * Conversión)
    ieo = part_goles * (1.0 + conv)
    
    # ICJ: Índice de Control de Juego (Contribución Preparatoria * Distancia relativa)
    icj = prep * (dist / 100.0)
    
    # IIF: Índice de Intensidad y Faltas (Faltas corregidas por distancia)
    iif = (faltas / (dist / 10.0 + 1.0))
    
    # Combined score
    score = (ieo * 0.45) + (icj * 0.40) - (iif * 0.15)
    return ieo, icj, iif, score

def analyze_match(match_data: dict) -> dict:
    weights = database.get_feature_weights()
    eq_a = match_data["equipo_a"]
    eq_b = match_data["equipo_b"]
    
    history_count = database.get_history_count()
    
    if history_count >= 15:
        # Enfoque Machine Learning (Random Forest)
        prediction, confidence, determinant_factor, method = run_ml_model(match_data, weights)
    else:
        # Enfoque Comparativo Táctico (IEO, ICJ, IIF)
        prediction, confidence, determinant_factor, method = run_comparative_tactical(match_data, weights)

    # Guardar predicción en la base de datos
    database.save_prediction(
        partido_id=match_data["partido_id"],
        equipo_a=eq_a["nombre"],
        equipo_b=eq_b["nombre"],
        raw_data=match_data,
        prediccion=prediction,
        confianza=confidence,
        factor_determinante=determinant_factor
    )
    
    ieo_a, icj_a, iif_a, score_a = calculate_indices(eq_a, weights)
    ieo_b, icj_b, iif_b, score_b = calculate_indices(eq_b, weights)
    
    return {
        "partido_id": match_data["partido_id"],
        "equipo_a": eq_a["nombre"],
        "equipo_b": eq_b["nombre"],
        "prediccion": prediction,
        "confianza": round(confidence * 100, 1),
        "factor_determinante": determinant_factor,
        "metodo": method,
        "indices": {
            "equipo_a": {"ieo": round(ieo_a, 2), "icj": round(icj_a, 2), "iif": round(iif_a, 2), "score": round(score_a, 2)},
            "equipo_b": {"ieo": round(ieo_b, 2), "icj": round(icj_b, 2), "iif": round(iif_b, 2), "score": round(score_b, 2)}
        },
        "historial_n": history_count
    }

def run_comparative_tactical(match_data: dict, weights: Dict[str, float]) -> Tuple[str, float, str, str]:
    eq_a = match_data["equipo_a"]
    eq_b = match_data["equipo_b"]
    
    ieo_a, icj_a, iif_a, score_a = calculate_indices(eq_a, weights)
    ieo_b, icj_b, iif_b, score_b = calculate_indices(eq_b, weights)
    
    delta_score = score_a - score_b
    max_score = max(abs(score_a), abs(score_b), 1.0)
    ratio = abs(delta_score) / max_score
    
    if ratio < 0.12:
        prediction = "X"
        confidence = 0.50 + (0.12 - ratio)
    elif delta_score > 0:
        prediction = "1"
        confidence = min(0.55 + ratio * 0.5, 0.92)
    else:
        prediction = "2"
        confidence = min(0.55 + ratio * 0.5, 0.92)
        
    # Determinar qué métrica inclina la balanza
    metric_diffs = {}
    metric_labels = {
        "conv": "Tasa de Conversión / Efectividad",
        "part_goles": "Participación Directa en Goles",
        "prep": "Contribución Preparatoria (Generación)",
        "distancia": "Distancia Recorrida (Despliegue Físico)",
        "faltas": "Control de Faltas e Intensidad Defensiva"
    }
    
    for metric in ["distancia", "part_goles", "prep", "faltas", "conv"]:
        w = weights.get(metric, 1.0)
        v_a = eq_a[metric]
        v_b = eq_b[metric]
        if metric == "faltas":
            # Menos faltas es mejor para el flujo de juego, mayor es penalizado
            diff = (v_b - v_a) * w
        else:
            diff = (v_a - v_b) * w
        metric_diffs[metric] = diff
        
    # Ordenar por magnitud de la diferencia ponderada
    top_metric = max(metric_diffs.keys(), key=lambda k: abs(metric_diffs[k]))
    best_team = eq_a["nombre"] if metric_diffs[top_metric] > 0 else eq_b["nombre"]
    determinant_factor = f"{metric_labels[top_metric]} favorable a {best_team}"
    
    return prediction, confidence, determinant_factor, "Análisis Comparativo Táctico (IEO/ICJ/IIF)"

def run_ml_model(match_data: dict, weights: Dict[str, float]) -> Tuple[str, float, str, str]:
    historical = database.get_historical_matches()
    
    X = []
    y = []
    
    metrics = ["distancia", "part_goles", "prep", "faltas", "conv"]
    
    for h in historical:
        raw = h["raw_data"]
        res = h["resultado_real"]
        e_a = raw["equipo_a"]
        e_b = raw["equipo_b"]
        
        feats = [(e_a[m] - e_b[m]) * weights.get(m, 1.0) for m in metrics]
        X.append(feats)
        y.append(res)
        
    clf = RandomForestClassifier(n_estimators=50, random_state=42)
    clf.fit(X, y)
    
    curr_a = match_data["equipo_a"]
    curr_b = match_data["equipo_b"]
    curr_feats = np.array([(curr_a[m] - curr_b[m]) * weights.get(m, 1.0) for m in metrics]).reshape(1, -1)
    
    pred = clf.predict(curr_feats)[0]
    probs = clf.predict_proba(curr_feats)[0]
    conf = float(np.max(probs))
    
    importances = clf.feature_importances_
    top_feat_idx = int(np.argmax(importances * np.abs(curr_feats[0])))
    top_metric = metrics[top_feat_idx]
    
    metric_labels = {
        "conv": "Tasa de Conversión",
        "part_goles": "Participación en Goles",
        "prep": "Contribución Preparatoria",
        "distancia": "Despliegue Físico (Distancia)",
        "faltas": "Control de Faltas"
    }
    
    favor_team = curr_a["nombre"] if curr_feats[0][top_feat_idx] > 0 else curr_b["nombre"]
    determinant_factor = f"Inferencia ML: {metric_labels[top_metric]} diferencial a favor de {favor_team}"
    
    return pred, conf, determinant_factor, "Modelo Random Forest ML"
