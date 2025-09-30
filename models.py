import psycopg2
import os

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    url = os.environ.get('DATABASE_URL')
    if url:
        # Heroku/producción suele requerir SSL
        return psycopg2.connect(url, sslmode='require')
    # Fallback local para desarrollo
    local_url = "postgresql://postgres:postgre@localhost:5432/gift_tracker_dev"
    return psycopg2.connect(local_url, sslmode='disable')

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS eventos (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL UNIQUE,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE
        );
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id SERIAL PRIMARY KEY,
            evento_id INTEGER NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
            comprador_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            destinatario VARCHAR(50) NOT NULL,
            descripcion TEXT NOT NULL,
            monto DECIMAL(10, 2) NOT NULL
        );
    ''')

    conn.commit()
    cur.close()
    conn.close()