const socket = io();
let jwtToken = null;
let timerInatividadeESP;
const baseAPI = "http://143.106.73.80:5001"; 

// ==========================================
// 1. SOCKET.IO E STATUS
// ==========================================
socket.on('connect', () => console.log("Conectado ao Flask via Socket.IO"));

socket.on('rfid_update', (data) => {
    const espStatus = document.getElementById('esp-status');
    const espLed = document.getElementById('esp-led');
    
    if (espStatus) {
        espStatus.innerText = "Conectado e Lendo";
        espStatus.className = "text-xs font-bold text-emerald-400 mr-3 hidden sm:inline tracking-wider";
        espLed.className = "w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse";
    }
    document.getElementById('esp-ip').innerText = `IP: ${data.ip || '0.0.0.0'}`;

    const notify = document.getElementById('notification-container');
    document.getElementById('notification-message').innerText = data.message;
    document.getElementById('notification-uid').innerText = `UID: ${data.uid}`;
    
    notify.classList.remove('translate-y-24', 'opacity-0');
    setTimeout(() => notify.classList.add('translate-y-24', 'opacity-0'), 5000);

    if (jwtToken) {
        if (data.status === 'objeto') {
            window.mudarAba('dashboard');
            buscarObjetoSocket(data.uid);
        } else if (data.status === 'usuario') {
            window.mudarAba('dashboard');
            buscarUsuarioSocket(data.uid);
        } else {
            window.mudarAba('cadastro');
            document.getElementById('tag_rfid_objeto').value = data.uid;
            document.getElementById('nome_objeto').focus();
        }
        listarTodasTags();
    }

    clearTimeout(timerInatividadeESP);
    timerInatividadeESP = setTimeout(() => {
        if (espStatus) {
            espStatus.innerText = "OFFLINE";
            espStatus.className = "text-xs font-bold text-red-500 mr-3 hidden sm:inline tracking-wider";
            espLed.className = "w-2 h-2 rounded-full bg-red-500 mr-2";
        }
    }, 15000);
});

// ==========================================
// 2. AUTENTICAÇÃO
// ==========================================
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
            carregarLocaisNoDropdown();
            listarTodosUsuarios();
        } else {
            alert("Acesso Negado: " + result.message);
        }
    } catch (e) { 
        alert("Falha ao conectar.");
    }
}

function fazerLogout() {
    jwtToken = null;
    document.getElementById('tela-login').style.display = 'flex';
    document.getElementById('login_senha').value = '';
}

// ==========================================
// 3. ROTAS DE OBJETOS
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
            
            window.objetosCadastrados = data.objetos; 
            
            data.objetos.forEach(obj => {
                let img = 'https://via.placeholder.com/300?text=Sem+Foto';
                if (obj.url_imagem) {
                    const parteFinal = obj.url_imagem.split('static/')[1];
                    if (parteFinal) img = `${baseAPI}/static/${parteFinal}`;
                 }

                grid.innerHTML += `
                    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden flex flex-col hover:border-indigo-500 transition-colors shadow-lg">
                        <div onclick="abrirDetalhesCard(${obj.id})" class="cursor-pointer group flex-1">
                            <div class="overflow-hidden">
                                <img src="${img}" class="h-48 w-full object-cover border-b border-gray-700 group-hover:scale-105 transition-transform duration-300">
                            </div>
                            <div class="p-4">
                                <h4 class="font-bold text-white text-lg group-hover:text-indigo-400 transition-colors">${obj.nome}</h4>
                                <p class="text-sm text-gray-400 mb-3 truncate">${obj.descricao}</p>
                                <div class="flex gap-2">
                                    <span class="bg-gray-900 text-emerald-400 font-mono text-xs px-2 py-1 rounded border border-gray-700">UID: ${obj.id_rfid}</span>
                                    <span class="bg-gray-900 text-gray-400 font-mono text-xs px-2 py-1 rounded border border-gray-700">ID: ${obj.id}</span>
                                </div>
                            </div>
                        </div>
                        <div class="bg-gray-900/50 px-4 py-3 border-t border-gray-700 flex justify-between">
                            <button onclick="recadastrarUID(${obj.id}, '${obj.nome}')" class="text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10 px-2 py-1 rounded text-sm font-medium transition-colors"><i class="fa-solid fa-pen mr-1"></i> Tag</button>
                            <button onclick="excluirObjeto(${obj.id}, '${obj.nome}')" class="text-red-500 hover:text-red-400 hover:bg-red-500/10 px-2 py-1 rounded text-sm font-medium transition-colors"><i class="fa-solid fa-trash mr-1"></i> Apagar</button>
                        </div>
                    </div>`;
            });
        }
    } catch (e) { console.error(e); }
}

async function excluirObjeto(idObjeto, nome) {
    if(!confirm(`Apagar "${nome}"?`)) return;
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
    const novaUid = prompt(`Nova Tag para "${nome}":\n(Aproxime o cartão e copie o código)`);
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
    } catch (e) { alert("Erro ao alterar."); }
}

// ==========================================
// 4. FUNÇÕES DE BUSCA E DETALHES
// ==========================================
function fecharModalBusca() { document.getElementById('modal-busca').classList.add('hidden'); }

function abrirModalBusca(objeto, nomeLocal) {
    document.getElementById('modal-busca-nome').innerText = objeto.nome;
    document.getElementById('modal-busca-desc').innerText = objeto.descricao || 'Sem descrição';
    document.getElementById('modal-busca-uid').innerText = objeto.id_rfid;
    document.getElementById('modal-busca-local').innerText = nomeLocal;
    document.getElementById('modal-busca-specs').innerText = objeto.especificacoes || '-';
    
    const imgEl = document.getElementById('modal-busca-img');
    if (objeto.url_imagem) {
        const parteFinal = objeto.url_imagem.split('static/')[1];
        imgEl.src = parteFinal ? `${baseAPI}/static/${parteFinal}` : objeto.url_imagem;
    } else {
        imgEl.src = 'https://via.placeholder.com/400x200?text=Sem+Foto';
    }
    document.getElementById('modal-busca').classList.remove('hidden');
}

function abrirDetalhesCard(id) {
    if (!window.objetosCadastrados) return;
    const obj = window.objetosCadastrados.find(o => o.id === id);
    if (obj) {
        let nomeLocal = "Não especificado";
        if (obj.id_lugar && window.locaisCadastrados) {
            const local = window.locaisCadastrados.find(l => l.id == obj.id_lugar);
            if (local) nomeLocal = local.endereco;
        }
        abrirModalBusca(obj, nomeLocal);
    }
}

async function buscarObjetoManual(tipo) {
    const valor = document.getElementById('input_busca_manual').value.trim();
    if(!valor) return alert("Digite um termo para buscar.");
    
    const valorSeguro = encodeURIComponent(valor);
    let rota = '';
    if (tipo === 'uid') rota = `/buscar_objeto_uid/${valorSeguro}`;
    else if (tipo === 'id') rota = `/buscar_objeto_id/${valorSeguro}`;
    else if (tipo === 'nome') rota = `/buscar_objeto_nome/${valorSeguro}`;

    try {
        const response = await fetch(rota);
        const data = await response.json();
        
        if(response.ok) {
            if (tipo === 'nome' && data.objetos) {
                const grid = document.getElementById('grid-inventario');
                grid.innerHTML = ''; 
                window.objetosCadastrados = data.objetos; 
                data.objetos.forEach(obj => {
                    let img = 'https://via.placeholder.com/300?text=Sem+Foto';
                    if (obj.url_imagem) {
                        const parteFinal = obj.url_imagem.split('static/')[1];
                        if (parteFinal) img = `${baseAPI}/static/${parteFinal}`;
                    }
                    grid.innerHTML += `
                        <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden flex flex-col hover:border-indigo-500 transition-colors shadow-lg">
                            <div onclick="abrirDetalhesCard(${obj.id})" class="cursor-pointer group flex-1">
                                <div class="overflow-hidden">
                                    <img src="${img}" class="h-48 w-full object-cover border-b border-gray-700 group-hover:scale-105 transition-transform">
                                </div>
                                <div class="p-4">
                                    <h4 class="font-bold text-white text-lg group-hover:text-indigo-400 transition-colors">${obj.nome}</h4>
                                    <p class="text-sm text-gray-400 mb-3 truncate">${obj.descricao}</p>
                                </div>
                            </div>
                        </div>`;
                });
            } else {
                let nomeLocal = "Não especificado";
                if (data.objeto.id_lugar && window.locaisCadastrados) {
                    const local = window.locaisCadastrados.find(l => l.id == data.objeto.id_lugar);
                    if (local) nomeLocal = local.endereco;
                }
                abrirModalBusca(data.objeto, nomeLocal);
            }
        } else { alert(data.message); }
    } catch (e) { alert("Erro ao buscar."); }
}

async function buscarObjetoSocket(uid) {
    try {
        const response = await fetch(`/buscar_objeto_uid/${uid}`);
        const data = await response.json();
        const resDiv = document.getElementById('resultado-busca');
        if (response.ok) {
            const obj = data.objeto;
            const img = obj.url_imagem ? (obj.url_imagem.startsWith('http') ? obj.url_imagem : baseAPI + obj.url_imagem) : 'https://via.placeholder.com/300';
            resDiv.innerHTML = `
                <div class="flex items-center space-x-6 w-full">
                    <img src="${img}" class="h-40 w-40 object-cover rounded-xl border-2 border-emerald-500">
                    <div class="flex-1 text-left">
                        <span class="bg-emerald-500/20 text-emerald-400 text-xs font-bold px-2 py-1 rounded border border-emerald-500/30">IDENTIFICADO</span>
                        <h4 class="text-3xl font-bold text-white mt-2 mb-1">${obj.nome}</h4>
                        <p class="text-emerald-500 font-mono mt-3"><i class="fa-solid fa-tag mr-2"></i>UID: ${obj.id_rfid}</p>
                    </div>
                </div>`;
        }
    } catch (e) {}
}

async function buscarUsuarioSocket(uid) {
    try {
        const response = await fetch(`/buscar_usuario_uid/${uid}`);
        const data = await response.json();
        const resDiv = document.getElementById('resultado-busca');
        if (response.ok) {
            const user = data.usuario;
            resDiv.innerHTML = `
                <div class="flex items-center space-x-6 w-full">
                    <div class="h-40 w-40 bg-blue-900/50 rounded-xl border-2 border-blue-500 flex items-center justify-center">
                        <i class="fa-solid fa-user text-6xl text-blue-400"></i>
                    </div>
                    <div class="flex-1 text-left">
                        <span class="bg-blue-500/20 text-blue-400 text-xs font-bold px-2 py-1 rounded border border-blue-500/30">USUÁRIO RECONHECIDO</span>
                        <h4 class="text-3xl font-bold text-white mt-2 mb-1">${user.nome}</h4>
                        <p class="text-blue-500 font-mono mt-3"><i class="fa-solid fa-id-badge mr-2"></i>Credencial: ${user.credencial_rfid}</p>
                    </div>
                </div>`;
        }
    } catch (e) {}
}

// ==========================================
// 5. TAGS RFID
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
                const statusHtml = tag.objeto_cadastrado === "Tag Livre" 
                    ? `<span class="bg-gray-700 text-emerald-300 px-2 py-1 rounded text-xs font-bold">Livre</span>`
                    : `<span class="bg-indigo-500/20 text-indigo-400 px-2 py-1 rounded text-xs font-bold"><i class="fa-solid fa-box mr-1"></i>${tag.objeto_cadastrado}</span>`;
                tabela.innerHTML += `
                    <tr class="hover:bg-gray-700/50">
                        <td class="px-6 py-4 font-mono text-emerald-400">${tag.uid}</td>
                        <td class="px-6 py-4 text-gray-400">${tag.date || '-'}</td>
                        <td class="px-6 py-4">${statusHtml}</td> 
                        <td class="px-6 py-4 text-right">
                            <button onclick="excluirTag('${tag.uid}')" class="text-red-500 hover:text-red-400"><i class="fa-solid fa-trash"></i> Apagar</button>
                        </td>
                    </tr>`;
            });
        }
    } catch (e) {}
}

async function excluirTag(uid) {
    if(!confirm(`Excluir a Tag ${uid}?`)) return;
    try {
        const response = await fetch('/excluir_rfid', {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid_recebido: uid })
        });
        const data = await response.json();
        alert(data.message || data.error);
        if(response.ok) listarTodasTags();
    } catch (e) {}
}

// ==========================================
// 6. LOCAIS E MODAIS DE LOCAIS
// ==========================================
function abrirModalLocal(tipo) {
    if (tipo === 'novo') {
        const form = document.getElementById('form-local');
        if (form) form.reset(); 
        document.getElementById('msg-local').innerText = '';
        document.getElementById('modal-novo-local').classList.remove('hidden');
    }
}

function fecharModalLocal(tipo) {
    if (tipo === 'novo') document.getElementById('modal-novo-local').classList.add('hidden');
    if (tipo === 'editar') document.getElementById('modal-editar-local').classList.add('hidden');
}

function abrirModalEditarLocal(idLocal) {
    if (!window.locaisCadastrados) return;
    const local = window.locaisCadastrados.find(l => l.id == idLocal);
    if (local) {
        document.getElementById('id_editar_local').value = local.id;
        document.getElementById('novo_endereco_local').value = local.endereco;
        document.getElementById('nova_descricao_local').value = local.descricao;
        document.getElementById('novo_responsavel_local').value = local.responsavel;
        document.getElementById('msg-editar-local').innerText = '';
        document.getElementById('modal-editar-local').classList.remove('hidden');
    }
}

async function carregarLocaisNoDropdown() {
    try {
        const response = await fetch('/listar_locais');
        const data = await response.json();

        if (response.ok && data.locais) {
            
            // ATUALIZA O NUMERO NO DASHBOARD
            const elDash = document.getElementById('dash-locais');
            if (elDash) elDash.innerText = data.locais.length;

            const selectCadastro = document.getElementById('local_objeto');
            const tabelaLocais = document.getElementById('tabela-locais');
            if (selectCadastro) selectCadastro.innerHTML = '<option value="" disabled selected>Selecione...</option>';
            if (tabelaLocais) tabelaLocais.innerHTML = ''; 

            window.locaisCadastrados = data.locais;
            data.locais.forEach(local => {
                if (selectCadastro) selectCadastro.innerHTML += `<option value="${local.id}">${local.endereco}</option>`;
                if (tabelaLocais) {
                    tabelaLocais.innerHTML += `
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-6 py-4 font-mono text-indigo-400 font-bold">${local.id}</td>
                            <td class="px-6 py-4 font-bold text-white">${local.endereco}</td>
                            <td class="px-6 py-4 text-gray-400">${local.descricao}</td>
                            <td class="px-6 py-4 text-gray-400">${local.responsavel}</td>
                            <td class="px-6 py-4 text-right">
                                <button onclick="abrirModalEditarLocal(${local.id})" class="text-amber-500 hover:bg-amber-500/10 px-3 py-1 rounded border border-amber-500/30"><i class="fa-solid fa-pen mr-1"></i> Editar</button>
                            </td>
                        </tr>`;
                }
            });
        }
    } catch (e) {}
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
            headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        msgDiv.innerText = res.message || res.error;
        msgDiv.className = response.ok ? "text-sm font-bold text-center mt-2 text-emerald-500" : "text-sm font-bold text-center mt-2 text-red-500";
        if(response.ok) {
            carregarLocaisNoDropdown();
            setTimeout(() => fecharModalLocal('novo'), 1000); 
        }
    } catch (e) { msgDiv.innerText = "Erro ao cadastrar."; }
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
            headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        msgDiv.innerText = res.message || res.error;
        msgDiv.className = response.ok ? "text-sm font-bold text-center mt-2 text-emerald-500" : "text-sm font-bold text-center mt-2 text-red-500";
        if(response.ok) {
            carregarLocaisNoDropdown();
            setTimeout(() => fecharModalLocal('editar'), 1000); 
        }
    } catch (e) { msgDiv.innerText = "Erro ao editar."; }
}

// ==========================================
// 7. USUÁRIOS
// ==========================================
async function listarTodosUsuarios() {
    try {
        const response = await fetch('/visualizar_todos_usuarios', { headers: { 'Authorization': `Bearer ${jwtToken}` } });
        const data = await response.json();
        if (response.ok && data.usuarios) {
            
            // ATUALIZA O NUMERO NO DASHBOARD
            const elDash = document.getElementById('dash-usuarios');
            if (elDash) elDash.innerText = data.usuarios.length;

            const tabelaUsuarios = document.getElementById('tabela-usuarios');
            tabelaUsuarios.innerHTML = ''; 
            data.usuarios.forEach(user => {
                tabelaUsuarios.innerHTML += `
                    <tr class="hover:bg-gray-700/50">
                        <td class="px-6 py-4 font-mono text-indigo-400">${user.id}</td>
                        <td class="px-6 py-4 font-bold text-white">${user.nome}</td>
                        <td class="px-6 py-4 text-gray-400">${user.email}</td>
                        <td class="px-6 py-4 font-mono text-emerald-400">${user.credencial_rfid || '-'}</td>
                    </tr>`;
            });
        }
    } catch (e) {}
}

async function cadastrarUsuario() {
    const msgDiv = document.getElementById('msg-cadastrar-usuario');
    const payload = { nome: document.getElementById('novo_nome_usuario').value, email: document.getElementById('novo_email_usuario').value, senha: document.getElementById('nova_senha_usuario').value };
    try {
        const response = await fetch('/registrar_usuario', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const res = await response.json();
        msgDiv.innerText = res.message || res.error;
        msgDiv.className = response.ok ? "text-emerald-500" : "text-red-500";
        if(response.ok) { document.getElementById('form-cadastrar-usuario').reset(); listarTodosUsuarios(); }
    } catch (e) {}
}

async function atribuirTagUsuario() {
    const msgDiv = document.getElementById('msg-atribuir-usuario');
    const id_usuario = document.getElementById('id_usuario_atribuir').value;
    const uid_usuario = document.getElementById('uid_usuario_atribuir').value;
    try {
        const response = await fetch('/atribuir_rfid_usuario', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_usuario: parseInt(id_usuario), uid_usuario: uid_usuario })
        });
        const res = await response.json();
        msgDiv.innerText = res.message || res.error;
        msgDiv.className = response.ok ? "text-emerald-500" : "text-red-500";
        if(response.ok) { document.getElementById('form-atribuir-tag-usuario').reset(); listarTodasTags(); listarTodosUsuarios(); }
    } catch (e) {}
}

// ==========================================
// 8. EFEITO DE INICIALIZAÇÃO (LOTTIE ANIMATION)
// ==========================================
// ==========================================
// 8. EFEITO DE INICIALIZAÇÃO (LOTTIE ANIMATION)
// ==========================================
// ==========================================
// 8. EFEITO DE INICIALIZAÇÃO (SEQUÊNCIA LOTTIE -> LOGO)
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    carregarLocaisNoDropdown();

    const splashScreen = document.getElementById('splash-screen');
    const lottieContainer = document.getElementById('lottie-container');
    const splashLogo = document.getElementById('splash-logo');
    const splashText = document.getElementById('splash-text');

    // 1. Inicia a animação de água
    const animation = lottie.loadAnimation({
        container: lottieContainer, 
        renderer: 'svg',
        loop: false, 
        autoplay: true, 
        path: '/static/Computer_Animation.json' 
    });

    // 2. Quando a água termina, começa a transição pro Logo
    animation.addEventListener('complete', () => {
        // Esconde a água e o texto de "Iniciando"
        lottieContainer.classList.add('opacity-0');
        splashText.classList.add('opacity-0');

        setTimeout(() => {
            lottieContainer.style.display = 'none';
            
            // Revela o Logo com efeito de fade e zoom
            splashLogo.classList.remove('opacity-0', 'scale-75');
            splashLogo.classList.add('opacity-100', 'scale-100');

            // 3. Após 2 segundos exibindo o logo, remove tudo e vai pro Login
            setTimeout(() => {
                splashScreen.style.opacity = '0';
                setTimeout(() => {
                    splashScreen.style.display = 'none';
                }, 1000);
            }, 2000); 

        }, 500); // Pequena pausa após o splash sumir
    });

    // Segurança: se o arquivo JSON falhar, remove o splash após 4 segundos
    setTimeout(() => {
        if (splashScreen.style.display !== 'none') {
            splashScreen.style.opacity = '0';
            setTimeout(() => { splashScreen.style.display = 'none'; }, 1000);
        }
    }, 5000);
});