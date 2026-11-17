import pytest
import app


from app.routes import app
from app.routes import auth 
from app.routes.app import app



@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
@pytest.mark.parametrize("email, senha, status_esperado", [
    ("admin@thalon.com", "V9#rT2@qL7!mX4$zK8", 200), ##Conta e senha corretas
    ("admin@thalon.com", "admin123", 401),     
    ("admin@thalon.com", "senha_errada", 401), 
    ("fantasma@thalon.com", "admin123", 404),  
    ("", "admin123", 400),                     
])
def test_login_dinamico(client, email, senha, status_esperado):
    payload = {
        "email": email,
        "senha": senha
    }
    
    resposta = client.post("/auth/login", json=payload)
    
    assert resposta.status_code == status_esperado