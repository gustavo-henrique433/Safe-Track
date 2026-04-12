// Inicializa a conexão Socket.IO
const socket = io();

// Referências dos elementos de Status
const apiStatus = document.getElementById('api-status');
const espStatus = document.getElementById('esp-status');
const espIp = document.getElementById('esp-ip');

// Referências da Notificação
const notificationContainer = document.getElementById('notification-container');
const notificationMessage = document.getElementById('notification-message');
const notificationUid = document.getElementById('notification-uid');

let timerInatividadeESP;

// --- GERENCIAMENTO DE STATUS DA API (SOCKET) ---
socket.on('connect', () => {
    apiStatus.innerText = "Online";
    apiStatus.style.color = "#28a745"; // Verde
});

socket.on('disconnect', () => {
    apiStatus.innerText = "Offline";
    apiStatus.style.color = "#dc3545"; // Vermelho
});

// --- MONITORAMENTO DO ESP32 EM TEMPO REAL ---
socket.on('rfid_update', (data) => {
    console.log("Dados recebidos do ESP32:", data);

    // 1. Atualiza o Status do Hardware e o IP
    espStatus.innerText = "Conectado";
    espStatus.style.color = "#28a745";
    espIp.innerText = `IP: ${data.ip || '0.0.0.0'}`;

    // 2. Exibe a Notificação Visual
    notificationMessage.innerText = data.message;
    notificationUid.innerText = `UID: ${data.uid}`;
    
    notificationContainer.classList.remove('notification-hidden');
    notificationContainer.classList.add('notification-visible');

    // 3. Lógica de "Check-in" (Inatividade)
    // Se o ESP32 não enviar nada em 30 segundos, assumimos que perdeu conexão
    clearTimeout(timerInatividadeESP);
    timerInatividadeESP = setTimeout(() => {
        espStatus.innerText = "Desconectado (Inativo)";
        espStatus.style.color = "#dc3545";
    }, 30000); // 30 segundos de tolerância

    // Esconde a notificação pop-up após 5 segundos
    setTimeout(() => {
        notificationContainer.classList.remove('notification-visible');
        notificationContainer.classList.add('notification-hidden');
    }, 5000);
});

// --- FUNÇÃO PARA CADASTRO MANUAL ---
async function cadastrarRFID() {
    const uid = document.getElementById('uid').value;
    const date = document.getElementById('date').value;
    const messageDiv = document.getElementById('response-message');

    if (!uid || !date) {
        messageDiv.innerText = "Preencha UID e Data.";
        messageDiv.className = 'message error';
        return;
    }

    try {
        const response = await fetch('/cadastrar_rfid', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid: uid, date: date })
        });

        const result = await response.json();

        if (response.ok) {
            messageDiv.innerText = result.message;
            messageDiv.className = 'message success';
        } else {
            messageDiv.innerText = result.message || "Erro no cadastro";
            messageDiv.className = 'message error';
        }
    } catch (error) {
        messageDiv.innerText = "Erro ao conectar com a API.";
        messageDiv.className = 'message error';
    }
}