import os
from database import get_db_connection

def clear_all_data():
    conn, engine = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM spins")
    cursor.execute("DELETE FROM game_metrics")
    
    conn.commit()
    conn.close()
    
    print(f"¡Toda la información en la base de datos [{engine.upper()}] ha sido borrada exitosamente!")

if __name__ == "__main__":
    clear_all_data()
