from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_login import login_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.config.extensions import db
from src.database.models import Esp32_registro

esp32_bp = Blueprint('esp32', __name__)
BLOCKLIST = set()

@esp32_bp.route('/cadastrar_esp32', methods = ['POST'])
def cadastrar_esp32():

    data = request.get_json()

    if not data:
        return jsonify({'message': 'Formato de dados invalidos !!'}),  400

    mac_adress = data.get('mac_adress')
    local = data.get('local')

    if not mac_adress:
        return jsonify ({'message': 'É necessario inserir o endereço Mac !!'}), 400

    if not local:
        return jsonify ({'message': 'É necessario inserir o local pertencente do esp32 !!'}), 400    

    try:
        novo_esp32 = Esp32_registro(
            mac = mac_adress, 
            local = local
        )    

        db.session.add(novo_esp32)
        db.session.commit()

        return jsonify ({'message': 'Esp32 cadastrado com sucesso !!'}), 200 

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Erro interno no servidor ao registrar acesso.'}), 500    

            


