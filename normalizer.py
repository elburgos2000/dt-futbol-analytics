import json
import re
import uuid
import hashlib
from typing import Dict, Any, Tuple, Optional, List, Union

REQUIRED_METRICS = ["distancia", "part_goles", "prep", "faltas", "conv"]

METRIC_ALIASES = {
    "distancia": ["distancia", "distancia_km", "dist", "km_recorridos"],
    "part_goles": ["part_goles", "participacion_goles", "part_gol", "goles_contrib", "goles"],
    "prep": ["prep", "contribucion_prep", "preparacion", "pases_clave", "prep_goles"],
    "faltas": ["faltas", "faltas_cometidas", "fouls"],
    "conv": ["conv", "tasa_conversion", "conversion", "tasa_conv", "efectividad"]
}

DAYS_PATTERN = r"(?:Día|Equipos|DíaEquipos|Lun|Mar|Mié|Jue|Vie|Sáb|Dom|Mon|Tue|Wed|Thu|Fri|Sat|Sun)"

def canonicalize_metric(key: str) -> Optional[str]:
    k = key.lower().strip().replace(" ", "_")
    for canonical, aliases in METRIC_ALIASES.items():
        if k in aliases or any(alias in k for alias in aliases):
            return canonical
    return None

def generate_estimated_metrics(team_name: str, is_home: bool = True) -> dict:
    """
    Genera un perfil métrico táctico único y determinista para un equipo 
    basado en su nombre y condición de local/visitante.
    """
    h = int(hashlib.md5(team_name.lower().encode('utf-8')).hexdigest()[:8], 16)
    
    # Rango de valores sintéticos realistas
    home_bonus = 1.03 if is_home else 0.97
    
    distancia = round((102.0 + (h % 100) / 10.0) * home_bonus, 1)        # 102 - 112 km
    part_goles = round((0.40 + (h % 60) / 100.0) * home_bonus, 2)       # 0.40 - 1.00
    prep = round((8.0 + (h % 90) / 10.0) * home_bonus, 1)               # 8.0 - 17.0
    faltas = round(9.0 + (h % 70) / 10.0, 1)                           # 9.0 - 16.0
    conv = round((0.08 + (h % 15) / 100.0) * home_bonus, 2)             # 0.08 - 0.23
    
    return {
        "nombre": team_name,
        "distancia": distancia,
        "part_goles": part_goles,
        "prep": prep,
        "faltas": faltas,
        "conv": conv
    }

def extract_matches_from_text(raw_text: str) -> List[Tuple[str, str]]:
    matches = []
    seen = set()
    
    raw_text_clean = re.sub(rf"(?<=[a-zA-Z0-9\)])({DAYS_PATTERN}(?:[A-Z\s,]|$))", r"\n\1", raw_text)
    lines = raw_text_clean.splitlines()
    
    for line in lines:
        line = line.strip()
        if not line or "vs" not in line.lower() or line.lower().startswith("día"):
            continue
            
        match_vs = re.search(r"(.+?)\s+(?:vs\.?|v\.?|-)\s+(.+)", line, re.IGNORECASE)
        if match_vs:
            part_a = match_vs.group(1).strip()
            part_b = match_vs.group(2).strip()
            
            eq_a = re.sub(rf"^(?:{DAYS_PATTERN}\s*,\s*|{DAYS_PATTERN}\s+|\d+[\.\,\-\)]\s*)+", "", part_a, flags=re.IGNORECASE).strip()
            eq_b = re.sub(rf"(?:,\s*{DAYS_PATTERN}|\s+{DAYS_PATTERN}|\d+[\.\,\-\)]\s*)+$", "", part_b, flags=re.IGNORECASE).strip()
            
            eq_a = re.sub(r"^[^\w\(\)]+", "", eq_a).strip()
            eq_b = re.sub(r"[^\w\(\)]+$", "", eq_b).strip()
            
            if eq_a and eq_b and len(eq_a) > 1 and len(eq_b) > 1:
                pair = (eq_a, eq_b)
                if pair not in seen:
                    seen.add(pair)
                    matches.append(pair)
                
    return matches

def parse_input_data(raw_text: str) -> Tuple[Optional[Union[dict, List[dict]]], Optional[str]]:
    raw_text = raw_text.strip()
    
    # 1. Intentar como JSON directo
    if raw_text.startswith("{") and raw_text.endswith("}"):
        try:
            data = json.loads(raw_text)
            return normalize_dict(data)
        except json.JSONDecodeError as e:
            return None, f"Error decodificando JSON: {str(e)}"
            
    # 2. Intentar buscar JSON dentro de bloques de código markdown (```json ... ```)
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return normalize_dict(data)
        except json.JSONDecodeError as e:
            return None, f"Error decodificando JSON en bloque: {str(e)}"

    # 3. Intentar parsear como Tabla Markdown con métricas explícitas
    if "|" in raw_text:
        parsed_md = parse_markdown_table(raw_text)
        if parsed_md:
            return normalize_dict(parsed_md)

    # 4. Detectar lista de partidos cruda (Equipo A vs Equipo B)
    extracted_fixtures = extract_matches_from_text(raw_text)
    if extracted_fixtures:
        batch_matches = []
        for idx, (eq_a_name, eq_b_name) in enumerate(extracted_fixtures, 1):
            p_id = f"M{idx:02d}"
            eq_a = generate_estimated_metrics(eq_a_name, is_home=True)
            eq_b = generate_estimated_metrics(eq_b_name, is_home=False)
            batch_matches.append({
                "partido_id": p_id,
                "equipo_a": eq_a,
                "equipo_b": eq_b,
                "estimado": True
            })
        return batch_matches, None
            
    return None, "Formato no reconocido. Envíame un JSON con métricas, una tabla Markdown o la lista de partidos 'Equipo A vs Equipo B'."

def parse_markdown_table(text: str) -> Optional[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip() and "|" in line]
    if len(lines) < 3:
        return None
    
    headers = [col.strip() for col in lines[0].split("|")[1:-1]]
    if len(headers) < 3:
        return None
    
    equipo_a_nombre = headers[1] if headers[1] else "Equipo A"
    equipo_b_nombre = headers[2] if headers[2] else "Equipo B"
    
    equipo_a_metrics = {}
    equipo_b_metrics = {}
    
    for line in lines[2:]:
        cols = [col.strip() for col in line.split("|")[1:-1]]
        if len(cols) >= 3:
            metric_raw = cols[0]
            val_a = parse_number(cols[1])
            val_b = parse_number(cols[2])
            
            c_metric = canonicalize_metric(metric_raw)
            if c_metric and val_a is not None and val_b is not None:
                equipo_a_metrics[c_metric] = val_a
                equipo_b_metrics[c_metric] = val_b
                
    if len(equipo_a_metrics) == 0 or len(equipo_b_metrics) == 0:
        return None
        
    return {
        "partido_id": str(uuid.uuid4())[:8],
        "equipo_a": {"nombre": equipo_a_nombre, **equipo_a_metrics},
        "equipo_b": {"nombre": equipo_b_nombre, **equipo_b_metrics}
    }

def parse_number(val_str: str) -> Optional[float]:
    clean = re.sub(r"[^\d\.]", "", val_str)
    try:
        return float(clean)
    except ValueError:
        return None

def normalize_dict(data: dict) -> Tuple[Optional[dict], Optional[str]]:
    if "equipo_a" not in data or "equipo_b" not in data:
        return None, "El JSON debe incluir los objetos 'equipo_a' y 'equipo_b'."
        
    p_id = str(data.get("partido_id", str(uuid.uuid4())[:8]))
    
    eq_a_raw = data["equipo_a"]
    eq_b_raw = data["equipo_b"]
    
    eq_a = {"nombre": eq_a_raw.get("nombre", "Equipo A")}
    eq_b = {"nombre": eq_b_raw.get("nombre", "Equipo B")}
    
    missing_a = []
    missing_b = []
    
    for metric in REQUIRED_METRICS:
        val_a = None
        for key, val in eq_a_raw.items():
            if canonicalize_metric(key) == metric:
                val_a = val
                break
        if val_a is None:
            missing_a.append(metric)
        else:
            eq_a[metric] = float(val_a)

        val_b = None
        for key, val in eq_b_raw.items():
            if canonicalize_metric(key) == metric:
                val_b = val
                break
        if val_b is None:
            missing_b.append(metric)
        else:
            eq_b[metric] = float(val_b)
            
    if missing_a or missing_b:
        missing_total = list(set(missing_a + missing_b))
        return None, f"Faltan métricas obligatorias en los datos: {', '.join(missing_total)}. Se requieren: {', '.join(REQUIRED_METRICS)}"
        
    return {
        "partido_id": p_id,
        "equipo_a": eq_a,
        "equipo_b": eq_b
    }, None
