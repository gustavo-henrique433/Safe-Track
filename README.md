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
- JS + Tailwind CSS
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
<p>- Docker: Permite que a aplicação rode de maneira leve e rapida em qualquer máquina ou Hardwar;</p>
<p>- C++: Usado para a programação das instruções do ESP32 e sensores permitindo maior eficiência e rapidez graça ao baixo nível de C++;</p>
<p>- JavaScript e Tailwind: Usado para a criação de um Front-End leve com uma UI/UX intuitiva e minimalista.</p>

<p>- </p>

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
<p>Já para  a montagem da Tela LCD modelo SH1106  a pinagem a seguir deve ser: </p>
<p>SDA - Pino 21 , SCK - Pino 22, GND - Pino GND e VDD alimentar com 3.3V </p>
<p align="center"> <img width="600" height="400" alt="Tela LCD" src="https://github.com/user-attachments/assets/e6f06798-b0c9-4764-b734-c86843b118f9" /></p>

<p> Já para o Led vermelho deve-se ultilizar o pino 13 e para o vermelho o pino 12 </p>


<p> Será necessario a ultilização de alguma IDE para sistemas embarcados, nesse caso será ultilizado o Arduino IDE 2.3.4, basta baixar a pasta Core e coloca-la dentro do diretorio /Arduino, depois basta abrir o compilador. </p> 
<p> Uma vez aberto deve-se ir em biblioteca e baixar os modulos do ESP32 e o modulo do sensor RFID especificamente RC522 </p>
<p>Após isso basta selecionar a porta COM em que o ESP32 está ligado e compilar o programa o que leva cerca de dois a três minutos</p>
<p>- OBS: Caso a IDE não reconheça a porta COM com o ESP32 deverá se instalar o driver, no caso do ESP32 Dev Modulo o driver é o CP210x </p>


### Prototipação:

<p>O prototipo batizado de Hermes ainda está na fase de desenvolvimento:</p>
<p align="center"> <img width="600" height="400" alt="Prototipo" src="https://github.com/user-attachments/assets/ba434920-3f66-4806-876c-bd43c245a221" /> </p> 

<p>No futuro esperamos imprimir a Placa de Circuito Impresso (PCB) que servirá como estrutura fisica e eletrica permitindo assim a eliminação do uso da protoboard e Jumpers, conferindo melhor Design e usabilidade. O software ultilizado para o dimensionamento da PCB foi o EasyEDA </p>


<h4>Esquema elétrico: </h4>
<p align="center"> <img width="600" height="400" alt="Schematic_Safe_Track_2026-05-29" src="https://github.com/user-attachments/assets/1aedc66b-c6ec-4884-9dbe-ad870c8dec62" /> </p>

<h4>Imagem PCB:</h4>
<p align="center">  <img width="477" height="383" alt="PCB_PCB_Safe_Track_2026-05-29" src="https://github.com/user-attachments/assets/149beda5-2f6a-401e-af9f-118cdab87f19" /> </p>

### Acompanhando funcionamento:

<p>Para acompanhar a API em tempo real basta acessar Localhost:5001 que é a porta de acesso onde roda o front-end que exibe informações como status da API e do ESP32 assim como seu IP</p>
<p align="center"> <img width="1436" height="762" alt="Captura de tela 2026-05-29 105221" src="https://github.com/user-attachments/assets/8d6277d4-f767-4493-a401-868f6bb0e448" /> </p>
<p align="center">- OBS: É possível e recomendado acompanhar a API através do terminal que está executando o container</p>
<p align="center"><img width="800" height="436" alt="Design sem nome" src="https://github.com/user-attachments/assets/11ab6857-db1c-41e6-96a9-c70431f68c84" /> </p>


## Vantagens:

<p>- A ultilização de docker para a programação do sistema permitiu a elaboração de um algoritmo, rapido e leve onde não é necessario a ultilização de computadores potentes;</p>
<p>- Funciona como um serviço Daemon logo seu funcioanamento é continuo permitindo assim maior segurança e automatização;</p>
<p>- Arquitetura moderna simples facilitando alterações e manutenções necessarias sem muita dor de cabeça;</p>
<p>- Baixo custo e otima eificiência operacional.</p>

##Futuras atualizações:

<p>- Sistema de Log's: Maior controle e segurança das ações realizadas pelos usuário </p>
<p>- Autenticação de dois fatores: Ultilizar o Gmail como sisema SMTP para envio de códigos de acesso.</p>
