import sqlite3
import os

DB_PATH = "/opt/data/nexus_playtv_bot/data/playtv.db"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabela de Pedidos e Assinaturas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        user_id INTEGER,
        username TEXT,
        product_id TEXT,
        payment_method TEXT,
        amount REAL,
        status TEXT DEFAULT 'pending',
        payment_id TEXT,
        delivered_credentials TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Tabela de Testes Grátis de 4h (1 teste por usuário para evitar abuso)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS free_trials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        iptv_username TEXT,
        iptv_password TEXT,
        server_url TEXT,
        m3u_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        reminded_30m INTEGER DEFAULT 0,
        reminded_expired INTEGER DEFAULT 0
    )
    """)
    
    # Tabela de Usuários / Preferências
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Banco de dados Nexus PlayTV inicializado com sucesso.")
