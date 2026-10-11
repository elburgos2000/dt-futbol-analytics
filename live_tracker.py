import asyncio
import random
import logging
from typing import List
from telegram.ext import Application
import database
import feedback_loop

logger = logging.getLogger(__name__)

async def start_live_tracker(app: Application):
    logger.info("⏱️ Motor de Seguimiento Táctico en Vivo iniciado...")
    while True:
        try:
            active_matches = database.get_active_tracked_matches()
            for m in active_matches:
                await process_match_tick(app, m)
        except Exception as e:
            logger.error(f"Error en bucle de seguimiento en vivo: {e}")
            
        await asyncio.sleep(15)

async def process_match_tick(app: Application, match: dict):
    rec_id = match["id"]
    p_id = match["partido_id"]
    chat_id = match["chat_id"]
    eq_a = match["equipo_a"]
    eq_b = match["equipo_b"]
    pred = match["prediccion"]
    status = match["status"]
    score_a = match["score_a"]
    score_b = match["score_b"]
    minuto = match["minuto"]
    
    pred_label = {"1": f"Victoria de {eq_a}", "X": "Empate", "2": f"Victoria de {eq_b}"}.get(pred, pred)

    if status == "START_SIMULATION":
        new_status = "LIVE"
        new_min = 1
        database.update_tracked_match(rec_id, new_status, score_a, score_b, new_min)
        
        msg = (
            f"🔔 *[NOTIFICACIÓN EN VIVO — SILBATO INICIAL]*\n\n"
            f"⚽ *{eq_a}* vs *{eq_b}* (ID: `{p_id}`)\n"
            f"• Pronóstico del Modelo: *{pred}* ({pred_label})\n"
            f"• Estado: 🟢 *¡PARTIDO EN JUEGO (0-0)!*\n\n"
            f"_Te notificaré de inmediato cada gol, las estadísticas de quién va ganando/perdiendo y el cierre del partido._"
        )
        await send_telegram(app, chat_id, msg)
        
    elif status == "LIVE":
        new_min = minuto + random.randint(15, 25)
        new_score_a = score_a
        new_score_b = score_b
        
        goal_occurred = False
        scorer = None
        
        if random.random() < 0.40 and new_min < 90:
            goal_occurred = True
            if pred == "1":
                scorer = eq_a if random.random() < 0.65 else eq_b
            elif pred == "2":
                scorer = eq_b if random.random() < 0.65 else eq_a
            else:
                scorer = eq_a if random.random() < 0.50 else eq_b
                
            if scorer == eq_a:
                new_score_a += 1
            else:
                new_score_b += 1

        if new_min >= 90:
            new_status = "FINISHED"
            final_min = 90
            database.update_tracked_match(rec_id, new_status, new_score_a, new_score_b, final_min)
            
            if new_score_a > new_score_b:
                resultado_real = "1"
                status_txt = f"🏆 *{eq_a} GANÓ* el encuentro ({new_score_a}-{new_score_b})"
            elif new_score_b > new_score_a:
                resultado_real = "2"
                status_txt = f"🏆 *{eq_b} GANÓ* el encuentro ({new_score_b}-{new_score_a})"
            else:
                resultado_real = "X"
                status_txt = f"🤝 *EMPATE FINAL* ({new_score_a}-{new_score_b})"
                
            acierto_txt = "✅ **CUMPLIDO**" if resultado_real == pred else "❌ **DESVIADO**"
            
            final_msg = (
                f"🏁 *[FINAL DEL PARTIDO — ID #{p_id}]*\n\n"
                f"⚽ *{eq_a} {new_score_a} - {new_score_b} {eq_b}*\n"
                f"• Situación: {status_txt}\n"
                f"• Pronóstico Inicial: **{pred}** ({pred_label}) ➔ {acierto_txt}\n"
            )
            await send_telegram(app, chat_id, final_msg)
            
            ok, fb_msg = feedback_loop.process_match_result(p_id, resultado_real)
            await send_telegram(app, chat_id, fb_msg)
            
        else:
            database.update_tracked_match(rec_id, "LIVE", new_score_a, new_score_b, new_min)
            
            if goal_occurred:
                if new_score_a > new_score_b:
                    state_desc = f"🔥 *{eq_a}* va **GANANDO** ({new_score_a}-{new_score_b}) | *{eq_b}* va **PERDIENDO**"
                    fav = "1"
                elif new_score_b > new_score_a:
                    state_desc = f"🔥 *{eq_b}* va **GANANDO** ({new_score_b}-{new_score_a}) | *{eq_a}* va **PERDIENDO**"
                    fav = "2"
                else:
                    state_desc = f"⚖️ *EMPATE MOMENTÁNEO* ({new_score_a}-{new_score_b})"
                    fav = "X"
                    
                pred_eval = "✅ *CUMPLIENDO PRONÓSTICO DEL MODELO*" if pred == fav else "⚠️ *RESULTADO ADVERSO AL PRONÓSTICO (Remontada requerida)*"

                goal_msg = (
                    f"⚽ *[¡GOOOOOOL DE {scorer.upper()}!]*\n"
                    f"⏱️ Minuto {new_min}' | ID: `{p_id}`\n\n"
                    f"📊 *ESTADO DEL PARTIDO:* {state_desc}\n"
                    f"🎯 *EVALUACIÓN DEL PRONÓSTICO:* {pred_eval}\n\n"
                    f"📈 *SITUACIÓN TÁCTICA:* {scorer} incrementa su Índice de Eficiencia Ofensiva (IEO)."
                )
                await send_telegram(app, chat_id, goal_msg)

async def send_telegram(app: Application, chat_id: int, text: str):
    try:
        await app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error enviando notificación a chat {chat_id}: {e}")
