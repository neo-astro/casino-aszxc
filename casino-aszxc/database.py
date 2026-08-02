import os
import sqlite3
import psycopg2

def load_env():
    """Carga variables desde el archivo .env si existe."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

# Cargar .env al importar el módulo
load_env()

DB_TYPE = os.getenv("DB_TYPE", "postgres").lower()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "casino_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DATABASE_URL = os.getenv("DATABASE_URL", None)

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "casino.db")

def get_db_connection():
    """
    Retorna una conexión a PostgreSQL según las variables de entorno en .env.
    Si se especifica SQLite o si falla la conexión a Postgres, usa el respaldo SQLite.
    """
    load_env()
    db_type = os.getenv("DB_TYPE", "postgres").lower()
    
    if db_type == "postgres":
        try:
            if DATABASE_URL:
                conn = psycopg2.connect(DATABASE_URL)
            else:
                conn = psycopg2.connect(
                    host=os.getenv("DB_HOST", "localhost"),
                    port=os.getenv("DB_PORT", "5432"),
                    dbname=os.getenv("DB_NAME", "casino_db"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", "postgres")
                )
            return conn, "postgres"
        except Exception as e:
            print(f"[AVISO] No se pudo conectar a PostgreSQL ({e}). Usando respaldo SQLite (casino.db).")
            conn = sqlite3.connect(SQLITE_PATH)
            return conn, "sqlite"
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        return conn, "sqlite"

def clean_spin_time(spin_time_str):
    """Limpia y da formato legible AAAA-MM-DD HH:MM:SS a la fecha/hora recibida."""
    if not spin_time_str or spin_time_str in ["JUEGO ACTUAL", "loading"]:
        return spin_time_str
    try:
        clean_str = spin_time_str.replace("T", " ").split(".")[0]
        return clean_str
    except Exception:
        return spin_time_str

def init_db():
    """Inicializa la base de datos (PostgreSQL o SQLite) creando las tablas si no existen."""
    conn, engine = get_db_connection()
    cursor = conn.cursor()
    
    if engine == "postgres":
        # DDL PostgreSQL
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spins (
                spin_hash VARCHAR(255) PRIMARY KEY,
                game_id VARCHAR(50) DEFAULT '126271',
                provider VARCHAR(50) DEFAULT 'SMARTSOFT',
                spin_time VARCHAR(100),
                coefficient NUMERIC,
                info TEXT,
                is_current BOOLEAN DEFAULT FALSE,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_metrics (
                spin_hash VARCHAR(255) PRIMARY KEY,
                game_id VARCHAR(50) DEFAULT '126271',
                provider VARCHAR(50) DEFAULT 'SMARTSOFT',
                players_active INT DEFAULT 0,
                players_win_count INT DEFAULT 0,
                total_bet_amount NUMERIC DEFAULT 0.0,
                players_cashout_total NUMERIC DEFAULT 0.0,
                spin_time VARCHAR(100),
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    else:
        # DDL SQLite
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spins (
                spin_hash TEXT PRIMARY KEY,
                game_id TEXT DEFAULT '126271',
                provider TEXT DEFAULT 'SMARTSOFT',
                spin_time TEXT,
                coefficient REAL,
                info TEXT,
                is_current INTEGER DEFAULT 0,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_metrics (
                spin_hash TEXT PRIMARY KEY,
                game_id TEXT DEFAULT '126271',
                provider TEXT DEFAULT 'SMARTSOFT',
                players_active INTEGER DEFAULT 0,
                players_win_count INTEGER DEFAULT 0,
                total_bet_amount REAL DEFAULT 0.0,
                players_cashout_total REAL DEFAULT 0.0,
                spin_time TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
    conn.commit()
    conn.close()

def save_spin(spin_data):
    """Guarda o actualiza una jugada (spin) en la base de datos."""
    spin_hash = spin_data.get("SpinHash")
    if not spin_hash or spin_hash == "loading":
        return False
        
    conn, engine = get_db_connection()
    cursor = conn.cursor()
    
    coeff = spin_data.get("Coefficient")
    try:
        coeff = float(coeff) if coeff is not None and coeff != "EN JUEGO" else None
    except ValueError:
        coeff = None

    spin_time = clean_spin_time(spin_data.get("SpinTime"))
    game_id = spin_data.get("game_id", "126271")
    provider = spin_data.get("provider", "SMARTSOFT")
    is_curr = True if spin_data.get("is_current") else False

    if engine == "postgres":
        query = """
            INSERT INTO spins (spin_hash, game_id, provider, spin_time, coefficient, info, is_current, recorded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (spin_hash) DO UPDATE SET
                game_id = EXCLUDED.game_id,
                provider = EXCLUDED.provider,
                spin_time = EXCLUDED.spin_time,
                coefficient = EXCLUDED.coefficient,
                info = EXCLUDED.info,
                is_current = EXCLUDED.is_current,
                recorded_at = CURRENT_TIMESTAMP;
        """
        cursor.execute(query, (
            spin_hash, game_id, provider, spin_time, coeff, spin_data.get("Info"), is_curr
        ))
    else:
        query = """
            INSERT OR REPLACE INTO spins (spin_hash, game_id, provider, spin_time, coefficient, info, is_current, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        cursor.execute(query, (
            spin_hash, game_id, provider, spin_time, coeff, spin_data.get("Info"), 1 if is_curr else 0
        ))
    
    conn.commit()
    conn.close()
    return True

def save_game_metrics(metrics_data):
    """Guarda o actualiza las métricas de apuestas asociadas al HASH de la jugada."""
    spin_hash = metrics_data.get("spin_hash")
    if not spin_hash or spin_hash in ["loading", "PENDIENTE"]:
        return False
        
    conn, engine = get_db_connection()
    cursor = conn.cursor()
    
    spin_time = clean_spin_time(metrics_data.get("spin_time"))
    game_id = metrics_data.get("game_id", "126271")
    provider = metrics_data.get("provider", "SMARTSOFT")
    
    if engine == "postgres":
        query = """
            INSERT INTO game_metrics (
                spin_hash, game_id, provider, players_active, players_win_count, 
                total_bet_amount, players_cashout_total, spin_time, recorded_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (spin_hash) DO UPDATE SET
                game_id = EXCLUDED.game_id,
                provider = EXCLUDED.provider,
                players_active = EXCLUDED.players_active,
                players_win_count = EXCLUDED.players_win_count,
                total_bet_amount = EXCLUDED.total_bet_amount,
                players_cashout_total = EXCLUDED.players_cashout_total,
                spin_time = EXCLUDED.spin_time,
                recorded_at = CURRENT_TIMESTAMP;
        """
        cursor.execute(query, (
            spin_hash, game_id, provider,
            metrics_data.get("players_active", 0),
            metrics_data.get("players_win_count", 0),
            metrics_data.get("total_bet_amount", 0.0),
            metrics_data.get("players_cashout_total", 0.0),
            spin_time
        ))
    else:
        query = """
            INSERT OR REPLACE INTO game_metrics (
                spin_hash, game_id, provider, players_active, players_win_count, 
                total_bet_amount, players_cashout_total, spin_time, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        cursor.execute(query, (
            spin_hash, game_id, provider,
            metrics_data.get("players_active", 0),
            metrics_data.get("players_win_count", 0),
            metrics_data.get("total_bet_amount", 0.0),
            metrics_data.get("players_cashout_total", 0.0),
            spin_time
        ))
    
    conn.commit()
    conn.close()
    return True

if __name__ == "__main__":
    init_db()
    conn, engine = get_db_connection()
    print(f"Base de datos ({engine.upper()}) inicializada y conectada exitosamente.")
    conn.close()
