"""
migrar_db.py — Agrega las columnas nuevas a la base de datos existente
Corre esto UNA sola vez desde la carpeta files/:

    python migrar_db.py

No borra datos, solo agrega las columnas que faltan.
"""
import sqlite3
import os

# Buscar la base de datos automáticamente
posibles_rutas = [
    "apoyofes.db",
    "./apoyofes.db",
    "app/apoyofes.db",
]
DB_PATH = None
for ruta in posibles_rutas:
    if os.path.exists(ruta):
        DB_PATH = ruta
        break

if not DB_PATH:
    print("❌ No se encontró apoyofes.db. Asegúrate de correr esto desde la carpeta files/")
    exit(1)

print(f"✅ Base de datos encontrada: {DB_PATH}")

# Columnas nuevas a agregar (tabla, columna, tipo SQL)
NUEVAS_COLUMNAS = [
    ("usuarios", "emergencia_nombre",   "VARCHAR(120)"),
    ("usuarios", "emergencia_telefono", "VARCHAR(20)"),
    ("usuarios", "emergencia_email",    "VARCHAR(200)"),
]

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

for tabla, columna, tipo in NUEVAS_COLUMNAS:
    # Verificar si ya existe
    cur.execute(f"PRAGMA table_info({tabla})")
    columnas_existentes = [row[1] for row in cur.fetchall()]

    if columna in columnas_existentes:
        print(f"  ⏭  {tabla}.{columna} ya existe — sin cambios")
    else:
        cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
        print(f"  ✅ Columna agregada: {tabla}.{columna} ({tipo})")

conn.commit()
conn.close()
print("\n🎉 Migración completada. Reinicia el servidor.")
