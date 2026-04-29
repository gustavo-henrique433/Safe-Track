<h1 align="center">Safe-Track:</h1>

<p align="center">
  <img width="800" height="436" alt="Gemini_Generated_Image_q9wnb9q9wnb9q9wn" src="https://github.com/user-attachments/assets/7d689ae1-9358-4bc4-b568-ed0320d3b80b" />
</p>

---

## O que é:

<p>
Safe-Track é um projeto desenvolvido por alunos do 4° semestre de ADS da Fatec Campinas com o objetivo de proporcionar segurança e automação de patrimonios e ambientes.
</p>

---

## Tecnologias:

- Python + Flask  
- C++  
- Docker  
- ESP32  
- Sensor RFID RC522  
- Cloud OpenStack  

---

## Requisitos:

<p>Sistema Linux nativo ou WSL com docker e docker-compose instalados</p>
<p>Porta 5001 liberada para conexão com a API</p>
<p>IDE para sistemas embarcados como arduibo IDE</p>
<p>Micro-controlador ESP32</p>

---

## Arquitetura: Terminar

<p>- Python + Flask + SQLAlchemy: Usado para a criação e elaboração das rotas da API onde ocorre o recebimento e  envio das informações, lógica e de processamento, além da elaboração do banco de dados;</p>  
<p>- Docker;</p>
<p>- C++: Usado para a programação das instruções do ESP32 e sensores;</p>
<p>- JavaScript e HTML</p>

## Estrutura de diretorios:

<p>Na raiz do projeto se encontram três diretorios principais que contém o cerebro do projeto</p>
<p>/docker: É onde se localiza os arquivos DockerFile e Docker-compose necessarios para a montagem e funcionamento do container</p>
<p>/src: É divido em outros dois subdiretorios sendo estes /app e /database </p>
<p>/app: É onde está o Back-end e Front-End do projeto e contém pastas como as rotas da API, Statics e Templates em que fica localizado todo o front-end</p>
<p>/database: Banco de dados do sistema e contém arquivos como como Hermes.db  e model.py</p>


## Como subir o ambiente:

### Subindo a API

<p>
Para subir o ambiente é necessario navegar atá o diretorio docker, uma vez dentro dele basta rodar o comando para subir o container
</p>

```bash
cd docker
docker-compose up --build
```
<p>- OBS: Tanto o ESP32  quanto o Docker devem estar conectados a mesma rede</p>

### Montagem do ESP32

<p> A pinagem do RC522 ao ESP32 deve ser seguida de acordo com a imagem a baixo: </p> 
<p align="center"> <img width="698" height="268" alt="Pinos RFID" src="https://github.com/user-attachments/assets/6e11e82c-da87-4d66-ac0e-a1e41c9ef2a5" /> </p> 
<p> Já para o Led vermelho deve-se ultilizar o pino 13 e para o vermelho o pino 12 </p>



<p> Será necessario a ultilização de alguma IDE para sistemas embarcados, nesse caso será ultilizado o Arduino IDE 2.3.4, basta baixar a pasta Core e coloca-la dentro do diretorio /Arduino, depois basta abrir o compilador. </p> 
<p> Uma vez aberto deve-se ir em biblioteca e baixar os modulos do ESP32 e o modulo do sensor RFID especificamente RC522 </p>
<p>Após isso basta selecionar a porta COM em que o ESP32 está ligado e compilar o programa o que leva cerca de dois a três minutos</p>
<p>- OBS: Caso a IDE não reconheça a porta COM com o ESP32 deverá se instalar o driver, no caso do ESP32 Dev Modulo o driver é o CP210x </p>

### Acompanhando funcionamento:

<p>Para acompanhar a API em tempo real basta acessar Localhost:5001 que é a porta de acesso onde roda o front-end que exibe informações como status da API e do ESP32 assim como seu IP</p>
<img width="800" height="436" alt="Front Borrado png" src="https://github.com/user-attachments/assets/242ad038-06b0-4300-83d8-ac32a96e242b" />
<p>- OBS: É possivél e recomendado acompanhar a API através do terminal que está executando o container</p>
<img width="800" height="436" alt="Design sem nome" src="https://github.com/user-attachments/assets/11ab6857-db1c-41e6-96a9-c70431f68c84" />

## Vantagens:

<p>- A ultilização de docker para a programação do sistema permitiu a elaboração de um algoritmo, rapido e leve onde não é necessario a ultilização de computadores potentes;</p>
<p>- Funciona como um serviço Daemon logo seu funcioanamento é continuo permitindo assim maior segurança e automatização;</p>
<p>- Arquitetura moderna simples facilitando alterações e manutenções necessarias sem muita dor de cabeça;</p>
<p>- Baixo custo e otima eificiência operacional.</p>
