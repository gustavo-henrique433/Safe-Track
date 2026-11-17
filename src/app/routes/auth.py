from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_login import login_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.config.extensions import db
from src.database.models import User, Root, RFID, Object

auth_bp = Blueprint('auth', __name__)
BLOCKLIST = set()

@auth_bp.route('/registrar_usuario', methods=['POST'])
def registrar_ususrios():

    data = request.get_json()

    nome = data.get('nome')
    email = data.get('email')
    senha = data.get('senha')

    if nome and email and senha:
        if User.query.filter_by(email=email).first():
            return jsonify({'message:' 'Esse email já foi cadastrado !!'}), 400

        senha_hash = generate_password_hash(senha)    
        usuario_registrado = User(nome=nome, email=email, senha=senha_hash, tipo_user='users')
        db.session.add(usuario_registrado)
        db.session.commit()

        return jsonify({'message': 'Novo usuario registrado com sucesso !!'}), 201
 
    else:
        return jsonify({'message': 'Preencha todos os campos do cadastro !!'}), 400
    

@auth_bp.route('/registrar_root', methods=['POST'])
@jwt_required()
def registrar_root():

    id_solicitante = get_jwt_identity()
    solicitante = User.query.get(id_solicitante)

    if not isinstance(solicitante, Root):
        return jsonify({'message': 'Acesso Negado: Apenas usuários Root podem criar novos Roots.'}), 403
    
    
    data = request.get_json()
    nome = data.get('nome')
    email = data.get('email')
    senha_root = data.get('senha_root')
    nivel_permissao = data.get('nivel_permissao')

    if not all([nome, email,  senha_root, nivel_permissao]):
        return jsonify({'message': 'Preencha todos os campos !!'}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email já cadastrado'}), 400
    
    senha_hash = generate_password_hash(senha_root)   
    

    novo_root = Root(
        nome=nome, 
        email=email, 
        tipo_user='root', 
        senha_root=senha_hash, 
        nivel_permissao=nivel_permissao
    )

    db.session.add(novo_root)
    db.session.commit()

    return jsonify({'message': 'Novo Root registrado com sucesso !!'}), 201

@auth_bp.route('/atribuir_rfid_usuario', methods = ['POST'])
@jwt_required()
def atribuir_rfid():

    id_solicitante = get_jwt_identity()
    solicitante = User.query.get(id_solicitante)

    if not isinstance(solicitante, Root):
        return jsonify({'message': 'Acesso Negado: Apenas usuários Root podem realizar essa ação !!'}), 403

    data = request.get_json()

    if not data:
        return jsonify ({'message': 'formato de dado invalido !!'}), 400

    id_usuario = data.get('id_usuario')
    uid_usuario = data.get('uid_usuario')

    usuario_encontrado = User.query.filter_by(id = id_usuario, status_conta =True).first()

    if not usuario_encontrado:
        return jsonify ({'message': 'Usuario não encontrado !!'}), 404

    uid_encontrada = RFID.query.filter_by(uid = uid_usuario).first()

    if not uid_encontrada:
        return jsonify ({'message': 'Tag RFID não encontrada !!'}), 404

    verificar_objeto_cadastrado = Object.query.filter_by(id_rfid = uid_usuario).first()
    if verificar_objeto_cadastrado:
        return jsonify ({'message': 'Tag já em uso por um objeto !!'}), 409

    verificar_usuario_cadastrado = User.query.filter_by(credencial_rfid = uid_usuario).first()    
    if  verificar_usuario_cadastrado:
        return jsonify({'message': 'Esta Tag já está em uso por outro usuario !!'}), 409

    try:
        usuario_encontrado.credencial_rfid = uid_usuario
        db.session.commit()

        return jsonify ({
            'message': 'Tag RFID atribuida a usuario com sucesso!', 
            'usuario':  usuario_encontrado.nome,
            'credencial_rfid':  usuario_encontrado.credencial_rfid
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro ao atualizar no banco: {str(e)}'}), 500     


@auth_bp.route('/visualizar_todos_usuarios', methods=['GET'])
@jwt_required()
def listar_usuarios_teste():

    id_solicitante = get_jwt_identity()
    solicitante = User.query.get(id_solicitante)

    if not isinstance(solicitante, Root):
        return jsonify({'message': 'Acesso Negado: Apenas usuários Root podem realizar essa ação !!'}), 403


    try:
        usuarios_db = User.query.all()
        lista_usuarios = []

        for u in usuarios_db:
            lista_usuarios.append({
                'id': u.id,
                'nome': u.nome,
                'email': u.email,
                'credencial_rfid': u.credencial_rfid  
            })

        return jsonify({
            'total': len(lista_usuarios),
            'usuarios': lista_usuarios
        }), 200

    except Exception as e:
        return jsonify({'error': f'Erro ao listar usuarios: {str(e)}'}), 500        

@auth_bp.route('/buscar_usuario_uid/<string:uid>', methods=['GET'])
def buscar_usuario_uid(uid):
    usuario = User.query.filter_by(credencial_rfid=uid).first()
    if not usuario:
        return jsonify({'message': 'Usuário não encontrado'}), 404
        
    return jsonify({
        'usuario': {
            'nome': usuario.nome,
            'email': usuario.email,
            'credencial_rfid': usuario.credencial_rfid
        }
    }), 200        

    

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    senha = data.get('senha')
    usuario = User.query.filter_by(email=email).first()

    if usuario and check_password_hash(usuario.senha, senha):
        access_token = create_access_token(identity=str(usuario.id))
        login_user(usuario)
        return jsonify({
            "message": "Login realizado com sucesso !!",
            "access_token": access_token,
            "user_type": usuario.tipo_user
        }), 200

    else:
        return jsonify({'message': 'Erro, email ou senha errados !!'}), 401
    

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    BLOCKLIST.add(jti)
    return jsonify({"message": "Logout realizado com sucesso"}), 200



    
        

