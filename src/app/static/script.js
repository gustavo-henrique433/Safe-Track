const socket = io();
let jwtToken = null;
let timerInatividadeESP;
const baseAPI = "http://143.106.73.80:5001"; // IP da sua VM

// ==========================================
// 1. SOCKET.IO E STATUS DO HARDWARE
// ==========================================
socket.on('connect', () => console.log("Conectado ao servidor Flask via Socket.IO"));
socket.on('rfid_update', (data) => {
    const espStatus = document.getElementById('esp-status');
    const espLed = document.getElementById('esp-led');
    if (espStatus) {
        espStatus.innerText = "Conectado e Lendo";
        espStatus.className = "text-sm font-medium text-emerald-400";
        espLed.className = "w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse";
    }
    document.getElementById('esp-ip').innerText = `IP: ${data.ip || '0.0.0.0'}`;

    const notify = document.getElementById('notification-container');
    document.getElementById('notification-message').innerText = data.message;
    document.getElementById('notification-uid').innerText = `UID: ${data.uid}`;
    notify.classList.remove('translate-y-20', 'opacity-0');
    setTimeout(() => notify.classList.add('translate-y-20', 'opacity-0'), 5000);

    if (jwtToken) {
        if (data.tem_objeto) {
            mudarAba('dashboard');
            buscarObjetoSocket(data.uid);
        } else {
            mudarAba('cadastro');
            document.getElementById('tag_rfid_objeto').value = data.uid;
            document.getElementById('nome_objeto').focus();
        }
        listarTodasTags();
    }

    clearTimeout(timerInatividadeESP);
    timerInatividadeESP = setTimeout(() => {
        if (espStatus) {
            espStatus.innerText = "Inativo";
            espStatus.className = "text-sm font-medium text-red-500";
            espLed.className = "w-2 h-2 rounded-full bg-red-500 mr-2";
        }
    }, 15000);
});

// ==========================================
// 2. NAVEGAÇÃO E AUTENTICAÇÃO
// ==========================================
function mudarAba(abaId) {
    document.querySelectorAll('.secao-conteudo').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.aba-btn').forEach(btn => {
        btn.className = "w-full flex items-center px-4 py-3 text-gray-400 hover:bg-gray-700 hover:text-white rounded-lg transition-colors group aba-btn";
    });
    document.getElementById(`aba-${abaId}`).classList.remove('hidden');
    document.getElementById(`btn-${abaId}`).className = "w-full flex items-center px-4 py-3 bg-indigo-600 text-white rounded-lg transition-colors group aba-btn";
    const titulos = { 
        'dashboard': 'Visão Geral', 
        'cadastro': 'Cadastro de Patrimônio', 
        'busca': 'Inventário Completo', 
        'tags': 'Gestão de Tags (RFID)',
        'locais': 'Gestão de Locais' 
    };
    document.getElementById('titulo-pagina').innerText = titulos[abaId];
}

async function fazerLogin() {
    const email = document.getElementById('login_email').value;
    const senha = document.getElementById('login_senha').value;
    try {
        const response = await fetch(`${baseAPI}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, senha })
        });
        const result = await response.json();
        if (response.ok) {
            jwtToken = result.access_token;
            document.getElementById('tela-login').style.display = 'none';
            listarTodosObjetos();
            listarTodasTags();
            carregarLocaisNoDropdown(); // Carrega os locais logo no login
        } else {
            alert("Acesso Negado: " + result.message);
        }
    } catch (e) { alert("Falha ao conectar no servidor de Auth."); }
}

function fazerLogout() {
    jwtToken = null;
    document.getElementById('tela-login').style.display = 'flex';
    document.getElementById('login_senha').value = '';
}

// ==========================================
// 3. ROTAS DE OBJETOS (CRUD)
// ==========================================
async function cadastrarObjeto() {
    const msgDiv = document.getElementById('msg-cadastro');
    const form = new FormData();
    form.append('nome', document.getElementById('nome_objeto').value);
    form.append('descricao', document.getElementById('descricao_objeto').value);
    form.append('especificacoes', document.getElementById('especificacoes_objeto').value);
    form.append('uid_recebido', document.getElementById('tag_rfid_objeto').value);
    form.append('imagem', document.getElementById('imagem_objeto').files[0]);
    form.append('local', document.getElementById('local_objeto').value);
    try {
        const response = await fetch('/cadastrar_objeto', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${jwtToken}` },
            body: form
        });
        const res = await response.json();
        
        msgDiv.innerText = res.message || res.error;
        msgDiv.className = response.ok ? "text-sm font-bold mt-2 text-emerald-500" : "text-sm font-bold mt-2 text-red-500";
        
        if(response.ok) {
            document.getElementById('form-cadastro').reset();
            listarTodosObjetos(); 
        }
    } catch (e) { msgDiv.innerText = "Erro ao cadastrar."; }
}

async function listarTodosObjetos() {
    try {
        const response = await fetch('/vizualizar_todos_objetos', { headers: { 'Authorization': `Bearer ${jwtToken}` }});
        const data = await response.json();
        
        if (response.ok && data.objetos) {
            document.getElementById('dash-objetos').innerText = data.total_objetos;
            const grid = document.getElementById('grid-inventario');
            grid.innerHTML = '';
            
            data.objetos.forEach(obj => {
                let img = 'https://via.placeholder.com/300?text=Sem+Foto';
                if (obj.url_imagem) {
                    const parteFinal = obj.url_imagem.split('static/')[1];
                    if (parteFinal) img = `${baseAPI}/static/${parteFinal}`;
                 }

                grid.innerHTML += `
                    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden flex flex-col hover:border-indigo-500 transition-colors">
                        <img src="${img}" class="h-48 w-full object-cover border-b border-gray-700">
                        <div class="p-4 flex-1">
                            <h4 class="font-bold text-white text-lg">${obj.nome}</h4>
                            <p class="text-sm text-gray-400 mb-2 truncate">${obj.descricao}</p>
                            <span class="bg-gray-900 text-emerald-400 font-mono text-xs px-2 py-1 rounded border border-gray-700">UID: ${obj.id_rfid}</span>
                            <span class="bg-gray-900 text-gray-400 font-mono text-xs px-2 py-1 rounded border border-gray-700 ml-1">ID: ${obj.id}</span>
                        </div>
                        <div class="bg-gray-900/50 px-4 py-3 border-t border-gray-700 flex justify-between">
                            <button onclick="recadastrarUID(${obj.id}, '${obj.nome}')" class="text-indigo-400 hover:text-indigo-300 text-sm font-medium"><i class="fa-solid fa-pen mr-1"></i> Tag</button>
                            <button onclick="excluirObjeto(${obj.id}, '${obj.nome}')" class="text-red-500 hover:text-red-400 text-sm font-medium"><i class="fa-solid fa-trash mr-1"></i> Apagar</button>
                        </div>
                    </div>`;
            });
        }
    } catch (e) { console.error(e); }
}

async function excluirObjeto(idObjeto, nome) {
    if(!confirm(`Tem certeza que deseja apagar "${nome}"?`)) return;
    try {
        const response = await fetch('/excluir_objeto', {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ objeto_excluir: idObjeto })
        });
        const data = await response.json();
        alert(data.message || data.error);
        if(response.ok) listarTodosObjetos();
    } catch (e) { alert("Erro ao excluir."); }
}

async function recadastrarUID(idObjeto, nome) {
    const novaUid = prompt(`Nova Tag para "${nome}":\n(Aproxime o cartão e copie o código aqui)`);
    if(!novaUid) return;
    try {
        const response = await fetch('/recadastrar_objeto', {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_objeto: idObjeto, nova_uid: novaUid })
        });
        const data = await response.json();
        alert(data.message || data.error);
        if(response.ok) listarTodosObjetos();
    } catch (e) { alert("Erro ao alterar Tag."); }
}

// ==========================================
// 4. FUNÇÕES DO MODAL E BUSCA MANUAL
// ==========================================
function fecharModalBusca() {
    document.getElementById('modal-busca').classList.add('hidden');
}

function abrirModalBusca(objeto, nomeLocal) {
    document.getElementById('modal-busca-nome').innerText = objeto.nome;
    document.getElementById('modal-busca-desc').innerText = objeto.descricao || 'Sem descrição';
    document.getElementById('modal-busca-uid').innerText = objeto.id_rfid;
    document.getElementById('modal-busca-local').innerText = nomeLocal;
    document.getElementById('modal-busca-specs').innerText = objeto.especificacoes || 'Nenhuma especificação cadastrada.';
    
    const imgEl = document.getElementById('modal-busca-img');
    if (objeto.url_imagem) {
        const parteFinal = objeto.url_imagem.split('static/')[1];
        imgEl.src = parteFinal ? `${baseAPI}/static/${parteFinal}` : objeto.url_imagem;
    } else {
        imgEl.src = 'https://via.placeholder.com/400x200?text=Sem+Foto';
    }

    document.getElementById('modal-busca').classList.remove('hidden');
}

async function buscarObjetoManual(tipo) {
    const valor = document.getElementById('input_busca_manual').value;
    if(!valor) return alert("Digite um termo.");
    const rota = tipo === 'uid' ? `/buscar_objeto_uid/${valor}` : `/buscar_objeto_id/${valor}`;
    try {
        const response = await fetch(rota);
        const data = await response.json();
        if(response.ok) {
            let nomeLocal = "Local não especificado";
            if (data.objeto.id_lugar && window.locaisCadastrados) {
                const local = window.locaisCadastrados.find(l => l.id == data.objeto.id_lugar);
                if (local) nomeLocal = local.endereco;
            }
            abrirModalBusca(data.objeto, nomeLocal);
        } else { 
            alert(data.message);
        }
    } catch (e) { 
        alert("Erro na busca");
    }
}

async function buscarObjetoSocket(uid) {
    try {
        const response = await fetch(`/buscar_objeto_uid/${uid}`);
        const data = await response.json();
        const resDiv = document.getElementById('resultado-busca');
        
        if (response.ok) {
            const obj = data.objeto;
            const img = obj.url_imagem ? (obj.url_imagem.startsWith('http') ? obj.url_imagem : baseAPI + obj.url_imagem) : 'https://via.placeholder.com/300?text=Sem+Foto';
            resDiv.innerHTML = `
                <div class="flex items-center space-x-6 w-full animate-pulse-once">
                    <img src="${img}" class="h-40 w-40 object-cover rounded-xl border-2 border-emerald-500 shadow-md">
                    <div class="flex-1 text-left">
                        <span class="bg-emerald-500/20 text-emerald-400 text-xs font-bold px-2 py-1 rounded border border-emerald-500/30">✅ IDENTIFICADO</span>
                        <h4 class="text-3xl font-bold text-white mt-2 mb-1">${obj.nome}</h4>
                        <p class="text-gray-400 text-sm"><strong>Desc:</strong> ${obj.descricao}</p>
                        <p class="text-gray-500 text-sm"><strong>Specs:</strong> ${obj.especificacoes || '-'}</p>
                        <p class="text-emerald-500 font-mono mt-3"><i class="fa-solid fa-tag mr-2"></i>UID: ${obj.id_rfid}</p>
                    </div>
                </div>`;
        }
    } catch (e) { console.error("Erro socket fetch", e); }
}

// ==========================================
// 5. ROTAS DE TAGS RFID
// ==========================================
async function listarTodasTags() {
    try {
        const response = await fetch('/vizualizar_todos_rfid');
        const data = await response.json();
        
        if (response.ok && data.objetos) {
            document.getElementById('dash-tags').innerText = data.total_objetos;
            const tabela = document.getElementById('tabela-tags');
            tabela.innerHTML = '';
            
            data.objetos.forEach(tag => {
                
                // Mágica Visual: Cria uma etiqueta diferente se estiver livre ou em uso
                const statusHtml = tag.objeto_cadastrado === "Tag Livre" 
                    ? `<span class="bg-gray-700 text-gray-300 px-2 py-1 rounded text-xs font-bold border border-gray-600">Livre</span>`
                    : `<span class="bg-indigo-500/20 text-indigo-400 px-2 py-1 rounded text-xs font-bold border border-indigo-500/30"><i class="fa-solid fa-box mr-1"></i>${tag.objeto_cadastrado}</span>`;

                tabela.innerHTML += `
                    <tr class="hover:bg-gray-700/50 transition-colors">
                        <td class="px-6 py-4 font-mono text-emerald-400 font-medium">${tag.uid}</td>
                        <td class="px-6 py-4 text-gray-400">${tag.date || 'Desconhecida'}</td>
                        <td class="px-6 py-4">${statusHtml}</td> <td class="px-6 py-4 text-right">
                            <button onclick="excluirTag('${tag.uid}')" class="text-red-500 hover:text-red-400 font-medium text-sm transition-colors border border-red-500/30 px-3 py-1 rounded hover:bg-red-500/10">
                                <i class="fa-solid fa-trash mr-1"></i> Apagar
                            </button>
                        </td>
                    </tr>`;
            });
        }
    } catch (e) { console.error(e); }
}

async function excluirTag(uid) {
    if(!confirm(`Excluir a Tag ${uid} do sistema de reconhecimento?`)) return;
    try {
        const response = await fetch('/excluir_rfid', {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid_recebido: uid })
        });
        const data = await response.json();
        alert(data.message || data.error);
        if(response.ok) listarTodasTags();
    } catch (e) { alert("Erro ao excluir tag."); }
}

// ==========================================
// 6. ROTAS E FUNÇÕES DE LOCAIS
// ==========================================
function mudarSubAbaLocais(subAbaId) {
    document.getElementById('subaba-visualizar').classList.add('hidden');
    document.getElementById('subaba-cadastrar').classList.add('hidden');
    document.getElementById('subaba-editar').classList.add('hidden');
    const botoes = ['visualizar', 'cadastrar', 'editar'];
    botoes.forEach(btn => {
        const el = document.getElementById(`btn-sub-${btn}`);
        if (el) {
            el.className = "px-5 py-2.5 bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white border border-gray-700 rounded-lg font-bold transition-all";
        }
    });
    document.getElementById(`subaba-${subAbaId}`).classList.remove('hidden');
    const btnAtivo = document.getElementById(`btn-sub-${subAbaId}`);
    
    if (btnAtivo) {
        btnAtivo.className = "px-5 py-2.5 bg-indigo-600 text-white rounded-lg font-bold transition-all shadow-[0_0_15px_rgba(79,70,229,0.4)]";
    }
}

async function carregarLocaisNoDropdown() {
    try {
        const response = await fetch('/listar_locais');
        const data = await response.json();

        if (response.ok && data.locais) {
            const selectCadastroObjeto = document.getElementById('local_objeto');
            const selectEditarLocal = document.getElementById('id_editar_local');
            const tabelaLocais = document.getElementById('tabela-locais');
            
            const optionPadrao = '<option value="" disabled selected>Selecione um local...</option>';
            if (selectCadastroObjeto) selectCadastroObjeto.innerHTML = optionPadrao;
            if (selectEditarLocal) selectEditarLocal.innerHTML = optionPadrao;
            if (tabelaLocais) tabelaLocais.innerHTML = ''; 

            window.locaisCadastrados = data.locais;
            data.locais.forEach(local => {
                const optionTag = `<option value="${local.id}">${local.endereco}</option>`;
                
                if (selectCadastroObjeto) selectCadastroObjeto.innerHTML += optionTag;
                if (selectEditarLocal) selectEditarLocal.innerHTML += optionTag;

                if (tabelaLocais) {
                    tabelaLocais.innerHTML += `
                        <tr class="hover:bg-gray-700/50 transition-colors">
                            <td class="px-6 py-4 font-mono text-indigo-400 font-bold">${local.id}</td>
                            <td class="px-6 py-4 font-bold text-white">${local.endereco}</td>
                            <td class="px-6 py-4 text-gray-400">${local.descricao}</td>
                            <td class="px-6 py-4 text-gray-400">${local.responsavel}</td>
                        </tr>
                    `;
                }
            });
        }
    } catch (e) {
        console.error("Erro ao carregar locais:", e);
    }
}

function preencherFormularioEdicao(idLocalEscolhido) {
    if (!window.locaisCadastrados) return;
    const local = window.locaisCadastrados.find(l => l.id == idLocalEscolhido);
    if (local) {
        document.getElementById('novo_endereco_local').value = local.endereco;
        document.getElementById('nova_descricao_local').value = local.descricao;
        document.getElementById('novo_responsavel_local').value = local.responsavel;
    }
}

async function cadastrarLocal() {
    const msgDiv = document.getElementById('msg-local');
    const payload = {
        endereco: document.getElementById('endereco_local').value,
        descricao: document.getElementById('descricao_local').value,
        responsavel: document.getElementById('responsavel_local').value
    };
    try {
        const response = await fetch('/cadastrar_local', {
            method: 'POST',
            headers: { 
                'Authorization': `Bearer ${jwtToken}`,
                'Content-Type': 'application/json' 
            },
            body: JSON.stringify(payload)
        });
        
        const res = await response.json();
        msgDiv.innerText = res.message || res.error;
        msgDiv.className = response.ok ? "text-sm font-bold text-center mt-2 text-emerald-500" : "text-sm font-bold text-center mt-2 text-red-500";
        if(response.ok) {
            document.getElementById('form-local').reset();
            carregarLocaisNoDropdown(); // Atualiza a tabela imediatamente
            mudarSubAbaLocais('visualizar'); // Volta para a tabela
        }
    } catch (e) { 
        msgDiv.innerText = "Erro de conexão ao cadastrar local.";
        msgDiv.className = "text-sm font-bold text-center mt-2 text-red-500";
    }
}

async function editarLocal() {
    const msgDiv = document.getElementById('msg-editar-local');
    const payload = {
        local_alterado: document.getElementById('id_editar_local').value,
        novo_endereco: document.getElementById('novo_endereco_local').value,
        nova_descricao: document.getElementById('nova_descricao_local').value,
        novo_responsavel: document.getElementById('novo_responsavel_local').value
    };
    try {
        const response = await fetch('/editar_local', {
            method: 'PUT',
            headers: { 
                'Authorization': `Bearer ${jwtToken}`,
                'Content-Type': 'application/json' 
            },
            body: JSON.stringify(payload)
        });
        
        const res = await response.json();
        msgDiv.innerText = res.message || res.error;
        msgDiv.className = response.ok ? "text-sm font-bold text-center mt-2 text-amber-500" : "text-sm font-bold text-center mt-2 text-red-500";
        if(response.ok) {
            document.getElementById('form-editar-local').reset();
            carregarLocaisNoDropdown(); // Atualiza a tabela imediatamente
            mudarSubAbaLocais('visualizar'); // Volta para a tabela
        }
    } catch (e) { 
        msgDiv.innerText = "Erro de conexão ao editar local.";
        msgDiv.className = "text-sm font-bold text-center mt-2 text-red-500";
    }
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('-ml-64');
}

// Carrega os dropdowns assim que a página estiver pronta (mesmo antes do login, se for público)
document.addEventListener('DOMContentLoaded', () => {
    carregarLocaisNoDropdown();
});