# cache_manager.py
# (v3.0.0 - Genel Veri Yönetimi)

import sqlite3
import os
from datetime import datetime

DB_FILE = "yasam_skoru_cache.db"


def init_db():
    """Veritabanı ve tabloyu oluşturur."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS environmental_cache (
            grid_id TEXT PRIMARY KEY,
            ndvi_value REAL,
            no2_value REAL,
            last_updated TEXT
        )
    ''')

    conn.commit()
    conn.close()


def get_grid_id(lat, lon):
    grid_lat = round(lat * 200) / 200
    grid_lon = round(lon * 200) / 200
    return f"{grid_lat}_{grid_lon}"


def get_cached_data(lat, lon, data_type="ndvi"):
    grid_id = get_grid_id(lat, lon)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    column = "ndvi_value" if data_type == "ndvi" else "no2_value"

    try:
        cursor.execute(f"SELECT {column} FROM environmental_cache WHERE grid_id = ?", (grid_id,))
        result = cursor.fetchone()
    except Exception:
        result = None

    conn.close()
    if result and result[0] is not None: return result[0]
    return None


def save_data_to_cache(lat, lon, data_type, value):
    grid_id = get_grid_id(lat, lon)
    now = datetime.now().isoformat()
    column = "ndvi_value" if data_type == "ndvi" else "no2_value"

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM environmental_cache WHERE grid_id = ?", (grid_id,))
    exists = cursor.fetchone()

    if exists:
        cursor.execute(f"UPDATE environmental_cache SET {column} = ?, last_updated = ? WHERE grid_id = ?",
                       (value, now, grid_id))
    else:
        if data_type == "ndvi":
            cursor.execute("INSERT INTO environmental_cache (grid_id, ndvi_value, last_updated) VALUES (?, ?, ?)",
                           (grid_id, value, now))
        else:
            cursor.execute("INSERT INTO environmental_cache (grid_id, no2_value, last_updated) VALUES (?, ?, ?)",
                           (grid_id, value, now))

    conn.commit()
    conn.close()
    print(f"  [CACHE] {data_type.upper()} kaydedildi. Grid: {grid_id}")


init_db()