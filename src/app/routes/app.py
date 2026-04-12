import os
from flask import Flask
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_login import LoginManager
from flask import render_template
from flask_socketio import SocketIO
from werkzeug.security import generate_password_hash
from app.config.extensions import db
from src.database.models import User, Root


from app.routes.rfid import rfid_bp

BLOCKLIST = set()
##broker_url = os.getenv('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//')
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

app = Flask(__name__, 
            template_folder='../templates', 
            static_folder='../static')

socketio = SocketIO(app, cors_allowed_origins="*")

CORS(app)

##app.config['CELERY_BROKER_URL'] = broker_url
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BASE_DIR}/database/hermes.db"
app.config['JWT_SECRET_KEY'] = 'k1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7'
app.config['SECRET_KEY'] = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6'
app.config['JWT_TOKEN_LOCATION'] = ['headers']
##app.config['CELERY_RESULT_BACKEND'] = 'db+sqlite:////app/database/results.sqlite'

db.init_app(app)
##celery.conf.update(app.config)
jwt = JWTManager(app)

login_manager = LoginManager()
login_manager.init_app(app)

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
            db.session.add(root_entry)
            db.session.commit()
    except Exception:
        db.session.rollback()



if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)