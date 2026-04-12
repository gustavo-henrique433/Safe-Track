from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_login import login_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.config.extensions import db
from src.database.models import User, Root

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
        usuario_registrado = User(nome=nome, email=email, senha=senha_hash, type='user')
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
        type='root', 
        senha_root=senha_hash, 
        nivel_permissao=nivel_permissao
    )

    db.session.add(novo_root)
    db.session.commit()

    return jsonify({'message': 'Novo Root registrado com sucesso !!'}), 201


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
            "user_type": usuario.type 
        }), 200

    else:
        return jsonify({'message': 'Erro, email ou senha errados !!'}), 401
    

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    BLOCKLIST.add(jti)
    return jsonify({"message": "Logout realizado com sucesso"}), 200



    
        

