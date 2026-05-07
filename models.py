import sqlite3
import os
from datetime import datetime

DATABASE = 'gestion.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crea las tablas si no existen"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS socio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            fondo_disponible REAL DEFAULT 0.0,
            fondo_total REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ciclo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_compra TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_cierre TIMESTAMP,
            producto TEXT NOT NULL,
            proveedor TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_compra REAL NOT NULL,
            precio_venta_estimado REAL NOT NULL,
            total_compra REAL NOT NULL,
            estado TEXT DEFAULT 'abierto'
        );

        CREATE TABLE IF NOT EXISTS aporte_ciclo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ciclo_id INTEGER,
            socio_id INTEGER,
            monto REAL NOT NULL,
            FOREIGN KEY (ciclo_id) REFERENCES ciclo(id),
            FOREIGN KEY (socio_id) REFERENCES socio(id)
        );

        CREATE TABLE IF NOT EXISTS venta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ciclo_id INTEGER,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            total REAL NOT NULL,
            tipo TEXT DEFAULT 'cliente',
            pagado INTEGER DEFAULT 1,  -- 1=si, 0=no
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ciclo_id) REFERENCES ciclo(id)
        );

        CREATE TABLE IF NOT EXISTS movimiento_fondo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            socio_id INTEGER,
            monto REAL,
            descripcion TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (socio_id) REFERENCES socio(id)
        );
    ''')
    conn.commit()
    conn.close()

# -------------------- SOCIOS --------------------
def obtener_socios():
    conn = get_db()
    socios = conn.execute('SELECT * FROM socio ORDER BY id DESC').fetchall()
    conn.close()
    return socios

def obtener_socio(id):
    conn = get_db()
    socio = conn.execute('SELECT * FROM socio WHERE id = ?', (id,)).fetchone()
    conn.close()
    return socio

def crear_socio(nombre):
    conn = get_db()
    conn.execute('INSERT INTO socio (nombre) VALUES (?)', (nombre,))
    conn.commit()
    conn.close()

def agregar_fondo_socio(socio_id, monto):
    conn = get_db()
    conn.execute('UPDATE socio SET fondo_disponible = fondo_disponible + ? WHERE id = ?', (monto, socio_id))
    conn.execute('UPDATE socio SET fondo_total = fondo_total + ? WHERE id = ?', (monto, socio_id))
    conn.execute('INSERT INTO movimiento_fondo (socio_id, monto, descripcion) VALUES (?, ?, ?)',
                 (socio_id, monto, 'Aportación manual'))
    conn.commit()
    conn.close()

def retirar_fondo_socio(socio_id, monto):
    conn = get_db()
    conn.execute('UPDATE socio SET fondo_disponible = fondo_disponible - ? WHERE id = ?', (monto, socio_id))
    # fondo_total no se toca porque es histórico?
    conn.execute('INSERT INTO movimiento_fondo (socio_id, monto, descripcion) VALUES (?, ?, ?)',
                 (socio_id, -monto, 'Retiro manual'))
    conn.commit()
    conn.close()

def obtener_movimientos_socio(socio_id):
    conn = get_db()
    movs = conn.execute('SELECT * FROM movimiento_fondo WHERE socio_id = ? ORDER BY fecha DESC', (socio_id,)).fetchall()
    conn.close()
    return movs

def obtener_participaciones_socio(socio_id):
    conn = get_db()
    participaciones = conn.execute('''
        SELECT c.id as ciclo_id, c.producto, c.estado, a.monto as aporte,
               COALESCE((SELECT SUM(total) FROM venta WHERE ciclo_id = c.id AND pagado=1), 0) as ingreso_total,
               c.total_compra
        FROM aporte_ciclo a
        JOIN ciclo c ON a.ciclo_id = c.id
        WHERE a.socio_id = ?
        ORDER BY c.fecha_compra DESC
    ''', (socio_id,)).fetchall()
    conn.close()
    return participaciones
    
# -------------------- CICLOS --------------------
def obtener_ciclos():
    conn = get_db()
    ciclos = conn.execute('SELECT * FROM ciclo ORDER BY fecha_compra DESC').fetchall()
    conn.close()
    return ciclos

def obtener_ciclo(id):
    conn = get_db()
    ciclo = conn.execute('SELECT * FROM ciclo WHERE id = ?', (id,)).fetchone()
    conn.close()
    return ciclo

def crear_ciclo(producto, proveedor, cantidad, precio_compra, precio_venta, total_compra, aportes):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ciclo (producto, proveedor, cantidad, precio_compra, precio_venta_estimado, total_compra, estado)
        VALUES (?, ?, ?, ?, ?, ?, 'abierto')
    ''', (producto, proveedor, cantidad, precio_compra, precio_venta, total_compra))
    ciclo_id = cursor.lastrowid

    # Insertar aportes y descontar de fondo de socios
    for socio_id, monto in aportes.items():
        cursor.execute('INSERT INTO aporte_ciclo (ciclo_id, socio_id, monto) VALUES (?, ?, ?)',
                       (ciclo_id, socio_id, monto))
        # Descontar del fondo disponible
        cursor.execute('UPDATE socio SET fondo_disponible = fondo_disponible - ? WHERE id = ?', (monto, socio_id))
        # Registrar movimiento negativo (inversión)
        cursor.execute('INSERT INTO movimiento_fondo (socio_id, monto, descripcion) VALUES (?, ?, ?)',
                       (socio_id, -monto, f'Inversión en ciclo #{ciclo_id}'))
    conn.commit()
    conn.close()
    return ciclo_id

def obtener_aportes_ciclo(ciclo_id):
    conn = get_db()
    aportes = conn.execute('''
        SELECT a.*, s.nombre FROM aporte_ciclo a
        JOIN socio s ON a.socio_id = s.id
        WHERE a.ciclo_id = ?
    ''', (ciclo_id,)).fetchall()
    conn.close()
    return aportes

def obtener_ventas_ciclo(ciclo_id):
    conn = get_db()
    ventas = conn.execute('SELECT * FROM venta WHERE ciclo_id = ? ORDER BY fecha', (ciclo_id,)).fetchall()
    conn.close()
    return ventas

def registrar_venta(ciclo_id, cantidad, precio_unitario, total, tipo, pagado):
    conn = get_db()
    conn.execute('''
        INSERT INTO venta (ciclo_id, cantidad, precio_unitario, total, tipo, pagado)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (ciclo_id, cantidad, precio_unitario, total, tipo, pagado))
    conn.commit()
    conn.close()

def obtener_venta(venta_id):
    conn = get_db()
    venta = conn.execute('SELECT * FROM venta WHERE id = ?', (venta_id,)).fetchone()
    conn.close()
    return venta

def marcar_venta_pagada(venta_id):
    conn = get_db()
    conn.execute('UPDATE venta SET pagado = 1 WHERE id = ?', (venta_id,))
    conn.commit()
    conn.close()

def cerrar_ciclo(ciclo_id):
    conn = get_db()
    ciclo = conn.execute('SELECT * FROM ciclo WHERE id = ? AND estado = "abierto"', (ciclo_id,)).fetchone()
    if not ciclo:
        raise Exception('El ciclo no existe o ya está cerrado')

    ventas = conn.execute('SELECT * FROM venta WHERE ciclo_id = ?', (ciclo_id,)).fetchall()
    total_vendido = sum(v['cantidad'] for v in ventas)
    if total_vendido != ciclo['cantidad']:
        raise Exception('No se han vendido todas las unidades')

    pagados = all(v['pagado'] == 1 for v in ventas)
    if not pagados:
        raise Exception('Hay ventas de pasadores aún no pagadas')

    ingreso_total = sum(v['total'] for v in ventas if v['pagado'] == 1)
    ganancia = ingreso_total - ciclo['total_compra']

    aportes = conn.execute('SELECT * FROM aporte_ciclo WHERE ciclo_id = ?', (ciclo_id,)).fetchall()
    total_aportado = sum(a['monto'] for a in aportes)

    for a in aportes:
        parte_ganancia = (a['monto'] / total_aportado) * ganancia
        total_a_socio = a['monto'] + parte_ganancia  # devolución inversión + ganancia
        # Sumar al fondo disponible
        conn.execute('UPDATE socio SET fondo_disponible = fondo_disponible + ? WHERE id = ?', (total_a_socio, a['socio_id']))
        # Registrar movimiento positivo
        conn.execute('INSERT INTO movimiento_fondo (socio_id, monto, descripcion) VALUES (?, ?, ?)',
                     (a['socio_id'], total_a_socio, f'Ganancia y devolución del ciclo #{ciclo_id}'))

    # Actualizar estado del ciclo
    conn.execute('UPDATE ciclo SET estado = "cerrado", fecha_cierre = ? WHERE id = ?',
                 (datetime.now().isoformat(), ciclo_id))
    conn.commit()
    conn.close()