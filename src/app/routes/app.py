import os
import logging 
##from app.routes import mqtt_handlers    
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_login import LoginManager
from flask import render_template
from flask_socketio import SocketIO
##from flask_mqtt import Mqtt
from werkzeug.security import generate_password_hash
from app.config.extensions import db
from src.database.models import User, Root 
from src.logs.config_log import configurar_logger
##from database.models import User, Root
#from logs.config_log import configurar_logger



##from app.routes.rfid import rfid_bp
##from app.routes.object import object_bp
##from app.routes.auth import auth_bp
##from app.routes.local import local_bp
##from app.routes.control_door import control_door_bp 
##from app.routes.esp32 import esp32_bp

BLOCKLIST = set()
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

app = Flask(__name__, 
            template_folder='../templates', 
            static_folder='../static')

from app.routes.auth import auth_bp
from app.routes.rfid import rfid_bp
from app.routes.object import object_bp
from app.routes.local import local_bp
from app.routes.control_door import control_door_bp 
from app.routes.esp32 import esp32_bp        
  
            

socketio = SocketIO(app, cors_allowed_origins="*")
logger = configurar_logger()

CORS(app)

##app.config['CELERY_BROKER_URL'] = broker_url
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BASE_DIR}/database/hermes.db"
app.config['JWT_SECRET_KEY'] = 'b3aee42cec430c26bd07ea5784fa0e02cc3cebbb55d841c88393ae286bc42155'
app.config['SECRET_KEY'] = '0abd4d73e603df0bfad74eb46586a961c4369cfcb2f6b5c5045c2297ca1337a0'
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['PROPAGATE_EXCEPTIONS'] = True
##app.config['CELERY_RESULT_BACKEND'] = 'db+sqlite:////app/database/results.sqlite'

##app.config['MQTT_BROKER_URL'] = 'test.mosquitto.org'
##app.config['MQTT_BROKER_PORT'] = 1883
##app.config['MQTT_USERNAME'] = ''
##app.config['MQTT_PASSWORD'] = ''
##app.config['MQTT_KEEPALIVE'] = 60
##app.config['MQTT_TLS_ENABLED'] = False

db.init_app(app)
##mqtt.init_app(app)
##celery.conf.update(app.config)
jwt = JWTManager(app)

login_manager = LoginManager()
login_manager.init_app(app)

##mqtt = Mqtt(app)


@app.before_request
def log_de_trafego():
    metodo = request.method       
    caminho = request.path        
    ip = request.remote_addr

    logger.info(f"Acesso | IP: {ip} | Método: {metodo} | Rota: {caminho}")

@app.errorhandler(Exception)
def erro_global(e):

    logger.error(f"Erro interno detectado: {e}", exc_info=True)
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
app.register_blueprint(control_door_bp )
app.register_blueprint(esp32_bp )

with app.app_context():
    db.create_all()
    try:
        if not User.query.filter_by(email="admin@thalon.com").first():
            
            root_entry = Root(
                nome="Admin Master",
                email="admin@thalon.com",
                senha=generate_password_hash("V9#rT2@qL7!mX4$zK8"),
                tipo_user='roots',
                senha_root="V9#rT2@qL7!mX4$zK8",
                nivel_permissao="total"
            )
            
            db.session.add(root_entry)
            db.session.commit()
            
            print("Usuário Root padrão criado com sucesso!")

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao criar o usuário Root padrão: {e}")


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
