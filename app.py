import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from models import obtener_socios, obtener_ciclos
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
import models

app = Flask(__name__)
app.secret_key = 'Elija una contraseña'
app.config['SECRET_KEY'] = 'tu-clave-secreta-muy-segura-cambiala-en-produccion'  # ¡Cámbiala!

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Inicializar la base de datos si no existe
models.init_db()

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = models.get_db()
    user_data = conn.execute('SELECT * FROM usuario WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'])
    return None

# -------------------- RUTAS PRINCIPALES --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = models.obtener_usuario_por_username(username)
        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['id'], user['username'])
            login_user(user_obj)
            flash('Inicio de sesión exitoso', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    socios = models.obtener_socios()
    ciclos = models.obtener_ciclos()
    ciclos_abiertos = sum(1 for c in ciclos if c['estado'] == 'abierto')
    fondo_total = sum(s['fondo_disponible'] for s in socios)
    return render_template('index.html', socios_count=len(socios), ciclos_abiertos=ciclos_abiertos, fondo_total=fondo_total)

# -------------------- SOCIOS --------------------
@app.route('/socios')
@login_required
def listar_socios():
    socios = models.obtener_socios()
    return render_template('socios.html', socios=socios)

@app.route('/socio/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_socio():
    if request.method == 'POST':
        nombre = request.form['nombre']
        if nombre:
            models.crear_socio(nombre)
            flash('Socio creado correctamente', 'success')
            return redirect(url_for('listar_socios'))
    return render_template('socio_nuevo.html')

@app.route('/socio/<int:id>')
@login_required
def detalle_socio(id):
    socio = models.obtener_socio(id)
    movimientos = models.obtener_movimientos_socio(id)
    participaciones = models.obtener_participaciones_socio(id)
    return render_template('socio_detalle.html', socio=socio, movimientos=movimientos, participaciones=participaciones)

@app.route('/socio/<int:id>/agregar_fondo', methods=['POST'])
@login_required
def agregar_fondo(id):
    monto = float(request.form['monto'])
    if monto > 0:
        models.agregar_fondo_socio(id, monto)
        flash(f'Se agregaron ${monto:.2f} al fondo', 'success')
    else:
        flash('El monto debe ser positivo', 'danger')
    return redirect(url_for('detalle_socio', id=id))

@app.route('/socio/<int:id>/retirar_fondo', methods=['POST'])
@login_required
def retirar_fondo(id):
    monto = float(request.form['monto'])
    if monto <= 0:
        flash('Monto inválido', 'danger')
        return redirect(url_for('detalle_socio', id=id))
    socio = models.obtener_socio(id)
    if socio['fondo_disponible'] >= monto:
        models.retirar_fondo_socio(id, monto)
        flash(f'Se retiraron ${monto:.2f} del fondo', 'success')
    else:
        flash('Fondo insuficiente', 'danger')
    return redirect(url_for('detalle_socio', id=id))

# -------------------- CICLOS (COMPRAS) --------------------
@app.route('/ciclos')
@login_required
def listar_ciclos():
    ciclos = models.obtener_ciclos()
    return render_template('ciclos.html', ciclos=ciclos)

@app.route('/ciclo/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_ciclo():
    if request.method == 'POST':
        producto = request.form['producto']
        proveedor = request.form['proveedor']
        cantidad = int(request.form['cantidad'])
        precio_compra = float(request.form['precio_compra'])
        precio_venta = float(request.form['precio_venta'])
        total_compra = cantidad * precio_compra

        # Obtener aportes de los socios (dinámico, vía JS o manual)
        # Por simplicidad, usaremos un listado de socios con input de monto
        socios = models.obtener_socios()
        aportes = {}
        for s in socios:
            monto_key = f'aporte_{s["id"]}'
            if monto_key in request.form and request.form[monto_key]:
                monto = float(request.form[monto_key])
                if monto > 0:
                    aportes[s['id']] = monto

        if sum(aportes.values()) != total_compra:
            flash('La suma de los aportes debe ser igual al total de la compra', 'danger')
            return redirect(url_for('nuevo_ciclo'))

        # Validar fondos suficientes
        for socio_id, monto in aportes.items():
            socio = models.obtener_socio(socio_id)
            if socio['fondo_disponible'] < monto:
                flash(f'El socio {socio["nombre"]} no tiene suficiente fondo disponible', 'danger')
                return redirect(url_for('nuevo_ciclo'))

        # Crear ciclo y descontar aportes
        ciclo_id = models.crear_ciclo(producto, proveedor, cantidad, precio_compra, precio_venta, total_compra, aportes)
        flash('Ciclo creado exitosamente', 'success')
        return redirect(url_for('detalle_ciclo', id=ciclo_id))

    socios = models.obtener_socios()
    return render_template('ciclo_nuevo.html', socios=socios)

@app.route('/ciclo/<int:id>')
@login_required
def detalle_ciclo(id):
    ciclo = models.obtener_ciclo(id)
    aportes = models.obtener_aportes_ciclo(id)
    ventas = models.obtener_ventas_ciclo(id)
    total_vendido = sum(v['cantidad'] for v in ventas)
    restante = ciclo['cantidad'] - total_vendido
    ingresos = sum(v['total'] for v in ventas if v['pagado'] == 1)
    ganancia_realizada = ingresos - ciclo['total_compra'] if ingresos > 0 else 0
    # ganancia esperada (si se vende todo al precio estimado)
    ganancia_esperada = (ciclo['precio_venta_estimado'] - ciclo['precio_compra']) * ciclo['cantidad']
    return render_template('ciclo_detalle.html', ciclo=ciclo, aportes=aportes, ventas=ventas,
                           total_vendido=total_vendido, restante=restante,
                           ganancia_realizada=ganancia_realizada, ganancia_esperada=ganancia_esperada)

@app.route('/ciclo/<int:id>/cerrar', methods=['POST'])
@login_required
def cerrar_ciclo(id):
    try:
        models.cerrar_ciclo(id)
        flash('Ciclo cerrado y ganancias distribuidas a los socios', 'success')
    except Exception as e:
        flash(str(e), 'danger')
    return redirect(url_for('detalle_ciclo', id=id))

# -------------------- VENTAS Y PASADORES --------------------
@app.route('/ciclo/<int:id>/venta', methods=['GET', 'POST'])
@login_required
def nueva_venta(id):
    ciclo = models.obtener_ciclo(id)
    # Calcular cuánto se ha vendido hasta ahora
    ventas_actuales = models.obtener_ventas_ciclo(id)
    total_vendido = sum(v['cantidad'] for v in ventas_actuales)
    
    if request.method == 'POST':
        cantidad = int(request.form['cantidad'])
        precio_unitario = float(request.form['precio_unitario'])
        tipo = request.form['tipo']
        total = cantidad * precio_unitario

        # Validar stock
        if total_vendido + cantidad > ciclo['cantidad']:
            flash('No hay suficientes unidades restantes', 'danger')
            return redirect(url_for('nueva_venta', id=id))

        pagado = 1 if tipo == 'cliente' else 0
        models.registrar_venta(id, cantidad, precio_unitario, total, tipo, pagado)
        flash('Venta registrada', 'success')
        return redirect(url_for('detalle_ciclo', id=id))
    
    # Pasamos total_vendido a la plantilla
    return render_template('venta_nueva.html', ciclo=ciclo, total_vendido=total_vendido)
    
@app.route('/venta/<int:venta_id>/pagar', methods=['POST'])
@login_required
def pagar_pasador(venta_id):
    venta = models.obtener_venta(venta_id)
    if venta and venta['tipo'] == 'pasador' and venta['pagado'] == 0:
        models.marcar_venta_pagada(venta_id)
        flash('Pago de pasador registrado', 'success')
        # Intentar cerrar ciclo automáticamente si corresponde
        ciclo_id = venta['ciclo_id']
        ciclo = models.obtener_ciclo(ciclo_id)
        ventas = models.obtener_ventas_ciclo(ciclo_id)
        total_vendido = sum(v['cantidad'] for v in ventas)
        todos_pagados = all(v['pagado'] == 1 for v in ventas)
        if total_vendido == ciclo['cantidad'] and todos_pagados and ciclo['estado'] == 'abierto':
            try:
                models.cerrar_ciclo(ciclo_id)
                flash('¡El ciclo se cerró automáticamente porque todas las unidades fueron vendidas y pagadas!', 'success')
            except Exception as e:
                flash(f'Error al cerrar ciclo: {e}', 'danger')
    else:
        flash('Venta inválida o ya pagada', 'danger')
    return redirect(url_for('detalle_ciclo', id=venta['ciclo_id']))

# -------------------- EJECUCIÓN --------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)