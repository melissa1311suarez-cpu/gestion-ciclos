from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# ======================== CONFIGURACIÓN ========================
app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_cambiala_por_una_segura'

# Base de datos con ruta ABSOLUTA y PERSISTENTE
basedir = os.path.abspath(os.path.dirname(__file__))
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database', 'gestion.db')
print(f"🔍 Ruta de la base de datos: {db_path}")
print(f"🔍 ¿Existe el archivo? {os.path.exists(db_path)}")
print(f"🔍 ¿Existe la carpeta database? {os.path.exists(os.path.join(basedir, 'database'))}")

# Si existe, mostrar el tamaño
if os.path.exists(db_path):
    print(f"🔍 Tamaño del archivo: {os.path.getsize(db_path)} bytes")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database', 'gestion.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configuración de Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ======================== MODELOS ========================

class Socio(db.Model):
    __tablename__ = 'socio'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    fondo_disponible = db.Column(db.Float, default=0.0)
    fondo_total = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    movimientos = db.relationship('MovimientoFondo', backref='socio', lazy=True)
    aportes = db.relationship('AporteCiclo', backref='socio', lazy=True)

class Ciclo(db.Model):
    __tablename__ = 'ciclo'
    id = db.Column(db.Integer, primary_key=True)
    fecha_compra = db.Column(db.DateTime, default=datetime.now)
    fecha_cierre = db.Column(db.DateTime, nullable=True)
    producto = db.Column(db.String(200), nullable=False)
    proveedor = db.Column(db.String(200), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_compra = db.Column(db.Float, nullable=False)
    precio_venta_estimado = db.Column(db.Float, nullable=False)
    total_compra = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(20), default='abierto')
    
    aportes = db.relationship('AporteCiclo', backref='ciclo', lazy=True)
    ventas = db.relationship('Venta', backref='ciclo', lazy=True)

class AporteCiclo(db.Model):
    __tablename__ = 'aporte_ciclo'
    id = db.Column(db.Integer, primary_key=True)
    ciclo_id = db.Column(db.Integer, db.ForeignKey('ciclo.id'), nullable=False)
    socio_id = db.Column(db.Integer, db.ForeignKey('socio.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)

class Venta(db.Model):
    __tablename__ = 'venta'
    id = db.Column(db.Integer, primary_key=True)
    ciclo_id = db.Column(db.Integer, db.ForeignKey('ciclo.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(20), default='cliente')
    pagado = db.Column(db.Integer, default=1)
    fecha = db.Column(db.DateTime, default=datetime.now)

class MovimientoFondo(db.Model):
    __tablename__ = 'movimiento_fondo'
    id = db.Column(db.Integer, primary_key=True)
    socio_id = db.Column(db.Integer, db.ForeignKey('socio.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(500))
    fecha = db.Column(db.DateTime, default=datetime.now)

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

# ======================== USER LOADER ========================
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# ======================== FUNCIONES DE DISTRIBUCIÓN ========================

def distribuir_venta(ciclo_id, cantidad, precio_unitario):
    """Distribuye el ingreso de una venta entre los socios del ciclo."""
    ciclo = Ciclo.query.get(ciclo_id)
    if not ciclo:
        return
    
    aportes = AporteCiclo.query.filter_by(ciclo_id=ciclo_id).all()
    if not aportes:
        return
    
    total_aportado = sum(a.monto for a in aportes)
    costo_unidad = ciclo.precio_compra
    costo_total = costo_unidad * cantidad
    ingreso_total = precio_unitario * cantidad
    ganancia_total = ingreso_total - costo_total
    
    for aporte in aportes:
        porcentaje = aporte.monto / total_aportado
        costo_parte = costo_total * porcentaje
        ganancia_parte = ganancia_total * porcentaje
        total_a_socio = costo_parte + ganancia_parte
        
        socio = Socio.query.get(aporte.socio_id)
        socio.fondo_disponible += total_a_socio
        
        movimiento = MovimientoFondo(
            socio_id=aporte.socio_id,
            monto=total_a_socio,
            descripcion=f'Distribución venta en ciclo #{ciclo_id} (cantidad: {cantidad})'
        )
        db.session.add(movimiento)
    
    db.session.commit()

# ======================== RUTAS ========================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Usuario.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
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
    socios = Socio.query.all()
    ciclos = Ciclo.query.all()
    ciclos_abiertos = sum(1 for c in ciclos if c.estado == 'abierto')
    fondo_total = sum(s.fondo_disponible for s in socios)
    return render_template('index.html', socios_count=len(socios), ciclos_abiertos=ciclos_abiertos, fondo_total=fondo_total)

@app.route('/socios')
@login_required
def listar_socios():
    socios = Socio.query.all()
    return render_template('socios.html', socios=socios)

@app.route('/socio/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_socio():
    if request.method == 'POST':
        nombre = request.form['nombre']
        if nombre:
            socio = Socio(nombre=nombre)
            db.session.add(socio)
            db.session.commit()
            flash('Socio creado correctamente', 'success')
            return redirect(url_for('listar_socios'))
    return render_template('socio_nuevo.html')

@app.route('/socio/<int:id>')
@login_required
def detalle_socio(id):
    socio = Socio.query.get_or_404(id)
    movimientos = MovimientoFondo.query.filter_by(socio_id=id).order_by(MovimientoFondo.fecha.desc()).all()
    
    # Calcular TOTAL INVERTIDO REAL (suma de todos los aportes en ciclos)
    total_invertido_real = db.session.query(db.func.sum(AporteCiclo.monto)).filter_by(socio_id=id).scalar() or 0
    
    # Obtener participaciones
    participaciones = db.session.query(
        Ciclo.id.label('ciclo_id'),
        Ciclo.producto,
        Ciclo.estado,
        AporteCiclo.monto.label('aporte'),
        Ciclo.total_compra,
        db.func.coalesce(db.func.sum(Venta.total).filter(Venta.pagado == 1), 0).label('ingreso_total')
    ).join(AporteCiclo, AporteCiclo.ciclo_id == Ciclo.id)\
     .outerjoin(Venta, Venta.ciclo_id == Ciclo.id)\
     .filter(AporteCiclo.socio_id == id)\
     .group_by(Ciclo.id).all()
    
    return render_template('socio_detalle.html', 
                         socio=socio, 
                         movimientos=movimientos, 
                         participaciones=participaciones,
                         total_invertido_real=total_invertido_real)

@app.route('/socio/<int:id>/agregar_fondo', methods=['POST'])
@login_required
def agregar_fondo(id):
    monto = float(request.form['monto'])
    if monto > 0:
        socio = Socio.query.get_or_404(id)
        socio.fondo_disponible += monto
        socio.fondo_total += monto
        movimiento = MovimientoFondo(socio_id=id, monto=monto, descripcion='Aportación manual')
        db.session.add(movimiento)
        db.session.commit()
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
    socio = Socio.query.get_or_404(id)
    if socio.fondo_disponible >= monto:
        socio.fondo_disponible -= monto
        movimiento = MovimientoFondo(socio_id=id, monto=-monto, descripcion='Retiro manual')
        db.session.add(movimiento)
        db.session.commit()
        flash(f'Se retiraron ${monto:.2f} del fondo', 'success')
    else:
        flash('Fondo insuficiente', 'danger')
    return redirect(url_for('detalle_socio', id=id))

@app.route('/ciclos')
@login_required
def listar_ciclos():
    ciclos = Ciclo.query.order_by(Ciclo.fecha_compra.desc()).all()
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
        
        socios = Socio.query.all()
        aportes = {}
        for s in socios:
            monto_key = f'aporte_{s.id}'
            if monto_key in request.form and request.form[monto_key]:
                monto = float(request.form[monto_key])
                if monto > 0:
                    aportes[s.id] = monto
        
        if sum(aportes.values()) != total_compra:
            flash('La suma de los aportes debe ser igual al total de la compra', 'danger')
            return redirect(url_for('nuevo_ciclo'))
        
        for socio_id, monto in aportes.items():
            socio = Socio.query.get(socio_id)
            if socio.fondo_disponible < monto:
                flash(f'El socio {socio.nombre} no tiene suficiente fondo disponible', 'danger')
                return redirect(url_for('nuevo_ciclo'))
        
        # Crear ciclo
        ciclo = Ciclo(
            producto=producto,
            proveedor=proveedor,
            cantidad=cantidad,
            precio_compra=precio_compra,
            precio_venta_estimado=precio_venta,
            total_compra=total_compra,
            estado='abierto'
        )
        db.session.add(ciclo)
        db.session.flush()  # Para obtener el ID
        
        for socio_id, monto in aportes.items():
            socio = Socio.query.get(socio_id)
            aporte = AporteCiclo(ciclo_id=ciclo.id, socio_id=socio_id, monto=monto)
            db.session.add(aporte)
            socio.fondo_disponible -= monto
            movimiento = MovimientoFondo(socio_id=socio_id, monto=-monto, descripcion=f'Inversión en ciclo #{ciclo.id}')
            db.session.add(movimiento)
        
        db.session.commit()
        flash('Ciclo creado exitosamente', 'success')
        return redirect(url_for('detalle_ciclo', id=ciclo.id))
    
    socios = Socio.query.all()
    return render_template('ciclo_nuevo.html', socios=socios)

@app.route('/ciclo/<int:id>')
@login_required
def detalle_ciclo(id):
    ciclo = Ciclo.query.get_or_404(id)
    aportes = AporteCiclo.query.filter_by(ciclo_id=id).all()
    ventas = Venta.query.filter_by(ciclo_id=id).all()
    total_vendido = sum(v.cantidad for v in ventas)
    restante = ciclo.cantidad - total_vendido
    ingresos = sum(v.total for v in ventas if v.pagado == 1)
    ganancia_realizada = ingresos - ciclo.total_compra if ingresos > 0 else 0
    ganancia_esperada = (ciclo.precio_venta_estimado - ciclo.precio_compra) * ciclo.cantidad
    
    return render_template('ciclo_detalle.html', 
                         ciclo=ciclo, 
                         aportes=aportes, 
                         ventas=ventas,
                         total_vendido=total_vendido, 
                         restante=restante,
                         ganancia_realizada=ganancia_realizada, 
                         ganancia_esperada=ganancia_esperada)

@app.route('/ciclo/<int:id>/cerrar', methods=['POST'])
@login_required
def cerrar_ciclo(id):
    try:
        ciclo = Ciclo.query.get_or_404(id)
        ventas = Venta.query.filter_by(ciclo_id=id).all()
        total_vendido = sum(v.cantidad for v in ventas)
        
        if total_vendido != ciclo.cantidad:
            flash('No se han vendido todas las unidades', 'danger')
            return redirect(url_for('detalle_ciclo', id=id))
        
        pagados = all(v.pagado == 1 for v in ventas)
        if not pagados:
            flash('Hay ventas de pasadores aún no pagadas', 'danger')
            return redirect(url_for('detalle_ciclo', id=id))
        
        ciclo.estado = 'cerrado'
        ciclo.fecha_cierre = datetime.now()
        db.session.commit()
        flash('Ciclo cerrado exitosamente', 'success')
    except Exception as e:
        flash(str(e), 'danger')
    return redirect(url_for('detalle_ciclo', id=id))

@app.route('/ciclo/<int:id>/venta', methods=['GET', 'POST'])
@login_required
def nueva_venta(id):
    ciclo = Ciclo.query.get_or_404(id)
    ventas_actuales = Venta.query.filter_by(ciclo_id=id).all()
    total_vendido = sum(v.cantidad for v in ventas_actuales)
    
    if request.method == 'POST':
        cantidad = int(request.form['cantidad'])
        precio_unitario = float(request.form['precio_unitario'])
        tipo = request.form['tipo']
        total = cantidad * precio_unitario
        
        if total_vendido + cantidad > ciclo.cantidad:
            flash('No hay suficientes unidades restantes', 'danger')
            return redirect(url_for('nueva_venta', id=id))
        
        pagado = 1 if tipo == 'cliente' else 0
        venta = Venta(
            ciclo_id=id,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            total=total,
            tipo=tipo,
            pagado=pagado
        )
        db.session.add(venta)
        db.session.commit()
        
        # Distribuir inmediatamente si es cliente
        if tipo == 'cliente' and pagado == 1:
            distribuir_venta(id, cantidad, precio_unitario)
        
        flash('Venta registrada', 'success')
        return redirect(url_for('detalle_ciclo', id=id))
    
    return render_template('venta_nueva.html', ciclo=ciclo, total_vendido=total_vendido)

@app.route('/venta/<int:venta_id>/pagar', methods=['POST'])
@login_required
def pagar_pasador(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    if venta.tipo == 'pasador' and venta.pagado == 0:
        venta.pagado = 1
        db.session.commit()
        distribuir_venta(venta.ciclo_id, venta.cantidad, venta.precio_unitario)
        flash('Pago de pasador registrado', 'success')
        
        # Verificar si el ciclo se puede cerrar automáticamente
        ciclo = Ciclo.query.get(venta.ciclo_id)
        ventas = Venta.query.filter_by(ciclo_id=venta.ciclo_id).all()
        total_vendido = sum(v.cantidad for v in ventas)
        todos_pagados = all(v.pagado == 1 for v in ventas)
        
        if total_vendido == ciclo.cantidad and todos_pagados and ciclo.estado == 'abierto':
            ciclo.estado = 'cerrado'
            ciclo.fecha_cierre = datetime.now()
            db.session.commit()
            flash('¡El ciclo se cerró automáticamente porque todas las unidades fueron vendidas y pagadas!', 'success')
    else:
        flash('Venta inválida o ya pagada', 'danger')
    return redirect(url_for('detalle_ciclo', id=venta.ciclo_id))

# ======================== INICIALIZAR BASE DE DATOS ========================
with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(username='admin').first():
        import os
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        admin = Usuario(username='admin', password_hash=generate_password_hash(admin_password))
        db.session.add(admin)
        db.session.commit()
        print("✅ Usuario admin creado")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)