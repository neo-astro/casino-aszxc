import os
from database import get_db_connection, init_db

def format_dt(dt_str):
    if not dt_str:
        return "N/A"
    return str(dt_str).replace("T", " ").split(".")[0]

def show_stored_data():
    init_db()
    conn, engine = get_db_connection()
    cursor = conn.cursor()
    
    print(f"=== HISTORIAL DE JUGADAS EN BASE DE DATOS [{engine.upper()}] ===")
    cursor.execute("SELECT spin_hash, game_id, provider, spin_time, coefficient, is_current, recorded_at FROM spins ORDER BY recorded_at DESC LIMIT 15")
    spins = cursor.fetchall()
    if spins:
        for s in spins:
            coef_str = f"{s[4]}x" if s[4] is not None else ("EN CURSO" if s[5] else "N/A")
            hora_juego = format_dt(s[3])
            hora_registro = format_dt(s[6])
            print(f"Juego: {s[1]} ({s[2]}) | Hash: {s[0][:14]}... | Coef: {coef_str:<8} | Fecha Juego: {hora_juego:<19} | Registrado: {hora_registro}")
    else:
        print("No hay registros en la tabla spins.")
        
    print(f"\n=== MÉTRICAS ÚNICAS POR HASH [{engine.upper()}] ===")
    cursor.execute("""
        SELECT 
            m.spin_hash, 
            m.game_id,
            m.provider,
            s.coefficient,
            m.players_active, 
            m.players_win_count, 
            m.total_bet_amount, 
            m.players_cashout_total, 
            m.spin_time,
            m.recorded_at 
        FROM game_metrics m
        LEFT JOIN spins s ON m.spin_hash = s.spin_hash
        ORDER BY m.recorded_at DESC LIMIT 15
    """)
    metrics = cursor.fetchall()
    if metrics:
        for m in metrics:
            coef_val = f"{m[3]}x" if m[3] is not None else "En curso"
            fecha_hora_partida = format_dt(m[8]) if m[8] else format_dt(m[9])
            fecha_hora_registro = format_dt(m[9])
            print(f"Juego: {m[1]} | Hash: {m[0][:14]}... | Coef: {coef_val:<7} | Jugadores: {m[4]:<3} | Ganadores: {m[5]:<3} | Ingresado: ${m[6]:>7.2f} | Cobrado: ${m[7]:>7.2f} | Fecha: {fecha_hora_partida}")
    else:
        print("No hay registros en la tabla game_metrics.")
        
    conn.close()

if __name__ == "__main__":
    show_stored_data()
