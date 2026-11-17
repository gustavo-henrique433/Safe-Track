from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_login import login_user
from flask import request
from flask import send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from app.config.extensions import db
from src.database.models import User, Root, RFID, Object, Local, Historico_patrimonio
from flask_socketio import emit # Importação necessária
from werkzeug.utils import secure_filename
import time
import os

object_bp = Blueprint('object', __name__)

PASTA_UPLOADS = 'static/uploads'

@object_bp.route('/cadastrar_objeto', methods =['POST'])
@jwt_required()
def cadastrar_objeto():

    id_solicitante = get_jwt_identity()
    solicitante = User.query.get(id_solicitante)

    if not isinstance(solicitante, Root):
        return jsonify({'message': 'Acesso Negado: Apenas usuários Root podem cadastrar objetos.'}), 403

    nome = request.form.get('nome')
    descricao = request.form.get('descricao')
    especificacoes = request.form.get('especificacoes')
    local = request.form.get('local')
    uid_recebido = request.form.get('uid_recebido')
    imagem = request.files.get('imagem')

    if not nome or not descricao or not uid_recebido or not imagem or not local:
        return jsonify({'error': 'Preencha todos os campos !!'}), 400

    nome_arquivo_seguro = secure_filename(imagem.filename)
    caminho_completo = os.path.join(PASTA_UPLOADS, nome_arquivo_seguro)

    rfid_tag = RFID.query.filter_by(uid=uid_recebido).first()

    if not rfid_tag:
        return jsonify({'error': 'Tag RFID não encontrada no sistema. Cadastre-a primeiro.'}), 404

    local_encontrado  = Local.query.filter_by(id = local).first()

    if not local_encontrado:
        return jsonify({'error': 'Local não encontrado no sistema. Cadastre-o primiero.'}), 404    

    try:
        os.makedirs(PASTA_UPLOADS, exist_ok=True)
        imagem.save(caminho_completo)


        novo_objeto  = Object (
            id_rfid = rfid_tag.uid,
            nome = nome, 
            descricao = descricao, 
            especificacoes = especificacoes,
            id_lugar = local_encontrado.id,
            url_imagem=caminho_completo
         
        )

        db.session.add(novo_objeto)
        db.session.commit()

        return jsonify({'message':'Objeto cadastrado com sucesso !!', 'objeto': novo_objeto.nome }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify ({'error': f'Erro ao salvar no banco: {str(e)}'}), 500

@object_bp.route('/static/uploads/<path:filename>')
def serve_imagem(filename):
    diretorio_absoluto = os.path.abspath(PASTA_UPLOADS)
    return send_from_directory(diretorio_absoluto, filename)        


@object_bp.route('/recadastrar_objeto', methods =['PUT'])
@jwt_required()
def recadastrar_objeto():

    id_solicitante = get_jwt_identity()
    solicitante = User.query.get(id_solicitante)

    if not isinstance(solicitante, Root):
        return jsonify({'message': 'Acesso Negado: Apenas usuários Root podem recadastrar objetos.'}), 403

    data = request.get_json()

    if not data: 
        return jsonify({'error': 'JSON inválido'}), 400

    id_objeto = data.get('id_objeto')
    nova_uid = data.get('nova_uid')    


    objeto_encontrado = Object.query.filter_by(id=id_objeto).first()

    if not objeto_encontrado:
        return jsonify({'message': 'Insira o id de um objeto cadastrado  !! '}), 404

    uid_recebida = RFID.query.filter_by(uid = nova_uid).first()

    if not uid_recebida:
        return jsonify({'message': 'Insira uma UID valida ou cadastre uma nova !!'}), 404

    uid_existente = Object.query.filter_by(id_rfid = nova_uid).first()

    if uid_existente:
        return jsonify({'message': 'Este UID já está atribuido a outro objeto !!'}), 400

    try:

        objeto_encontrado.id_rfid = nova_uid
        db.session.commit()
        
        return jsonify({
            'message': 'Tag RFID do objeto atualizada com sucesso!', 
            'objeto': objeto_encontrado.nome,
            'nova_tag': objeto_encontrado.id_rfid
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro ao atualizar no banco: {str(e)}'}), 500    



@object_bp.route('/excluir_objeto', methods=['DELETE'])
@jwt_required()
def excluir_objeto():

    id_solicitante = get_jwt_identity()
    solicitante = User.query.get(id_solicitante)

    if not isinstance(solicitante, Root):
        return jsonify({'message': 'Acesso Negado: Apenas usuários Root podem excluir objetos do banco !!'}), 403

    data = request.get_json()

    if not data: 
        return jsonify({'error': 'JSON inválido'}), 400    

    objeto_excluir = data.get('objeto_excluir')

    objeto_encontrado = Object.query.filter_by(id = objeto_excluir).first()

    if not objeto_encontrado:
        return jsonify({'message': 'ID de objeto invalido ou inexistente'}), 404

    try: 
        db.session.delete(objeto_encontrado)
        db.session.commit()

        return jsonify({'message': 'Objeto excluido com sucesso !!'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro ao atualizar no banco: {str(e)}'}), 500    



@object_bp.route('/vizualizar_todos_objetos', methods=['GET'])
@jwt_required()
def listar_todos_objetos():


    todos_objetos = Object.query.all()
    lista_objetos = []

    for objeto in todos_objetos:
        if objeto.url_imagem:
            url_completa = f"{request.host_url}{objeto.url_imagem}"
        else:
            url_completa = None
        dados_objeto = {
            'id': objeto.id,
            'nome': objeto.nome,
            'descricao': objeto.descricao,
            'especificacoes': objeto.especificacoes,
            'id_lugar': objeto.id_lugar,
            'id_rfid': objeto.id_rfid,
            'url_imagem': url_completa
        }
        lista_objetos.append(dados_objeto)

    return jsonify({
        'message': 'Objetos listados com sucesso!',
        'total_objetos': len(lista_objetos),
        'objetos': lista_objetos
    }), 200   



@object_bp.route('/buscar_objeto_id/<int:id_objeto>', methods=['GET']) 
def buscar_objeto_id(id_objeto):
    
    objeto_encontrado = Object.query.filter_by(id = id_objeto).first()

    try:
        if not objeto_encontrado:
            objeto_nao_encontrado = Historico_patrimonio(
                id_objeto = None,
                id_usuario = None,
                acao = "buscar_objeto_id", 
                status_tentativa = "falha"
            )

            db.session.add(objeto_nao_encontrado)
            db.session.commit()

            return jsonify({'message': 'Este objeto não existe ou ID invalido !!'}), 404

        url_completa = None
        if objeto_encontrado.url_imagem:
            url_completa = f"{request.host_url}{objeto_encontrado.url_imagem}"       

        objeto_encontrado_historico = Historico_patrimonio(
                id_objeto = objeto_encontrado.id,
                id_usuario = None,
                acao = "buscar_objeto_id", 
                status_tentativa = "sucesso"
        )
        db.session.add(objeto_encontrado_historico)
        db.session.commit()


        return jsonify({
            'message': 'Objeto encontrado com sucesso!',
            'objeto': {
            'id': objeto_encontrado.id,
            'nome': objeto_encontrado.nome,
            'descricao': objeto_encontrado.descricao,
            'especificacoes': objeto_encontrado.especificacoes,
            'id_lugar': objeto_encontrado.id_lugar,
            'url_imagem': url_completa,
            'id_rfid': objeto_encontrado.id_rfid
        }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Erro interno no servidor ao registrar historico de patrimonio.'}), 500    


@object_bp.route('/buscar_objeto_uid/<string:uid_objeto>', methods=['GET']) 
def buscar_objeto_uid(uid_objeto):

    uid_encontrado = Object.query.filter_by(id_rfid = uid_objeto).first()

    try:
        if not uid_encontrado:
            objeto_nao_encontrado = Historico_patrimonio(
                id_objeto = None,
                id_usuario = None,
                acao = "buscar_objeto_uid", 
                status_tentativa = "falha"
            )

            db.session.add(objeto_nao_encontrado)
            db.session.commit()

            return jsonify({'message': 'Este objeto não existe ou UID invalido !!'}), 404

        url_completa = None
        if uid_encontrado.url_imagem:
            url_completa = f"{request.host_url}{uid_encontrado.url_imagem}"       

        nome_do_local = uid_encontrado.local_relacionado.endereco if uid_encontrado.local_relacionado else "Sem local"

        objeto_encontrado_historico = Historico_patrimonio(
            id_objeto = uid_encontrado.id,
            id_usuario = None,
            acao = "buscar_objeto_uid", 
            status_tentativa = "sucesso"
        )
        
        db.session.add(objeto_encontrado_historico)
        db.session.commit()

        return jsonify({
            'message': 'Objeto encontrado com sucesso!',
            'objeto': {
                'id': uid_encontrado.id,
                'nome': uid_encontrado.nome,
                'descricao': uid_encontrado.descricao,
                'especificacoes': uid_encontrado.especificacoes,
                'id_lugar': nome_do_local,
                'url_imagem': url_completa,
                'id_rfid': uid_encontrado.id_rfid
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Erro interno no servidor ao registrar historico de patrimonio.'}), 500

@object_bp.route('/buscar_objeto_nome/<string:nome_objeto>', methods=['GET']) 
def buscar_objeto_nome(nome_objeto):
    try:
        termo = f"%{nome_objeto}%"
        objetos_encontrados = Object.query.filter(Object.nome.like(termo)).all()

        if not objetos_encontrados:
            return jsonify ({'message': f'Nenhum Objeto encontrado contendo "{nome_objeto}" !!'}), 404

        lista_objetos = []
        for obj in objetos_encontrados:
            url_completa = None
            if obj.url_imagem:
                url_completa = f"{request.host_url}{obj.url_imagem}"
                
            lista_objetos.append({
                'id': obj.id,
                'nome': obj.nome,
                'descricao': obj.descricao,
                'especificacoes': obj.especificacoes,
                'id_lugar': obj.id_lugar,
                'url_imagem': url_completa,
                'id_rfid': obj.id_rfid
            })

        return jsonify({
            'message': 'Objetos encontrados com sucesso!',
            'objetos': lista_objetos 
        }), 200

    except Exception as e:
        return jsonify({'message': f'Erro no servidor ao buscar: {str(e)}'}), 500

















    


    




    

