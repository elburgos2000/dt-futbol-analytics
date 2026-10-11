import os
import re
import asyncio
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

import database
import normalizer
import tactical_engine
import feedback_loop
import live_tracker

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🧠 *DT Futbol Statistics — Núcleo Operativo Táctico*\n\n"
        "Soy tu analista táctico de alto nivel con menú interactivo de selección de partidos.\n\n"
        "📋 *Cómo Operar:*\n"
        "1. Pega tu lista de partidos (ej. `Lun,Equipo A vs Equipo B`).\n"
        "2. Te mostraré el pronóstico masivo y una **Botonera Interactiva** en Telegram para programar los encuentros que deseas seguir.\n"
        "3. Para iniciar la simulación en tiempo real de partidos confirmados, usa `/simular todos` o `/simular M14`.\n\n"
        "📌 *Comandos Disponibles:*\n"
        "• `/confirmar` : Abrir menú interactivo de selección de partidos.\n"
        "• `/simular <partido_ids | todos>` : Iniciar simulación/monitoreo en vivo de encuentros seleccionados.\n"
        "• `/resultado <partido_id> <1|X|2>` : Registrar resultado manual para Feedback Loop.\n"
        "• `/stats` : Rendimiento del modelo e historial."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = database.get_stats_summary()
    weights = database.get_feature_weights()
    history_count = database.get_history_count()
    
    msg = (
        "📈 *[REPORTE DE RENDIMIENTO DEL MODELO]*\n\n"
        f"• *Partidos en Base de Datos:* {stats['total']}\n"
        f"• *Partidos Validados (Feedback):* {history_count}\n"
        f"• *Predicciones Acertadas:* {stats['aciertos']}\n"
        f"• *Tasa de Acierto Global:* *{stats['tasa_acierto']}%*\n\n"
        "⚖️ *Matriz Actual de Pesos de Métricas:*\n"
        + "\n".join([f"  - `{m}`: {w:.2f}" for m, w in weights.items()])
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def seguir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matches = database.get_all_matches_in_db()
    if not matches:
        await update.message.reply_text("No hay partidos registrados aún. Envía primero una lista de partidos.")
        return
        
    chat_id = update.effective_chat.id
    context.user_data["active_matches"] = matches
    if "selected" not in context.user_data:
        context.user_data["selected"] = set()
        
    keyboard = build_match_selection_keyboard(matches, context.user_data["selected"])
    msg = "👇 *SELECCIÓN INTERACTIVA DE PARTIDOS PROGRAMADOS:*\nToca los botones para seleccionar los encuentros que deseas programar en tu agenda:"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

def build_match_selection_keyboard(matches: list, selected: set) -> InlineKeyboardMarkup:
    keyboard = []
    keyboard.append([InlineKeyboardButton("🔔 PROGRAMAR TODOS LOS PARTIDOS", callback_data="track_all")])
    
    for m in matches[:10]:
        p_id = m["partido_id"]
        is_sel = p_id in selected
        icon = "✅" if is_sel else "⚽"
        label = f"{icon} #{p_id}: {m['equipo_a'][:10]} vs {m['equipo_b'][:10]} ({m['prediccion']})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"toggle_{p_id}")])
        
    count = len(selected)
    keyboard.append([InlineKeyboardButton(f"📅 CONFIRMAR PROGRAMACIÓN ({count})", callback_data="confirm_selected")])
    
    return InlineKeyboardMarkup(keyboard)

async def handle_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    
    if "selected" not in context.user_data:
        context.user_data["selected"] = set()
        
    matches = context.user_data.get("active_matches", database.get_all_matches_in_db())
    
    if data == "track_all":
        p_ids = [m["partido_id"] for m in matches if m.get("resultado_real") is None]
        tracked, _ = database.track_matches_for_chat(chat_id, p_ids)
        await query.edit_message_text(
            f"📅 *[PARTIDOS PROGRAMADOS CON ÉXITO]*\n\n"
            f"Se han registrado *{len(tracked)} partidos* en tu agenda.\n"
            f"Los partidos permanecen programados hasta su hora oficial.\n\n"
            f"💡 *Para probar la simulación en vivo ahora:* Envía el comando `/simular todos` o `/simular M14`.",
            parse_mode="Markdown"
        )
        return
        
    if data.startswith("toggle_"):
        p_id = data.replace("toggle_", "")
        if p_id in context.user_data["selected"]:
            context.user_data["selected"].remove(p_id)
        else:
            context.user_data["selected"].add(p_id)
            
        new_keyboard = build_match_selection_keyboard(matches, context.user_data["selected"])
        await query.edit_message_reply_markup(reply_markup=new_keyboard)
        return
        
    if data == "confirm_selected":
        selected_ids = list(context.user_data["selected"])
        if not selected_ids:
            await query.edit_message_text("⚠️ No seleccionaste ningún partido. Toca `/confirmar` para intentar de nuevo.", parse_mode="Markdown")
            return
            
        tracked, _ = database.track_matches_for_chat(chat_id, selected_ids)
        msg = f"📅 *[PARTIDOS PROGRAMADOS REGISTRADOS]*\n\nSe han guardado en agenda *{len(tracked)} partidos seleccionados*:\n"
        for t in tracked:
            msg += f"• `{t['partido_id']}`: *{t['equipo_a']}* vs *{t['equipo_b']}*\n"
        msg += "\n💡 *Para activar las notificaciones y simulación en vivo de estos partidos:* envía `/simular` o `/simular todos`."
        await query.edit_message_text(msg, parse_mode="Markdown")
        context.user_data["selected"].clear()
        return

async def simular_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    chat_id = update.effective_chat.id
    
    if not args or "todos" in [a.lower() for a in args]:
        matches = database.get_all_matches_in_db()
        p_ids = [m["partido_id"] for m in matches if m["resultado_real"] is None]
    else:
        p_ids = [a.upper().strip(",") for a in args]
        
    database.track_matches_for_chat(chat_id, p_ids)
    started = database.start_match_simulation(chat_id, p_ids)
    
    if started:
        msg = (
            f"🚀 *[INICIANDO SIMULACIÓN Y MONITOREO EN VIVO]*\n\n"
            f"Se ha iniciado la simulación en tiempo real para *{len(started)} partidos*:\n"
            + "\n".join([f"• `{pid}`" for pid in started]) + "\n\n"
            f"_Recibirás alertas inmediatas del silbato inicial, goles, marcador en vivo y cierre del partido._"
        )
    else:
        msg = "⚠️ No se encontraron partidos válidos para iniciar simulación."
        
    await update.message.reply_text(msg, parse_mode="Markdown")

async def resultado_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ *Sintaxis incorrecta.* Uso: `/resultado <partido_id> <1|X|2>`\nEjemplo: `/resultado M01 1`",
            parse_mode="Markdown"
        )
        return
        
    partido_id = args[0]
    resultado_real = args[1]
    
    success, msg = feedback_loop.process_match_result(partido_id, resultado_real)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def process_data_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return
        
    if re.search(r"\b(confirmo|confirmar|seguir|seguimiento)\b", text, re.IGNORECASE):
        await seguir_command(update, context)
        return
        
    if re.search(r"\b(simular|simulacion|comenzar|iniciar)\b", text, re.IGNORECASE):
        ids = re.findall(r"\b(?:M\d+|[A-Za-z0-9]{8})\b", text, re.IGNORECASE)
        if "todos" in text.lower() or not ids:
            context.args = ["todos"]
        else:
            context.args = ids
        await simular_command(update, context)
        return

    normalized, err = normalizer.parse_input_data(text)
    if err:
        await update.message.reply_text(err, parse_mode="Markdown")
        return
        
    if isinstance(normalized, list):
        await process_batch_matches(update, normalized)
    else:
        await process_single_match(update, normalized)

async def process_batch_matches(update: Update, batch: list):
    total = len(batch)
    await update.message.reply_text(
        f"⚡ *[PROCESANDO LOTE DE {total} PARTIDOS...]*\nEjecutando inferencia estadística y modelo predictivo táctico...",
        parse_mode="Markdown"
    )
    
    results = []
    matches_db = []
    for match_data in batch:
        analysis = tactical_engine.analyze_match(match_data)
        results.append(analysis)
        matches_db.append({
            "partido_id": analysis["partido_id"],
            "equipo_a": analysis["equipo_a"],
            "equipo_b": analysis["equipo_b"],
            "prediccion": analysis["prediccion"]
        })
        
    context.user_data["active_matches"] = matches_db
    context.user_data["selected"] = set()
    
    header = f"⚽ *[PRONÓSTICO TÁCTICO MASIVO — {total} PARTIDOS]*\n\n"
    
    lines = []
    for r in results:
        p_id = r["partido_id"]
        eq_a = r["equipo_a"]
        eq_b = r["equipo_b"]
        pred = r["prediccion"]
        conf = r["confianza"]
        fact = r["factor_determinante"]
        
        pred_label = {"1": "Gana Local (1)", "X": "Empate (X)", "2": "Gana Visita (2)"}.get(pred, pred)
        
        lines.append(
            f"`#{p_id}` *{eq_a}* vs *{eq_b}*\n"
            f"  ↳ Pronóstico: *{pred_label}* ({conf}% conf.)\n"
            f"  ↳ Factor: _{fact}_\n"
        )
        
    full_text = header + "\n".join(lines)
    
    if len(full_text) > 3800:
        chunks = [full_text[i:i+3500] for i in range(0, len(full_text), 3500)]
        for chunk in chunks[:-1]:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        full_text = chunks[-1]

    keyboard = build_match_selection_keyboard(matches_db, context.user_data["selected"])
    await update.message.reply_text(
        full_text + "\n\n👇 *Toca los botones para programar los encuentros que deseas agendar:*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def process_single_match(update: Update, normalized: dict):
    analysis = tactical_engine.analyze_match(normalized)
    
    eq_a = normalized["equipo_a"]
    eq_b = normalized["equipo_b"]
    ind = analysis["indices"]
    p_id = analysis["partido_id"]
    
    pred_map = {"1": f"Victoria de {eq_a['nombre']}", "X": "Empate", "2": f"Victoria de {eq_b['nombre']}"}
    pred_desc = pred_map.get(analysis["prediccion"], analysis["prediccion"])
    
    table_str = (
        "```\n"
        f"Métrica            | {eq_a['nombre'][:10]:<10} | {eq_b['nombre'][:10]:<10}\n"
        "-------------------|------------|------------\n"
        f"Distancia (km)     | {eq_a['distancia']:<10.1f} | {eq_b['distancia']:<10.1f}\n"
        f"Part. Goles        | {eq_a['part_goles']:<10.2f} | {eq_b['part_goles']:<10.2f}\n"
        f"Contrib. Prep      | {eq_a['prep']:<10.1f} | {eq_b['prep']:<10.1f}\n"
        f"Faltas             | {eq_a['faltas']:<10.1f} | {eq_b['faltas']:<10.1f}\n"
        f"Tasa Conv (%)      | {eq_a['conv']*100:<10.1f} | {eq_b['conv']*100:<10.1f}\n"
        "-------------------|------------|------------\n"
        f"IEO (Ofensivo)     | {ind['equipo_a']['ieo']:<10.2f} | {ind['equipo_b']['ieo']:<10.2f}\n"
        f"ICJ (Control)      | {ind['equipo_a']['icj']:<10.2f} | {ind['equipo_b']['icj']:<10.2f}\n"
        f"IIF (Intensidad)   | {ind['equipo_a']['iif']:<10.2f} | {ind['equipo_b']['iif']:<10.2f}\n"
        "```"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 Programar Partido #{p_id}", callback_data=f"toggle_{p_id}")],
        [InlineKeyboardButton(f"🚀 Confirmar Programación", callback_data="confirm_selected")]
    ])
    
    msg = (
        f"⚽ *[DIAGNÓSTICO TÁCTICO — PARTIDO #{p_id}]*\n"
        f"*{eq_a['nombre']} VS {eq_b['nombre']}*\n\n"
        f"{table_str}\n\n"
        "📊 *PROYECCIÓN DE ESCENARIO:*\n"
        f"• *Pronóstico:* `{analysis['prediccion']}` — **{pred_desc.upper()}**\n"
        f"• *Grado de Confianza:* **{analysis['confianza']}%**\n"
        f"• *Motor Aplicado:* _{analysis['metodo']}_\n\n"
        "🎯 *FACTOR DETERMINANTE:*\n"
        f"_{analysis['factor_determinante']}_\n"
    )
    
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

async def post_init(app):
    asyncio.create_task(live_tracker.start_live_tracker(app))

def main():
    database.init_db()
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN no configurado en el archivo .env")
        
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("resultado", resultado_command))
    app.add_handler(CommandHandler("feedback", resultado_command))
    app.add_handler(CommandHandler("confirmar", seguir_command))
    app.add_handler(CommandHandler("seguir", seguir_command))
    app.add_handler(CommandHandler("simular", simular_command))
    
    app.add_handler(CallbackQueryHandler(handle_button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), process_data_message))
    
    print("🤖 DT Futbol Statistics Bot (Modo Programado + Simulación) iniciado...")
    app.run_polling()

if __name__ == "__main__":
    main()
