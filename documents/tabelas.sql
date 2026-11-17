CREATE TABLE rfid (
	uid VARCHAR NOT NULL, 
	date VARCHAR(50) NOT NULL, 
	PRIMARY KEY (uid)
);
CREATE TABLE local (
	id INTEGER NOT NULL, 
	endereco VARCHAR(250) NOT NULL, 
	descricao TEXT NOT NULL, 
	responsavel VARCHAR(150) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE users (
	id INTEGER NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	email VARCHAR(100) NOT NULL, 
	senha VARCHAR(50) NOT NULL, 
	tipo_user VARCHAR(20) NOT NULL, 
	credencial_rfid INTEGER, 
	status_conta BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email), 
	UNIQUE (credencial_rfid), 
	FOREIGN KEY(credencial_rfid) REFERENCES rfid (uid)
);
CREATE TABLE object (
	id INTEGER NOT NULL, 
	id_rfid VARCHAR NOT NULL, 
	id_lugar INTEGER, 
	nome VARCHAR NOT NULL, 
	descricao TEXT NOT NULL, 
	especificacoes TEXT NOT NULL, 
	url_imagem VARCHAR(255), 
	PRIMARY KEY (id), 
	UNIQUE (id_rfid), 
	FOREIGN KEY(id_rfid) REFERENCES rfid (uid), 
	FOREIGN KEY(id_lugar) REFERENCES local (id)
);
CREATE TABLE registro_acesso (
	id INTEGER NOT NULL, 
	id_rfid VARCHAR, 
	id_local INTEGER NOT NULL, 
	horario DATETIME NOT NULL, 
	status_tentativa VARCHAR(20), 
	PRIMARY KEY (id), 
	FOREIGN KEY(id_rfid) REFERENCES rfid (uid), 
	FOREIGN KEY(id_local) REFERENCES local (id)
);
CREATE TABLE esp32_registro (
	mac VARCHAR NOT NULL, 
	local INTEGER, 
	PRIMARY KEY (mac), 
	FOREIGN KEY(local) REFERENCES local (id)
);
CREATE TABLE roots (
	id INTEGER NOT NULL, 
	senha_root VARCHAR(100) NOT NULL, 
	nivel_permissao VARCHAR(50) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES users (id)
);
CREATE TABLE historico_patrimonio (
	id INTEGER NOT NULL, 
	id_objeto INTEGER, 
	id_usuario INTEGER, 
	acao VARCHAR NOT NULL, 
	horario DATETIME NOT NULL, 
	status_tentativa VARCHAR(20), 
	PRIMARY KEY (id), 
	FOREIGN KEY(id_objeto) REFERENCES object (id), 
	FOREIGN KEY(id_usuario) REFERENCES users (id)
);
