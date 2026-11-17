from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_login import login_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.config.extensions import db
from src.database.models import User, Root, Registro_Acesso, Local

control_door_bp  = Blueprint('control_door', __name__)
BLOCKLIST = set()

@control_door_bp.route('/acessar_porta', methods = ['POST'])
def abrir_porta():
    
    data = request.get_json()

    if not data:
        return jsonify({'message': 'Formato de dado invalido !!'}), 400

    uid_solicitante = data.get('uid_solicitante')    
    id_local = data.get('local')

    credencial_acesso = User.query.filter_by(credencial_rfid=uid_solicitante, status_conta=True).first()
    local_encontrado = Local.query.filter_by(id=id_local).first()


    if not local_encontrado:
        return jsonify({'message': 'Equipamento de acesso nao reconhecido.'}), 404

    try:
        if not credencial_acesso:
            registro_falha = Registro_Acesso(
                id_rfid=uid_solicitante,
                id_local=local_encontrado.id,
                status_tentativa="Negado"
            )
            db.session.add(registro_falha)
            db.session.commit()
            
            return jsonify({'message': 'Acesso negado', 'abrir': False}), 403

        registro_sucesso = Registro_Acesso(
            id_rfid=uid_solicitante,
            id_local=local_encontrado.id,
            status_tentativa="Liberado"
        )
        db.session.add(registro_sucesso)
        db.session.commit()
        
        return jsonify({
            'message': f'Abrindo porta para {credencial_acesso.nome}',
            'abrir': True
        }), 200    

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Erro interno no servidor ao registrar acesso.'}), 500