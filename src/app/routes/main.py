
from flask import Blueprint, render_template, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

main_bp = Blueprint('main', __name__)

@main_bp.route('/home_api', methods=['GET'])
def home_aí():
    return "A API está rodando !!!  "