import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import database
import normalizer
import tactical_engine
import feedback_loop

def test_full_flow():
    print("--- [TEST 1: Inicialización de DB] ---")
    if os.path.exists("test_dt_futbol.db"):
        os.remove("test_dt_futbol.db")
    os.environ["DB_PATH"] = "test_dt_futbol.db"
    database.init_db()
    print("DB inicializada.")

    print("\n--- [TEST 2: Lote de Partidos Crudos] ---")
    user_raw_list = """Día,Equipos
Lun,Young Boys II vs FC Solothurn
Lun,Redbridge vs Welwyn Garden City"""

    batch_matches, err_res = normalizer.parse_input_data(user_raw_list)
    assert err_res is None
    assert len(batch_matches) == 2
    
    for m in batch_matches:
        analysis = tactical_engine.analyze_match(m)
        assert analysis["prediccion"] in ["1", "X", "2"]

    print("\n--- [TEST 3: Confirmación de Programación y Simulación] ---")
    tracked, not_found = database.track_matches_for_chat(chat_id=123456, partido_ids=["M01", "M02"])
    assert len(tracked) == 2
    print(f"Partidos registrados en agenda programada: {len(tracked)}")

    started = database.start_match_simulation(chat_id=123456, partido_ids=["M01", "M02"])
    assert len(started) == 2
    
    active = database.get_active_tracked_matches()
    assert len(active) == 2
    print("Módulo de programación y simulación verificado correctamente!")
    print("Tests finalizados con 100% de éxito.")

if __name__ == "__main__":
    test_full_flow()
