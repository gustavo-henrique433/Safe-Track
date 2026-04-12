from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_login import login_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.config.extensions import db
from src.database.models import User, Root, RFID
from flask_socketio import emit # Importação necessária
import time

ultimo_contato_esp = 0

rfid_bp = Blueprint('rfid', __name__)

@rfid_bp.route('/cadastrar_rfid', methods=['POST'])
def receber_dados():

    global ultimo_contato_esp

    data =  request.get_json()

    if not data:
        return jsonify({'error': 'JSON inválido'}), 400

    uid = data.get('uid')
    date = data.get('date')

    if uid:
        if RFID.query.filter_by(uid=uid).first():
            return jsonify ({'message': 'Tag RFID já cadastrada !!'}),  409

        rfid_registrado = RFID(uid=uid, date=date)

        db.session.add(rfid_registrado)
        db.session.commit()

        ultimo_contato_esp = time.time()
        ip_esp = request.remote_addr

       
        emit('rfid_update', {
            'message': 'DADOS ENVIADOS!',
            'uid': uid,
            'ip': ip_esp,
            'date': date
        }, namespace='/', broadcast=True)

        return jsonify({'message': 'Tag RFID cadastrada no banco de dados !!'})

    else: 
       return jsonify({'message': 'UID não enviado!!'}), 400