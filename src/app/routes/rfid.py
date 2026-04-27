from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_login import login_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.config.extensions import db
from src.database.models import User, Root, RFID, Object
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

    tag_verificar = RFID.query.filter_by(uid = uid).first()
 
    if not tag_verificar:
	    rfid_registrado = RFID(uid = uid, date=date)
	    db.session.add(rfid_registrado)
	    db.session.commit()
	    mensagem = 'Tag RFID cadastrada !!'

    else:
	    mensagem = 'Tag já cadastrada !!'

    objeto_vinculado = Object.query.filter_by(id_rfid =uid).first()	
  
    ultimo_contato_esp = time.time()
    ip_esp = request.remote_addr	

    emit('rfid_update', {
	
        'message': mensagem,
        'uid': uid,
	    'ip': ip_esp,
	    'tem_objeto': True if objeto_vinculado else False
    }, namespace='/', broadcast=True)  

    return jsonify({'message': 'Leitura processada !!'}), 200 	 

@rfid_bp.route('/excluir_rfid', methods=['DELETE'])      
@jwt_required()
def excluir_rfid():

    id_solicitante = get_jwt_identity()
    solicitante = User.query.get(id_solicitante)

    if not isinstance(solicitante, Root):
        return jsonify({'message': 'Acesso Negado: Apenas usuários Root podem realizar essa ação !!.'}), 403

    data = request.get_json()

    if not data:
        return jsonify({'message': 'Formato de dado invalido, esperado JSON !!'}), 400

    uid_recebido = data.get('uid_recebido')

    uid_existente = RFID.query.filter_by(uid=uid_recebido).first()

    if not uid_existente:
        return jsonify({'message': 'Código RFID invalido ou inexistente !! '}),  404

    objeto_vinculado = Object.query.filter_by(id_rfid = uid_recebido).first()
        
    if objeto_vinculado:
        return jsonify({
            'message': f'Falha: Esta tag está vinculada ao objeto "{objeto_vinculado.nome}". '
                       'Desvincule ou recadastre o objeto antes de apagar a tag.'
        }), 400

    try:
        db.session.delete(uid_existente)
        db.session.commit()

        return jsonify({'message': 'Tag RFID apagada com sucesso !!'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify ({'error': f'Erro ao apagar do banco: {str(e)}'}), 500    

@rfid_bp.route('/vizualizar_todos_rfid', methods =['GET'])
def listar_todos_rfid():

    todos_rfid = RFID.query.all()
    lista_rfids = []

    for rfid in todos_rfid:
        objeto_encontrado = Object.query.filter_by(id_rfid=rfid.uid).first()
        
        nome_objeto = objeto_encontrado.nome if objeto_encontrado else "Tag Livre"

        dado_rfid = {
            'uid': rfid.uid,
            'date': rfid.date,
            'objeto_cadastrado': nome_objeto 
        }

        lista_rfids.append(dado_rfid)

    return jsonify({
        'message': 'Tags RFID listadas: ',
        'total_objetos': len(lista_rfids),
        'objetos': lista_rfids
    }), 200


@rfid_bp.route('/buscar_rfid/<string:uid_rfid>', methods = ['GET'])
def buscar_rfid(uid_rfid):

    rfid_encontrado = RFID.query.filter_by(uid = uid_rfid).first()

    if not rfid_encontrado:
        return jsonify ({'message': 'Tag RFID não encontrada ou invalida !!'}), 400

    return jsonify({
        'message': 'Tag RFID encontrado com sucesso!',
        'objeto': {
            'uid': rfid_encontrado.uid,
            'data de criação': rfid_encontrado.date
        }
    }), 200
    

 


        






    
        

