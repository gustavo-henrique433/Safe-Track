import os
import logging 
from flask import Flask, request
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_login import LoginManager
from flask import render_template
from flask_socketio import SocketIO
from werkzeug.security import generate_password_hash
from app.config.extensions import db
from src.database.models import User, Root
from src.logs.config_log import iniciar_logs


from app.routes.rfid import rfid_bp
from app.routes.object import object_bp
from app.routes.auth import auth_bp
from app.routes.local import local_bp

BLOCKLIST = set()
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

app = Flask(__name__, 
            template_folder='../templates', 
            static_folder='../static')

socketio = SocketIO(app, cors_allowed_origins="*")

CORS(app)

##app.config['CELERY_BROKER_URL'] = broker_url
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BASE_DIR}/database/hermes.db"
app.config['JWT_SECRET_KEY'] = '************'
app.config['SECRET_KEY'] = '****************'
app.config['JWT_TOKEN_LOCATION'] = ['headers']
##app.config['CELERY_RESULT_BACKEND'] = 'db+sqlite:////app/database/results.sqlite'

db.init_app(app)
##celery.conf.update(app.config)
jwt = JWTManager(app)

login_manager = LoginManager()
login_manager.init_app(app)

@app.before_request
def log_de_trafego():
    metodo = request.method       
    caminho = request.path        
    ip = request.remote_addr

    logging.info(f"Acesso | IP: {ip} | Método: {metodo} | Rota: {caminho}")

@app.errorhandler(Exception)
def erro_global(e):

    logging.error(f"Erro interno detectado: {e}", exc_info=True)
    return jsonify({"message": "Ops! Ocorreu um erro interno no servidor."}), 500    


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload):
    return jwt_payload["jti"] in BLOCKLIST

@rfid_bp.route('/')
def index():
    return render_template('index.html')


app.register_blueprint(rfid_bp)
app.register_blueprint(object_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(local_bp)

with app.app_context():
    db.create_all()
    try:
        if not User.query.filter_by(email="admin@thalon.com").first():
            admin_user = User(
                nome="Admin Master",
                email="admin@thalon.com",
                senha=generate_password_hash("admin123"),
                type='root'
            )
            db.session.add(admin_user)
            db.session.commit()

            root_entry = Root(
                id=admin_user.id,
                senha_root="root123",
                nivel_permissao="total"
            )
            
            db.session.add(admin_root)
            db.session.commit()
            print("Usuário Root padrão criado com sucesso!")

    except Exception as e:
        db.session.rollback()

        print(f"Erro ao criar o usuário Root padrão: {e}")



if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
