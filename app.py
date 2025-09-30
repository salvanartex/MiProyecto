



import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_bcrypt import Bcrypt
from models import init_db, get_db_connection
import psycopg2
import psycopg2.extras

# Inicializar app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key-for-dev')

bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Modelo de usuario
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT id, username FROM usuarios WHERE id = %s', (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user:
        return User(user['id'], user['username'])
    return None

# Función para verificar si es admin
def is_admin():
    return current_user.is_authenticated and current_user.username == 'admin'

# Crear usuario admin si no existe
def create_admin_user():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM usuarios WHERE username = 'admin'")
    if not cur.fetchone():
        hashed = bcrypt.generate_password_hash("salvatore777").decode('utf-8')
        cur.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)", ('admin', hashed))
        conn.commit()
        print("✅ Usuario admin creado: admin / salvatore777")
    cur.close()
    conn.close()

# Inicializar base de datos y crear admin
init_db()
create_admin_user()



# Ruta para ver y gestionar compras propias en un evento
@app.route('/mis-compras/<int:evento_id>', methods=['GET'])
@login_required
def mis_compras(evento_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT nombre FROM eventos WHERE id = %s', (evento_id,))
    evento = cur.fetchone()
    if not evento:
        flash('Evento no encontrado')
        return redirect(url_for('dashboard'))
    cur.execute('''SELECT * FROM compras WHERE evento_id = %s AND comprador_id = %s ORDER BY id DESC''', (evento_id, current_user.id))
    compras_usuario = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('mis_compras.html', evento_id=evento_id, evento_nombre=evento['nombre'], compras_usuario=compras_usuario)

# Ruta para eliminar una compra propia
@app.route('/eliminar-compra/<int:compra_id>/<int:evento_id>', methods=['POST'])
@login_required
def eliminar_compra(compra_id, evento_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM compras WHERE id = %s AND comprador_id = %s', (compra_id, current_user.id))
    conn.commit()
    cur.close()
    conn.close()
    flash('Compra eliminada correctamente.')
    return redirect(url_for('mis_compras', evento_id=evento_id))

# Ruta para que el admin cree usuarios
@app.route('/admin/create-user', methods=['GET', 'POST'])
@login_required
def admin_create_user():
    if not is_admin():
        flash('Acceso denegado. Solo el administrador puede crear usuarios.')
        return redirect(url_for('dashboard'))
    error = None
    success = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            error = 'Usuario y contraseña son obligatorios.'
        else:
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                hashed = bcrypt.generate_password_hash(password).decode('utf-8')
                cur.execute('INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)', (username, hashed))
                conn.commit()
                success = f'Usuario "{username}" creado exitosamente.'
            except psycopg2.IntegrityError:
                conn.rollback()
                error = 'El nombre de usuario ya existe.'
            finally:
                cur.close()
                conn.close()
    # Cargar lista de usuarios para administración
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, username FROM usuarios ORDER BY username")
    usuarios = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin_create_user.html', error=error, success=success, usuarios=usuarios)

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not is_admin():
        flash('Acceso denegado.')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # No permitir borrar al usuario admin
    cur.execute('SELECT username FROM usuarios WHERE id = %s', (user_id,))
    row = cur.fetchone()
    if not row:
        flash('Usuario no encontrado.')
    elif row['username'] == 'admin':
        flash('No se puede eliminar al usuario admin.')
    else:
        cur2 = conn.cursor()
        cur2.execute('DELETE FROM usuarios WHERE id = %s', (user_id,))
        conn.commit()
        cur2.close()
        flash('Usuario eliminado correctamente.')
    cur.close()
    conn.close()
    return redirect(url_for('admin_create_user'))

# Rutas
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute('SELECT id, username, password_hash FROM usuarios WHERE username = %s', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and bcrypt.check_password_hash(user['password_hash'], password):
            login_user(User(user['id'], user['username']))
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Mostrar solo eventos NO asociados al usuario logueado
    cur.execute('SELECT id, nombre FROM eventos WHERE usuario_id != %s ORDER BY nombre', (current_user.id,))
    eventos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('dashboard.html', eventos=eventos)

@app.route('/register', methods=['GET', 'POST'])
def register():
    return render_template('register_disabled.html')

@app.route('/crear-evento', methods=['GET', 'POST'])
@login_required
def crear_evento():
    if not is_admin():
        flash('Acceso denegado. Solo el administrador puede crear eventos.')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT id, username FROM usuarios ORDER BY username')
    usuarios = cur.fetchall()
    cur.execute('SELECT id, nombre FROM eventos ORDER BY nombre')
    eventos = cur.fetchall()
    cur.close()
    if request.method == 'POST':
        if 'eliminar_evento' in request.form:
            evento_id = request.form['eliminar_evento']
            cur = conn.cursor()
            cur.execute('DELETE FROM eventos WHERE id = %s', (evento_id,))
            conn.commit()
            cur.close()
            flash('Evento eliminado correctamente.')
            return redirect(url_for('crear_evento'))
        nombre = request.form.get('nombre', '').strip()
        usuario_id = request.form.get('usuario_id')
        if not nombre or not usuario_id:
            flash('El nombre del evento y el usuario son obligatorios.')
        else:
            cur = conn.cursor()
            try:
                cur.execute('INSERT INTO eventos (nombre, usuario_id) VALUES (%s, %s)', (nombre, usuario_id))
                conn.commit()
                flash(f'Evento "{nombre}" creado exitosamente.')
                return redirect(url_for('dashboard'))
            except psycopg2.IntegrityError:
                conn.rollback()
                flash('Ya existe un evento con ese nombre.')
            finally:
                cur.close()
                conn.close()
            return render_template('crear_evento.html', usuarios=usuarios, eventos=eventos)
    conn.close()
    return render_template('crear_evento.html', usuarios=usuarios, eventos=eventos)

# Ruta para eliminar evento (POST)
@app.route('/eliminar-evento/<int:evento_id>', methods=['POST'])
@login_required
def eliminar_evento(evento_id):
    if not is_admin():
        flash('Acceso denegado.')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM eventos WHERE id = %s', (evento_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Evento eliminado correctamente.')
    return redirect(url_for('crear_evento'))

@app.route('/evento/<int:evento_id>')
@login_required
def ver_evento(evento_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute('SELECT nombre FROM eventos WHERE id = %s', (evento_id,))
    evento = cur.fetchone()
    if not evento:
        flash('Evento no encontrado')
        return redirect(url_for('dashboard'))
    
    cur.execute('''
        SELECT c.*, u.username AS comprador
        FROM compras c
        JOIN usuarios u ON c.comprador_id = u.id
        WHERE c.evento_id = %s
        ORDER BY c.id DESC
    ''', (evento_id,))
    compras = cur.fetchall()

    # Compras solo del usuario actual para este evento
    compras_usuario = [c for c in compras if c['comprador_id'] == current_user.id]

    total_general = sum(c['monto'] for c in compras) if compras else 0
    total_usuario = sum(c['monto'] for c in compras if c['comprador_id'] == current_user.id)

    gastos_por_usuario = {}
    for c in compras:
        comprador = c['comprador']
        gastos_por_usuario[comprador] = gastos_por_usuario.get(comprador, 0) + float(c['monto'])

    cur.close()
    conn.close()

    return render_template(
        'add_purchase.html',
        evento_id=evento_id,
        evento_nombre=evento['nombre'],
        compras=compras,
        total_general=total_general,
        total_usuario=total_usuario,
        gastos_por_usuario=gastos_por_usuario,
        compras_usuario=compras_usuario
    )

@app.route('/compra', methods=['POST'])
@login_required
def agregar_compra():
    evento_id = request.form['evento_id']
    descripcion = request.form['descripcion']
    # No se solicita destinatario; usamos el username del comprador para satisfacer NOT NULL
    destinatario = current_user.username
    try:
        monto = float(request.form['monto'])
    except ValueError:
        flash('Monto inválido')
        return redirect(url_for('ver_evento', evento_id=evento_id))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO compras (evento_id, comprador_id, destinatario, descripcion, monto)
        VALUES (%s, %s, %s, %s, %s)
    ''', (evento_id, current_user.id, destinatario, descripcion, monto))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('mis_compras', evento_id=evento_id))


# --- Ruta /cuenta-total movida junto al resto de rutas ---

@app.route('/cuenta-total')
@login_required
def cuenta_total():
    if not is_admin():
        flash('Acceso denegado. Solo el administrador puede ver la cuenta total.')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Obtener aportaciones de compras (solo de usuarios que NO son 'admin') para TODOS los eventos
    cur.execute('''
        SELECT c.comprador_id, u.username, SUM(c.monto) AS total_aportado
        FROM compras c
        JOIN usuarios u ON c.comprador_id = u.id
        WHERE u.username != 'admin'
        GROUP BY c.comprador_id, u.username
    ''')
    aportaciones = {row['username']: float(row['total_aportado']) for row in cur.fetchall()}
    # Obtener TODOS los usuarios registrados EXCEPTO 'admin'
    cur.execute("SELECT username FROM usuarios WHERE username != 'admin' ORDER BY username")
    usuarios_normales = [row['username'] for row in cur.fetchall()]
    # Si no hay usuarios normales, mostrar advertencia
    if not usuarios_normales:
        flash('No hay usuarios participantes (sin contar al admin).')
        return redirect(url_for('dashboard'))
    # Calcular total general (solo de usuarios normales)
    total_general = sum(aportaciones.get(u, 0) for u in usuarios_normales)
    num_usuarios = len(usuarios_normales)
    cuota_justa = total_general / num_usuarios if num_usuarios > 0 else 0
    # Calcular saldo por usuario (solo usuarios normales)
    saldos = {}
    for usuario in usuarios_normales:
        aportado = aportaciones.get(usuario, 0)
        saldo = aportado - cuota_justa
        saldos[usuario] = {
            'aportado': aportado,
            'cuota_justa': cuota_justa,
            'saldo': saldo
        }
    cur.close()
    conn.close()
    return render_template(
        'cuenta_total.html',
        total_general=total_general,
        num_usuarios=num_usuarios,
        cuota_justa=cuota_justa,
        saldos=saldos
    )


@app.route('/cuentas/<int:evento_id>')
@login_required
def cuentas(evento_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Verificar que el evento existe
    cur.execute('SELECT nombre FROM eventos WHERE id = %s', (evento_id,))
    evento = cur.fetchone()
    if not evento:
        flash('Evento no encontrado')
        return redirect(url_for('dashboard'))
    
    # Obtener el usuario asociado al evento
    cur.execute('SELECT usuario_id FROM eventos WHERE id = %s', (evento_id,))
    evento_row = cur.fetchone()
    usuario_evento_id = evento_row['usuario_id'] if evento_row else None

    # Obtener nombre de usuario asociado al evento
    usuario_evento_username = None
    if usuario_evento_id:
        cur.execute('SELECT username FROM usuarios WHERE id = %s', (usuario_evento_id,))
        user_row = cur.fetchone()
        if user_row:
            usuario_evento_username = user_row['username']

    # Obtener aportaciones de compras (solo de usuarios que NO son 'admin' NI el usuario asociado al evento)
    cur.execute('''
        SELECT c.comprador_id, u.username, SUM(c.monto) AS total_aportado
        FROM compras c
        JOIN usuarios u ON c.comprador_id = u.id
        WHERE c.evento_id = %s AND u.username != 'admin' AND u.username != %s
        GROUP BY c.comprador_id, u.username
    ''', (evento_id, usuario_evento_username))
    aportaciones = {row['username']: float(row['total_aportado']) for row in cur.fetchall()}

    # Obtener TODOS los usuarios registrados EXCEPTO 'admin' y el usuario asociado al evento
    cur.execute("SELECT username FROM usuarios WHERE username != 'admin' AND username != %s ORDER BY username", (usuario_evento_username,))
    usuarios_normales = [row['username'] for row in cur.fetchall()]

    # Si no hay usuarios normales, mostrar advertencia
    if not usuarios_normales:
        flash('No hay usuarios participantes (sin contar al admin ni el usuario asociado al evento).')
        return redirect(url_for('ver_evento', evento_id=evento_id))

    # Calcular total general (solo de usuarios normales)
    total_general = sum(aportaciones.get(u, 0) for u in usuarios_normales)
    num_usuarios = len(usuarios_normales)
    cuota_justa = total_general / num_usuarios if num_usuarios > 0 else 0

    # Calcular saldo por usuario (solo usuarios normales)
    saldos = {}
    for usuario in usuarios_normales:
        aportado = aportaciones.get(usuario, 0)
        saldo = aportado - cuota_justa
        saldos[usuario] = {
            'aportado': aportado,
            'cuota_justa': cuota_justa,
            'saldo': saldo
        }
    
    cur.close()
    conn.close()
    
    return render_template(
        'cuentas.html',
        evento_id=evento_id,
        evento_nombre=evento['nombre'],
        total_general=total_general,
        num_usuarios=num_usuarios,
        cuota_justa=cuota_justa,
        saldos=saldos
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)