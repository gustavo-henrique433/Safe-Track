from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_login import login_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.config.extensions import db
from src.database.models import User, Root, Local, RFID

local_bp = Blueprint('local', __name__)
BLOCKLIST = set()

@local_bp.route('/cadastrar_local', methods = ['POST'])
@jwt_required()
def cadastrar_local():

    id_solicitante = get_jwt_identity()
    solicitante = User.query.get(id_solicitante)

    if not isinstance(solicitante, Root):
        return jsonify({'message': 'Acesso Negado: Apenas usuários Root podem cadastrar objetos.'}), 403

    data = request.get_json()

    if not data:
        return jsonify({'message': 'Formato de dado invalido !!'})       

    endereco  = data.get('endereco')
    descricao = data.get('descricao')    
    responsavel = data.get('responsavel')

    if not endereco and descricao and responsavel:
        return jsonify({'message': 'Preencha todos os campos !! '})

    try:
        novo_local = Local(
            endereco = endereco, 
            descricao = descricao,
            responsavel = responsavel
        )

        db.session.add(novo_local)
        db.session.commit()

        return jsonify({'message': 'Novo local cadastrado com sucesso !!'}), 200

    
    except Exception as e:
        db.session.rollback()
        return jsonify ({'error': f'Erro ao salvar no banco: {str(e)}'}), 500

@local_bp.route('/editar_local', methods = ['PUT'])
@jwt_required()
def editar_local():

    id_solicitante = get_jwt_identity()
    solicitante = User.query.get(id_solicitante)

    if not isinstance(solicitante, Root):
        return jsonify({'message': 'Acesso Negado: Apenas usuários Root podem atualizar locais.'}), 403

    data = request.get_json()    

    if not data:
        return jsonify ({'error': 'Formato de dado invalido !!'}), 400

    local_alterado = data.get('local_alterado')    
    novo_endereco = data.get('novo_endereco')
    nova_descricao = data.get('nova_descricao')
    novo_responsavel = data.get('novo_responsavel')


    local_encontrado = Local.query.filter_by(id = local_alterado).first()

    if not local_encontrado:
        return jsonify ({'message': 'Nenhum local encontrado, insira um local valido !!'}), 404

    try:
        local_encontrado.endereco = novo_endereco
        local_encontrado.descricao = nova_descricao
        local_encontrado.responsavel = novo_responsavel
        
        db.session.commit()


        return jsonify({
            'message': 'Local atualizado !!!', 
            'endereco':  local_encontrado.endereco,
            'descricao': local_encontrado.descricao,
            'responsavel': local_encontrado.responsavel
        }), 200


    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro ao atualizar no banco: {str(e)}'}), 500    


##@local_bp.route('/excluir_local', methods = ['DELETE'])        

@local_bp.route('/listar_locais', methods = ['GET'])
def listar_salas():
    
    todos_locais = Local.query.all()
    lista_locais = []

    for local in todos_locais:
        dado_local = { 
            'id': local.id,
            'endereco': local.endereco,
            'descricao': local.descricao,
            'responsavel': local.responsavel
        }
        lista_locais.append(dado_local)


    return jsonify({
        'message': 'Locais listados com sucesso!',
        'total_locais': len(lista_locais),
        'locais': lista_locais
    }), 200       




                









    

    




