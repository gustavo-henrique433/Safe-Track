/* DOM simulado: HTML renderizado e respostas reais exportadas pelo Pytest.
 * Node e jsdom são ferramentas opcionais de teste; não são dependências da API.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');

const project = path.resolve(__dirname, '../../../..');
const artifacts = process.env.SAFE_TRACK_FRONTEND_ARTIFACTS;
assert.ok(artifacts, 'Defina SAFE_TRACK_FRONTEND_ARTIFACTS com as amostras exportadas pelo Pytest.');
const html = readFileSync(path.join(artifacts, 'index-renderizado.html'), 'utf8');
const samples = JSON.parse(readFileSync(path.join(artifacts, 'frontend-api.json'), 'utf8'));
const originalScript = readFileSync(path.join(project, 'src/app/static/script.js'), 'utf8');
const adminScript = readFileSync(path.join(project, 'src/app/static/admin.js'), 'utf8');
const permissionsScript = readFileSync(path.join(project, 'src/app/static/permissions.js'), 'utf8');
const navigation = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map((match) => match[1])
    .find((source) => source.includes('window.mudarAba ='));
assert.ok(navigation);

const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const copy = (data) => JSON.parse(JSON.stringify(data));

async function flush() { for (let i = 0; i < 12; i++) await new Promise(setImmediate); }

async function setup(t, { role = 'roots', intercept = null, changeSamples = null } = {}) {
    const data = copy(samples);
    if (changeSamples) changeSamples(data);
    const virtualConsole = new VirtualConsole();
    const errors = [];
    virtualConsole.on('jsdomError', (error) => errors.push(error.message));
    const dom = new JSDOM(html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ''), {
        url: 'http://localhost:5001/', runScripts: 'dangerously', virtualConsole,
    });
    const window = dom.window;
    const calls = [], alerts = [], downloads = [], confirmations = [];
    let confirmed = true;
    window.io = () => ({ on() {} });
    window.lottie = { loadAnimation: () => ({ addEventListener() {} }) };
    window.scrollTo = () => {};
    window.alert = (message) => alerts.push(message);
    window.confirm = (message) => { confirmations.push(message); return confirmed; };
    window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
    window.HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new window.Event('close')); };
    window.URL.createObjectURL = () => 'blob:teste';
    window.URL.revokeObjectURL = () => {};
    window.HTMLAnchorElement.prototype.click = function () { downloads.push({ filename: this.download, href: this.href }); };
    window.fetch = async (address, options = {}) => {
        const parsed = new URL(address, 'http://localhost:5001');
        const call = { address, path: parsed.pathname, params: parsed.searchParams,
            method: options.method || 'GET', headers: options.headers || {},
            body: options.body ? JSON.parse(options.body) : null, signal: options.signal };
        calls.push(call);
        if (intercept) {
            const response = await intercept(call, data);
            if (response !== undefined) return response;
        }
        if (call.path === '/login') return json({ access_token: `${role}-token-ficticio`, user_type: role });
        if (call.path === '/listar_locais') return json(data.locals);
        if (call.path === '/vizualizar_todos_rfid') return json(data.tags);
        if (call.path === '/visitantes' && call.method === 'GET') {
            const visitors = data.visitors.visitantes.filter((visitor) => !call.params.get('status') || visitor.status === call.params.get('status'));
            return json({ ...data.visitors, visitantes: visitors, total: visitors.length,
                pagina: Number(call.params.get('pagina') || 1), limite: Number(call.params.get('limite') || 25) });
        }
        if (/^\/visitantes\/\d+$/.test(call.path) && call.method === 'GET') {
            return json({ visitante: data.visitors.visitantes.find((visitor) => visitor.id === Number(call.path.split('/')[2])) });
        }
        if (/^\/visitantes\/\d+\/revogar$/.test(call.path)) {
            const visitor = data.visitors.visitantes.find((item) => item.id === Number(call.path.split('/')[2]));
            visitor.status = 'revogado'; return json({ visitante: visitor });
        }
        if (call.path.startsWith('/visitantes') && ['POST', 'PUT'].includes(call.method)) return json(data.visitor, call.method === 'POST' ? 201 : 200);
        if (call.path === '/api/dashboards/resumo') return json(data.summary);
        if (call.path === '/api/relatorios/acessos') return json({ ...data.accesses, pagina: Number(call.params.get('pagina') || 1) });
        if (call.path === '/api/relatorios/atividades') return json({ ...data.activities, pagina: Number(call.params.get('pagina') || 1) });
        if (call.path === '/api/relatorios/acessos.csv') return new Response(data.csv, { headers: { 'Content-Type': 'text/csv' } });
        // Leituras antigas disparadas pelo login original continuam simuladas.
        return json({ objetos: [], usuarios: [] });
    };
    window.eval(`${originalScript}\n${permissionsScript}`);
    window.eval(navigation);
    window.eval(adminScript);
    t.after(() => { dom.window.close(); assert.deepEqual(errors, [], 'Erro de execução no DOM'); });
    const id = (name) => window.document.getElementById(name);
    const field = (form, name) => id(form).elements.namedItem(name);
    const submit = async (name) => { id(name).dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })); await flush(); };
    id('login_email').value = 'root@example.test'; id('login_senha').value = 'Senha-ficticia-123!';
    await window.fazerLogin(); await flush();
    return { window, data, calls, alerts, downloads, confirmations, id, field, submit,
        confirm: (answer) => { confirmed = answer; },
        open: async (name) => { window.mudarAba(name); await flush(); },
        click: async (element) => { element.click(); await flush(); } };
}

async function newVisitor(h) {
    await h.open('visitantes'); await h.click(h.id('st-visitante-novo'));
    const fields = { nome: 'Nova visitante', email: 'nova@example.test', senha: 'Senha-ficticia-123!',
        credencial_rfid: 'b2c3d4e5', inicio: '2026-11-10T10:30:00', expiracao: '2026-11-10T12:30:00' };
    for (const [name, value] of Object.entries(fields)) h.field('st-visitante-formulario', name).value = value;
    h.id('st-visitante-locais').querySelector('input').checked = true;
}

function rowButton(h, label, index = 0) {
    return [...h.id('st-visitantes-corpo').querySelectorAll('button')].filter((button) => button.textContent === label)[index];
}

test('login original informa o perfil e libera somente os dois novos cartões Root', async (t) => {
    const h = await setup(t);
    assert.equal(h.id('tela-login').style.display, 'none');
    assert.equal(h.window.document.querySelectorAll('[data-safe-track-admin]:not([hidden])').length, 2);
    const login = h.calls.find((call) => call.path === '/login');
    assert.deepEqual(login.body, { email: 'root@example.test', senha: 'Senha-ficticia-123!' });
    assert.ok(h.calls.some((call) => call.path === '/listar_locais'));
    await h.click(h.window.document.querySelector('[data-safe-track-admin]'));
    assert.equal(h.id('aba-visitantes').classList.contains('hidden'), false);
    assert.ok(h.calls.some((call) => call.path === '/visitantes'));
});

for (const role of ['users', 'visitante']) test(`${role} não vê os cartões nem abre as novas abas`, async (t) => {
    const h = await setup(t, { role });
    await h.open('visitantes'); await h.open('relatorios');
    assert.equal(h.window.document.querySelectorAll('[data-safe-track-admin]:not([hidden])').length, 0);
    assert.ok(h.id('aba-visitantes').classList.contains('hidden'));
    assert.ok(h.id('aba-relatorios').classList.contains('hidden'));
    assert.equal(h.calls.filter((call) => call.path.startsWith('/visitantes') || call.path.startsWith('/api/')).length, 0);
});

test('listagem mostra validade, RFID, locais e situações recebidas sem inventar dados', async (t) => {
    const h = await setup(t); await h.open('visitantes');
    assert.equal(h.id('st-visitantes-corpo').rows.length, 3);
    for (const visitor of h.data.visitors.visitantes) assert.ok(h.id('st-visitantes-corpo').textContent.includes(visitor.nome));
    assert.match(h.id('st-visitantes-corpo').textContent, /Ativo.*Expirado.*Revogado/s);
    assert.match(h.id('st-visitantes-corpo').textContent, /Laboratório de teste/);
    assert.match(h.id('st-visitantes-fuso').textContent, /America\/Sao_Paulo/);
    assert.ok(rowButton(h, 'Revogar', 2).disabled);
    const call = h.calls.find((item) => item.path === '/visitantes');
    assert.equal(call.headers.Authorization, 'Bearer roots-token-ficticio');
    assert.equal(call.address.startsWith('/'), true);
});

test('filtro de situação e tamanho da página usam somente o contrato existente', async (t) => {
    const h = await setup(t); await h.open('visitantes');
    h.field('st-visitantes-filtros', 'status').value = 'expirado';
    h.field('st-visitantes-filtros', 'limite').value = '50';
    await h.submit('st-visitantes-filtros');
    const call = h.calls.filter((item) => item.path === '/visitantes').at(-1);
    assert.equal(call.params.get('status'), 'expirado'); assert.equal(call.params.get('limite'), '50');
    assert.equal(call.params.get('pagina'), '1');
    assert.equal(h.id('st-visitantes-corpo').rows.length, 1);
    assert.match(h.id('st-visitantes-corpo').textContent, /Visitante expirado/);
});

test('cadastro converte horário local em ISO UTC e envia somente os sete campos permitidos', async (t) => {
    const h = await setup(t); await newVisitor(h); await h.submit('st-visitante-formulario');
    const call = h.calls.find((item) => item.path === '/visitantes' && item.method === 'POST');
    assert.deepEqual(Object.keys(call.body).sort(), ['nome', 'email', 'senha', 'credencial_rfid', 'inicio', 'expiracao', 'locais'].sort());
    assert.equal(call.body.inicio, '2026-11-10T13:30:00.000Z');
    assert.equal(call.body.expiracao, '2026-11-10T15:30:00.000Z');
    assert.deepEqual(call.body.locais, [h.data.locals.locais[0].id]);
    assert.equal(call.body.credencial_rfid, 'b2c3d4e5');
    assert.equal(h.id('st-visitante-dialogo').open, false);
    assert.equal(h.field('st-visitante-formulario', 'senha').value, '');
    assert.match(h.id('st-visitantes-mensagem').textContent, /cadastrado com sucesso/);
});

for (const scenario of ['periodo', 'locais']) test(`cadastro inválido por ${scenario} não dispara gravação`, async (t) => {
    const h = await setup(t); await newVisitor(h);
    if (scenario === 'periodo') h.field('st-visitante-formulario', 'expiracao').value = h.field('st-visitante-formulario', 'inicio').value;
    else h.id('st-visitante-locais').querySelector('input').checked = false;
    await h.submit('st-visitante-formulario');
    assert.equal(h.calls.filter((call) => call.path === '/visitantes' && call.method === 'POST').length, 0);
    assert.equal(h.id('st-visitante-formulario-mensagem').dataset.state, 'error');
    assert.equal(h.id('st-visitante-dialogo').open, true);
});

test('edição preserva UID numérica inalterada, identificação e precisão original do período', async (t) => {
    const h = await setup(t, { changeSamples(data) { data.visitors.visitantes[0].credencial_rfid = 1234; } });
    await h.open('visitantes'); await h.click(rowButton(h, 'Permissões'));
    assert.equal(h.field('st-visitante-formulario', 'nome').disabled, true);
    assert.equal(h.field('st-visitante-formulario', 'senha').disabled, true);
    const previousEnd = h.field('st-visitante-formulario', 'expiracao').value;
    h.field('st-visitante-formulario', 'expiracao').value = previousEnd.replace(/T\d{2}:/, 'T23:');
    if (h.field('st-visitante-formulario', 'expiracao').value === previousEnd) h.field('st-visitante-formulario', 'expiracao').value = '2026-12-31T23:59:00';
    await h.submit('st-visitante-formulario');
    const call = h.calls.find((item) => item.method === 'PUT');
    assert.ok(call); assert.deepEqual(Object.keys(call.body), ['expiracao']);
    assert.equal(call.path, `/visitantes/${h.data.visitors.visitantes[0].id}`);
});

test('edição sem alterações não envia PUT ou campos não permitidos', async (t) => {
    const h = await setup(t); await h.open('visitantes'); await h.click(rowButton(h, 'Permissões'));
    await h.submit('st-visitante-formulario');
    assert.equal(h.calls.filter((call) => call.method === 'PUT').length, 0);
    assert.match(h.id('st-visitante-formulario-mensagem').textContent, /Nenhuma alteração/);
});

test('revogação confirmada usa a rota existente e conserva o visitante no histórico', async (t) => {
    const h = await setup(t); await h.open('visitantes');
    h.confirm(false); await h.click(rowButton(h, 'Revogar'));
    assert.equal(h.calls.filter((call) => call.path.endsWith('/revogar')).length, 0);
    h.confirm(true); await h.click(rowButton(h, 'Revogar'));
    const call = h.calls.find((item) => item.path.endsWith('/revogar'));
    assert.equal(call.method, 'POST'); assert.equal(call.body, null);
    assert.equal(h.id('st-visitantes-corpo').rows.length, 3);
    assert.ok(rowButton(h, 'Revogar').disabled);
    assert.match(h.id('st-visitantes-mensagem').textContent, /histórico foi mantido/);
});

test('histórico do visitante abre relatórios com seu identificador e sem alterar a rota original', async (t) => {
    const h = await setup(t); await h.open('visitantes'); await h.click(rowButton(h, 'Histórico'));
    assert.equal(h.id('aba-relatorios').classList.contains('hidden'), false);
    const id = String(h.data.visitors.visitantes[0].id);
    assert.equal(h.field('st-acessos-filtros', 'visitante').value, id);
    assert.ok(h.calls.some((call) => call.path === '/api/relatorios/acessos' && call.params.get('visitante') === id));
    assert.ok(h.calls.some((call) => call.path === '/api/dashboards/resumo' && call.params.get('visitante') === id));
    assert.equal(h.id('st-relatorio-tab-acessos').getAttribute('aria-selected'), 'true');
    assert.equal(h.id('st-relatorio-painel-acessos').hidden, false);
    assert.equal(h.id('st-relatorio-ferramentas').hidden, false);
});

test('resumo usa contagens reais, série SVG e ranking; indicadores sem fonte continuam indisponíveis', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    assert.equal(h.id('st-metricas-acessos').querySelector('dd').textContent, '2');
    assert.equal(h.id('st-grafico-diario').querySelectorAll('svg polyline').length, 3);
    assert.equal(h.id('st-diaria-corpo').rows.length, h.data.summary.evolucao_diaria.dias.length);
    assert.equal(h.id('st-ranking').children.length, 1);
    assert.match(h.id('st-indisponiveis').textContent, /Requisições à API: indisponível/);
    assert.match(h.id('st-indisponiveis').textContent, /Retiradas e movimentações de objetos: indisponível/);
    assert.match(h.id('st-acessos-corpo').textContent, /Não identificado no evento/);
});

test('período, local, visitante e resultado são aplicados de forma igual aos dois endpoints', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    const values = { inicio: '2026-11-01', fim: '2026-11-17', local: '1', visitante: '4', resultado: 'Negado' };
    for (const [name, value] of Object.entries(values)) h.field('st-acessos-filtros', name).value = value;
    await h.submit('st-acessos-filtros');
    for (const route of ['/api/dashboards/resumo', '/api/relatorios/acessos']) {
        const call = h.calls.filter((item) => item.path === route).at(-1);
        for (const [name, value] of Object.entries(values)) assert.equal(call.params.get(name), value);
    }
    assert.match(h.id('st-acessos-recorte').textContent, /Negado/);
});

test('CSV mantém os filtros aplicados mesmo com formulário alterado sem aplicar', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    h.field('st-acessos-filtros', 'resultado').value = 'Negado'; await h.submit('st-acessos-filtros');
    h.field('st-acessos-filtros', 'resultado').value = 'Liberado';
    await h.click(h.id('st-acessos-csv'));
    const call = h.calls.find((item) => item.path.endsWith('.csv'));
    assert.equal(call.params.get('resultado'), 'Negado');
    assert.equal(call.params.has('pagina'), false); assert.equal(call.params.has('limite'), false);
    assert.deepEqual(h.downloads, [{ filename: 'safe-track-acessos.csv', href: 'blob:teste' }]);
});

test('erro de limite do CSV fica visível e permite nova tentativa sem gerar arquivo', async (t) => {
    const h = await setup(t, { intercept(call) { if (call.path.endsWith('.csv')) return json({ message: 'Restrinja os filtros do relatório.' }, 400); } });
    await h.open('relatorios'); await h.click(h.id('st-acessos-csv'));
    assert.match(h.id('st-acessos-mensagem').textContent, /Restrinja/);
    assert.equal(h.id('st-acessos-csv').disabled, false); assert.equal(h.downloads.length, 0);
});

test('paginação de acessos mantém filtros e não repete a consulta do resumo', async (t) => {
    const h = await setup(t, { changeSamples(data) { data.accesses.total = 26; } });
    await h.open('relatorios');
    const before = h.calls.filter((call) => call.path === '/api/dashboards/resumo').length;
    await h.click(h.id('st-acessos-proxima'));
    assert.equal(h.calls.filter((call) => call.path === '/api/relatorios/acessos').at(-1).params.get('pagina'), '2');
    assert.equal(h.calls.filter((call) => call.path === '/api/dashboards/resumo').length, before);
    assert.equal(h.id('st-acessos-proxima').disabled, true);
    assert.equal(h.id('st-acessos-anterior').disabled, false);
});

test('histórico vazio apresenta zeros reais e estados vazios, sem criar série ou ranking', async (t) => {
    const h = await setup(t, { changeSamples(data) {
        data.summary.acessos = { total: 0, autorizados: 0, negados: 0, indefinidos: 0 };
        data.summary.evolucao_diaria.dias = []; data.summary.salas_mais_acessadas = [];
        data.accesses.acessos = []; data.accesses.total = 0;
    } });
    await h.open('relatorios');
    assert.equal(h.id('st-metricas-acessos').querySelector('dd').textContent, '0');
    assert.equal(h.id('st-grafico-diario').querySelector('svg'), null);
    assert.match(h.id('st-grafico-diario').textContent, /Nenhuma tentativa/);
    assert.match(h.id('st-ranking').textContent, /Nenhum acesso registrado no período/);
    assert.match(h.id('st-acessos-corpo').textContent, /Nenhuma tentativa/);
});

test('limitação da série diária e valores completos são apresentados explicitamente', async (t) => {
    const h = await setup(t, { changeSamples(data) { data.summary.evolucao_diaria.ha_dias_anteriores = true; } });
    await h.open('relatorios');
    assert.match(h.id('st-grafico-limite').textContent, /366 dias.*totais incluem todos/s);
    const values = h.data.summary.evolucao_diaria.dias[0];
    assert.ok(h.id('st-diaria-corpo').textContent.includes(values.data));
});

test('atividades têm filtros próprios e não recebem local ou visitante do acesso', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    h.field('st-acessos-filtros', 'visitante').value = '4';
    await h.click(h.id('st-relatorio-tab-patrimonio'));
    const values = { inicio: '2026-10-01', fim: '2026-11-17', objeto: '1', usuario: '2', acao: 'buscar_objeto_id', resultado: 'sucesso' };
    for (const [name, value] of Object.entries(values)) h.field('st-atividades-filtros', name).value = value;
    await h.submit('st-atividades-filtros');
    const call = h.calls.filter((item) => item.path === '/api/relatorios/atividades').at(-1);
    for (const [name, value] of Object.entries(values)) assert.equal(call.params.get(name), value);
    assert.equal(call.params.has('visitante'), false); assert.equal(call.params.has('local'), false);
    assert.match(h.id('st-atividades-corpo').textContent, /Consulta por ID/);
    assert.match(h.id('st-atividades-recorte').textContent, /sucesso/);
});

test('dados textuais novos são escapados como texto, inclusive em tabela e ranking', async (t) => {
    const payload = '<img src=x onerror="window.invadiu=true">';
    const h = await setup(t, { changeSamples(data) {
        data.visitors.visitantes[0].nome = payload;
        data.accesses.acessos[0].local = payload;
        data.summary.salas_mais_acessadas[0].local = payload;
    } });
    await h.open('visitantes'); assert.ok(h.id('st-visitantes-corpo').textContent.includes(payload));
    assert.equal(h.id('st-visitantes-corpo').querySelector('img'), null);
    await h.open('relatorios');
    assert.ok(h.id('st-ranking').textContent.includes(payload));
    assert.equal(h.id('st-ranking').querySelector('img'), null);
    assert.equal(h.id('st-acessos-corpo').querySelector('img'), null);
    assert.equal(h.window.invadiu, undefined);
});

test('logout limpa os dados administrativos, fecha o diálogo e retorna ao painel original', async (t) => {
    const h = await setup(t); await h.open('visitantes'); await h.click(rowButton(h, 'Permissões'));
    h.window.fazerLogout(); await flush();
    assert.equal(h.id('st-visitantes-corpo').textContent, '');
    assert.equal(h.id('st-visitante-dialogo').open, false);
    assert.equal(h.field('st-visitante-formulario', 'nome').value, '');
    assert.equal(h.window.document.querySelectorAll('[data-safe-track-admin]:not([hidden])').length, 0);
    assert.equal(h.id('aba-dashboard').classList.contains('hidden'), false);
    assert.equal(h.id('tela-login').style.display, 'flex');
    assert.equal(h.window.localStorage.length, 0);
});

test('resposta atrasada de consulta não reaparece após sair ou iniciar outra sessão', async (t) => {
    let release;
    const h = await setup(t, { intercept(call, data) {
        if (call.path === '/visitantes' && call.method === 'GET') return new Promise((resolve) => { release = () => resolve(json(data.visitors)); });
    } });
    h.window.mudarAba('visitantes'); await flush();
    const pending = h.calls.find((call) => call.path === '/visitantes');
    h.window.fazerLogout();
    h.window.SafeTrackAdmin.setSession('users', 'users-token-ficticio');
    release(); await flush();
    assert.equal(pending.signal.aborted, true);
    assert.equal(h.id('st-visitantes-corpo').textContent, '');
    assert.equal(h.id('st-visitantes-mensagem').textContent, '');
});

test('resposta de filtro antigo não sobrescreve o recorte mais recente', async (t) => {
    let release;
    const h = await setup(t, { intercept(call, data) {
        if (call.path === '/api/dashboards/resumo' && call.params.get('resultado') === 'Negado') {
            const old = copy(data.summary); old.acessos.total = 999;
            return new Promise((resolve) => { release = () => resolve(json(old)); });
        }
    } });
    await h.open('relatorios');
    h.field('st-acessos-filtros', 'resultado').value = 'Negado'; await h.submit('st-acessos-filtros');
    h.field('st-acessos-filtros', 'resultado').value = 'Liberado'; await h.submit('st-acessos-filtros');
    release(); await flush();
    assert.equal(h.id('st-metricas-acessos').querySelector('dd').textContent, '2');
    assert.match(h.id('st-acessos-recorte').textContent, /Liberado/);
});

test('erro ao carregar referências impede envio até atualizar com sucesso', async (t) => {
    let fail = true;
    const h = await setup(t, { intercept(call) {
        if (fail && call.path === '/vizualizar_todos_rfid') return json({ message: 'Falha simulada de consulta.' }, 500);
    } });
    await h.open('visitantes'); await h.click(h.id('st-visitante-novo'));
    assert.equal(h.id('st-visitante-salvar').disabled, true);
    assert.match(h.id('st-visitante-formulario-mensagem').textContent, /Falha simulada/);
    fail = false; await h.click(h.id('st-visitante-referencias'));
    assert.equal(h.id('st-visitante-salvar').disabled, false);
    assert.ok(h.id('st-visitante-locais').querySelector('input'));
});

test('conflito ao salvar permanece visível sem limpar o formulário ou fechar o diálogo', async (t) => {
    const h = await setup(t, { intercept(call) {
        if (call.path === '/visitantes' && call.method === 'POST') return json({ message: 'Tag já associada a outro usuário ou objeto.' }, 409);
    } });
    await newVisitor(h); await h.submit('st-visitante-formulario');
    assert.equal(h.id('st-visitante-dialogo').open, true);
    assert.match(h.id('st-visitante-formulario-mensagem').textContent, /Tag já associada/);
    assert.equal(h.field('st-visitante-formulario', 'nome').value, 'Nova visitante');
    assert.equal(h.id('st-visitante-salvar').disabled, false);
});

test('JWT expirado nos novos endpoints retorna ao login e remove os dados privados', async (t) => {
    const h = await setup(t, { intercept(call) {
        if (call.path === '/api/dashboards/resumo') return json({ msg: 'Token has expired' }, 401);
    } });
    await h.open('relatorios');
    assert.equal(h.id('tela-login').style.display, 'flex');
    assert.equal(h.id('st-metricas-acessos').children.length, 0);
    assert.equal(h.id('st-acessos-csv').disabled, true);
    assert.match(h.alerts.at(-1), /sessão expirou/);
});

test('todos os destinos anteriores da navegação e o alias de tags permanecem funcionando', async (t) => {
    const h = await setup(t);
    for (const name of ['dashboard', 'busca', 'cadastro', 'usuarios', 'locais', 'tags']) {
        await h.open(name);
        const target = name === 'tags' ? 'sec-tags' : `aba-${name}`;
        assert.equal(h.id(target).classList.contains('hidden'), false);
        assert.equal(h.window.document.querySelectorAll('.secao-conteudo:not(.hidden)').length, 1);
    }
});

test('paginação de visitantes mantém a situação aplicada mesmo com seleção ainda não aplicada', async (t) => {
    const h = await setup(t, { intercept(call, data) {
        if (call.path === '/visitantes' && call.method === 'GET') return json({ ...data.visitors,
            visitantes: [data.visitors.visitantes[0]], total: 26, pagina: Number(call.params.get('pagina')), limite: 25 });
    } });
    await h.open('visitantes');
    h.field('st-visitantes-filtros', 'status').value = 'ativo'; await h.submit('st-visitantes-filtros');
    h.field('st-visitantes-filtros', 'status').value = 'expirado'; await h.click(h.id('st-visitantes-proxima'));
    const call = h.calls.filter((item) => item.path === '/visitantes').at(-1);
    assert.equal(call.params.get('status'), 'ativo'); assert.equal(call.params.get('pagina'), '2');
    assert.equal(h.id('st-visitantes-proxima').disabled, true);
    assert.match(h.id('st-visitantes-pagina').textContent, /Página 2 de 2/);
});

for (const scenario of ['conexao', 'json']) test(`falha de ${scenario} apresenta mensagem e permite reaplicar os filtros`, async (t) => {
    let fail = true;
    const h = await setup(t, { intercept(call) {
        if (fail && call.path === '/api/dashboards/resumo') {
            if (scenario === 'conexao') throw new TypeError('Failed to fetch');
            return new Response('resposta sem JSON', { status: 200 });
        }
    } });
    await h.open('relatorios');
    assert.equal(h.id('st-acessos-mensagem').dataset.state, 'error');
    assert.match(h.id('st-acessos-mensagem').textContent, scenario === 'conexao' ? /Falha na conexão/ : /ler a resposta/);
    assert.equal(h.id('st-acessos-csv').disabled, true);
    fail = false; await h.submit('st-acessos-filtros');
    assert.equal(h.id('st-acessos-mensagem').textContent, '');
    assert.equal(h.id('st-acessos-csv').disabled, false);
    assert.equal(h.id('st-metricas-acessos').querySelector('dd').textContent, '2');
});

const reportModules = ['acessos', 'visitantes', 'patrimonio', 'locais', 'exportacao'];

function selectedReport(h, name) {
    const panels = [...h.window.document.querySelectorAll('[data-st-report-panel]')];
    const tabs = [...h.window.document.querySelectorAll('[data-st-report-tab]')];
    assert.equal(panels.length, 5);
    assert.equal(tabs.length, 5);
    assert.equal(panels.filter((panel) => !panel.hidden).length, 1);
    assert.equal(h.id(`st-relatorio-painel-${name}`).hidden, false);
    assert.equal(tabs.filter((tab) => tab.getAttribute('aria-selected') === 'true').length, 1);
    assert.equal(h.id(`st-relatorio-tab-${name}`).getAttribute('aria-selected'), 'true');
    assert.equal(h.id(`st-relatorio-tab-${name}`).tabIndex, 0);
    assert.ok(tabs.filter((tab) => tab.id !== `st-relatorio-tab-${name}`).every((tab) => tab.tabIndex === -1));
}

test('dashboard operacional apresenta os dados existentes e inicia com o painel Acessos', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    assert.ok(h.id('st-dashboard-operacional'));
    assert.match(h.id('st-dashboard-operacional').textContent, /Dashboard Operacional/);
    assert.equal(h.id('st-dashboard-operacional').hidden, false);
    assert.equal(h.id('st-metrica-visitantes-ativos').textContent.trim(), String(h.data.summary.visitantes.ativos));
    assert.equal(h.id('st-patrimonio-total').textContent.trim(), String(h.data.summary.cadastros.objetos));
    assert.equal(h.id('st-locais-total').textContent.trim(), String(h.data.summary.cadastros.locais));
    assert.deepEqual([...h.id('st-metricas-cadastros').querySelectorAll('dd')].map((item) => item.textContent),
        ['objetos', 'tags_rfid', 'locais'].map((name) => String(h.data.summary.cadastros[name])));
    selectedReport(h, 'acessos');
});

test('cinco módulos alternam um único painel com seleção acessível e dashboard sempre visível', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    for (const name of reportModules) {
        const tab = h.id(`st-relatorio-tab-${name}`);
        assert.equal(tab.tagName, 'BUTTON'); assert.equal(tab.type, 'button');
        assert.equal(tab.getAttribute('role'), 'tab');
        assert.equal(tab.getAttribute('aria-controls'), `st-relatorio-painel-${name}`);
        assert.equal(h.id(`st-relatorio-painel-${name}`).getAttribute('role'), 'tabpanel');
        assert.equal(h.id(`st-relatorio-painel-${name}`).getAttribute('aria-labelledby'), tab.id);
        await h.click(tab); selectedReport(h, name);
        assert.equal(h.id('st-dashboard-operacional').hidden, false);
        assert.equal(h.id('aba-relatorios').classList.contains('hidden'), false);
        assert.equal(h.window.document.querySelectorAll('.secao-conteudo:not(.hidden)').length, 1);
    }
});

test('filtros e CSV possuem uma instância compartilhada somente em Acessos e Exportação', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    const host = h.id('st-relatorio-ferramentas');
    const form = h.id('st-acessos-filtros'); const csv = h.id('st-acessos-csv');
    assert.ok(host.contains(form)); assert.ok(host.contains(csv));
    for (const name of reportModules) {
        await h.click(h.id(`st-relatorio-tab-${name}`));
        assert.equal(host.hidden, !['acessos', 'exportacao'].includes(name));
        assert.equal(h.id('st-acessos-filtros'), form); assert.equal(h.id('st-acessos-csv'), csv);
        assert.equal(h.window.document.querySelectorAll('[id="st-acessos-filtros"]').length, 1);
        assert.equal(h.window.document.querySelectorAll('[id="st-acessos-csv"]').length, 1);
    }
});

test('teclado usa setas Home e End para foco e seleção das abas sem recarregar a página', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    async function key(name, value, expected) {
        const tab = h.id(`st-relatorio-tab-${name}`); tab.focus();
        tab.dispatchEvent(new h.window.KeyboardEvent('keydown', { key: value, bubbles: true, cancelable: true }));
        await flush();
        assert.equal(h.window.document.activeElement, h.id(`st-relatorio-tab-${expected}`));
        selectedReport(h, expected);
    }
    await key('acessos', 'ArrowRight', 'visitantes');
    await key('visitantes', 'End', 'exportacao');
    await key('exportacao', 'ArrowRight', 'acessos');
    await key('acessos', 'ArrowLeft', 'exportacao');
    await key('exportacao', 'Home', 'acessos');
    assert.equal(h.window.location.href, 'http://localhost:5001/');
});

test('módulos preservam recorte aplicado página atual e formulário pendente sem repetir consultas', async (t) => {
    const h = await setup(t, { changeSamples(data) { data.accesses.total = 26; } });
    await h.open('relatorios');
    h.field('st-acessos-filtros', 'resultado').value = 'Negado'; await h.submit('st-acessos-filtros');
    await h.click(h.id('st-acessos-proxima'));
    h.field('st-acessos-filtros', 'resultado').value = 'Liberado';
    const before = h.calls.length;
    for (const name of ['visitantes', 'locais', 'exportacao', 'acessos']) await h.click(h.id(`st-relatorio-tab-${name}`));
    assert.equal(h.calls.length, before);
    assert.equal(h.field('st-acessos-filtros', 'resultado').value, 'Liberado');
    assert.match(h.id('st-acessos-recorte').textContent, /Negado/);
    assert.match(h.id('st-acessos-pagina').textContent, /Página 2 de 2/);
    await h.click(h.id('st-relatorio-tab-exportacao')); await h.click(h.id('st-acessos-csv'));
    const csv = h.calls.filter((call) => call.path.endsWith('.csv')).at(-1);
    assert.equal(csv.params.get('resultado'), 'Negado');
    assert.equal(csv.params.has('pagina'), false); assert.equal(h.downloads.length, 1);
});

test('Patrimônio carrega atividades uma vez e alternar módulos não reaplica seus filtros', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    assert.equal(h.calls.filter((call) => call.path === '/api/relatorios/atividades').length, 0);
    const beforeFirstSelection = h.calls.length;
    await h.click(h.id('st-relatorio-tab-patrimonio'));
    assert.equal(h.id('st-atividades-painel').open, true);
    assert.equal(h.calls.filter((call) => call.path === '/api/relatorios/atividades').length, 1);
    assert.equal(h.calls.length, beforeFirstSelection + 1);
    assert.equal(h.calls.at(-1).path, '/api/relatorios/atividades');
    h.field('st-atividades-filtros', 'resultado').value = 'falha'; await h.submit('st-atividades-filtros');
    const before = h.calls.length;
    await h.click(h.id('st-relatorio-tab-locais')); await h.click(h.id('st-relatorio-tab-patrimonio'));
    assert.equal(h.calls.length, before);
    assert.equal(h.field('st-atividades-filtros', 'resultado').value, 'falha');
    assert.match(h.id('st-atividades-recorte').textContent, /falha/);
});

test('Visitantes analítico reaproveita as cinco contagens sem consultar ou alterar contas', async (t) => {
    const h = await setup(t); await h.open('relatorios'); const before = h.calls.length;
    await h.click(h.id('st-relatorio-tab-visitantes'));
    const values = [...h.id('st-metricas-visitantes').querySelectorAll('dd')].map((item) => item.textContent);
    assert.deepEqual(values, ['cadastrados', 'ativos', 'agendados', 'expirados', 'revogados'].map((name) => String(h.data.summary.visitantes[name])));
    assert.equal(h.calls.length, before);
    assert.equal(h.calls.filter((call) => call.path.startsWith('/visitantes')).length, 0);
});

test('Locais detalha somente o ranking recebido e mantém uma única instância dos gráficos', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    const graph = h.id('st-grafico-diario').querySelector('svg'); const ranking = h.id('st-ranking');
    const before = h.calls.length;
    for (const name of ['locais', 'visitantes', 'exportacao', 'acessos', 'locais']) await h.click(h.id(`st-relatorio-tab-${name}`));
    assert.equal(h.calls.length, before);
    assert.equal(h.id('st-grafico-diario').querySelector('svg'), graph); assert.equal(h.id('st-ranking'), ranking);
    assert.equal(h.window.document.querySelectorAll('#st-grafico-diario svg').length, 1);
    assert.equal(h.window.document.querySelectorAll('[id="st-ranking"]').length, 1);
    assert.equal(h.id('st-locais-corpo').rows.length, h.data.summary.salas_mais_acessadas.length);
    for (const place of h.data.summary.salas_mais_acessadas) {
        assert.ok(h.id('st-locais-corpo').textContent.includes(place.local));
        assert.ok(h.id('st-locais-corpo').textContent.includes(String(place.autorizados)));
    }
});

test('Locais sem acessos autorizados apresenta estado vazio sem distribuição fictícia', async (t) => {
    const h = await setup(t, { changeSamples(data) { data.summary.salas_mais_acessadas = []; } });
    await h.open('relatorios'); await h.click(h.id('st-relatorio-tab-locais'));
    assert.match(h.id('st-locais-corpo').textContent, /Nenhum acesso autorizado/);
    assert.equal(h.id('st-locais-corpo').querySelector('td').colSpan > 1, true);
});

test('alternância interna não altera o conteúdo das outras páginas ou do diálogo de Visitantes', async (t) => {
    const h = await setup(t);
    const ids = ['aba-dashboard', 'aba-busca', 'aba-cadastro', 'aba-usuarios', 'aba-locais', 'sec-tags', 'aba-visitantes', 'st-visitante-dialogo'];
    const before = ids.map((id) => h.id(id).innerHTML);
    await h.open('relatorios');
    for (const name of reportModules) await h.click(h.id(`st-relatorio-tab-${name}`));
    assert.deepEqual(ids.map((id) => h.id(id).innerHTML), before);
});

test('logout limpa também os novos resumos e reinicia Acessos na próxima entrada', async (t) => {
    const h = await setup(t); await h.open('relatorios'); await h.click(h.id('st-relatorio-tab-visitantes'));
    h.window.fazerLogout(); await flush();
    for (const id of ['st-metrica-visitantes-ativos', 'st-patrimonio-total', 'st-locais-total']) assert.ok(['', '—'].includes(h.id(id).textContent.trim()));
    assert.equal(h.id('st-locais-corpo').textContent, '');
    await h.window.fazerLogin(); await flush(); await h.open('relatorios');
    selectedReport(h, 'acessos'); assert.equal(h.id('st-relatorio-ferramentas').hidden, false);
});

function sampleRanking(count) {
    return Array.from({ length: count }, (_, index) => ({
        id_local: index + 101, local: `Sala fictícia ${index + 1}`, autorizados: (count - index) * 10,
    }));
}

function rankingItems(h) { return [...h.id('st-ranking').querySelectorAll('[data-st-ranking-item]')]; }
function visibleRankingItems(h) { return rankingItems(h).filter((item) => !item.hidden); }

for (const count of [0, 1, 2, 3, 4, 10]) test(`ranking com ${count} salas mostra Top 3 sem truncar dados do módulo Locais`, async (t) => {
    const h = await setup(t, { changeSamples(data) { data.summary.salas_mais_acessadas = sampleRanking(count); } });
    await h.open('relatorios');
    assert.equal(rankingItems(h).length, count);
    assert.equal(visibleRankingItems(h).length, Math.min(count, 3));
    assert.equal(h.id('st-ranking-expandir').getAttribute('aria-expanded'), 'false');
    assert.equal(h.id('st-ranking-expandir').getAttribute('aria-controls'), 'st-ranking');
    if (count <= 3) assert.ok(h.id('st-ranking-expandir').hidden || h.id('st-ranking-expandir').disabled);
    else assert.equal(h.id('st-ranking-expandir').hidden, false);
    if (count === 0) {
        assert.match(h.id('st-ranking').textContent, /Nenhum acesso registrado no período/);
        assert.ok(h.id('st-ranking').querySelector('[aria-hidden="true"]'));
        assert.match(h.id('st-locais-corpo').textContent, /Nenhum acesso autorizado/);
    } else {
        assert.equal(h.id('st-locais-corpo').rows.length, count);
        assert.equal(h.id('st-locais-corpo').querySelectorAll('tr[hidden]').length, 0);
        for (const [index, item] of rankingItems(h).entries()) {
            assert.ok(item.textContent.includes(h.data.summary.salas_mais_acessadas[index].local));
            assert.ok(item.textContent.includes(String(h.data.summary.salas_mais_acessadas[index].autorizados)));
        }
    }
    const before = h.calls.length;
    await h.click(h.id('st-relatorio-tab-locais'));
    assert.equal(h.calls.length, before);
    if (count) assert.equal(h.id('st-locais-corpo').rows.length, count);
});

test('expansão do ranking mantém ordem barras contagens e instâncias sem consultas adicionais', async (t) => {
    const places = [
        { id_local: 17, local: 'Zeta', autorizados: 40 },
        { id_local: 41, local: 'Alfa', autorizados: 40 },
        { id_local: 52, local: 'Beta', autorizados: 20 },
        { id_local: 70, local: 'Gama', autorizados: 10 },
        { id_local: 99, local: 'Delta', autorizados: 5 },
    ];
    const h = await setup(t, { changeSamples(data) { data.summary.salas_mais_acessadas = places; } });
    await h.open('relatorios');
    const items = rankingItems(h); const graph = h.id('st-grafico-diario').querySelector('svg');
    const widths = items.map((item) => item.querySelector('.st-rank-fill').style.width);
    assert.deepEqual(widths, ['100%', '100%', '50%', '25%', '12.5%']);
    assert.match(h.id('st-ranking-expandir').textContent, /Ver ranking disponível \(até 10 salas\)/);
    assert.match(h.id('st-ranking-limite').textContent, /(?:até 10|Top 10)/i);
    assert.match(h.id('st-ranking-limite').textContent, /integral/i);
    const before = h.calls.length;
    await h.click(h.id('st-ranking-expandir'));
    assert.equal(visibleRankingItems(h).length, places.length);
    assert.equal(h.id('st-ranking-expandir').getAttribute('aria-expanded'), 'true');
    assert.equal(h.id('st-ranking-expandir').textContent.trim(), 'Mostrar menos');
    assert.deepEqual(rankingItems(h), items);
    for (const [index, item] of rankingItems(h).entries()) {
        assert.ok(item.textContent.includes(places[index].local));
        assert.match(item.textContent, new RegExp(`^\\s*${index + 1}º`));
    }
    assert.deepEqual(items.map((item) => item.querySelector('.st-rank-fill').style.width), widths);
    assert.equal(h.id('st-grafico-diario').querySelector('svg'), graph);
    assert.equal(h.window.document.querySelectorAll('[id="st-ranking"]').length, 1);
    assert.equal(h.calls.length, before);
    await h.click(h.id('st-ranking-expandir'));
    assert.equal(visibleRankingItems(h).length, 3);
    assert.equal(h.id('st-ranking-expandir').getAttribute('aria-expanded'), 'false');
    assert.deepEqual(rankingItems(h), items);
    assert.equal(h.calls.length, before);
    assert.equal(h.window.location.href, 'http://localhost:5001/');
});

test('novo recorte recolhe o ranking e usa todas as salas da resposta nova no módulo Locais', async (t) => {
    const h = await setup(t, { changeSamples(data) { data.summary.salas_mais_acessadas = sampleRanking(10); } });
    await h.open('relatorios'); await h.click(h.id('st-ranking-expandir'));
    assert.equal(visibleRankingItems(h).length, 10);
    h.data.summary.salas_mais_acessadas = sampleRanking(4);
    h.field('st-acessos-filtros', 'resultado').value = 'Liberado';
    const before = h.calls.length;
    await h.submit('st-acessos-filtros');
    assert.equal(h.calls.length, before + 2);
    assert.equal(rankingItems(h).length, 4); assert.equal(visibleRankingItems(h).length, 3);
    assert.equal(h.id('st-ranking-expandir').getAttribute('aria-expanded'), 'false');
    assert.equal(h.id('st-locais-corpo').rows.length, 4);
    assert.match(h.id('st-acessos-recorte').textContent, /Liberado/);
});

for (const failure of ['loading', 'erro']) test(`expansão fica indisponível no estado de ${failure} e não expõe ranking anterior`, async (t) => {
    let mode = 'normal', release;
    const h = await setup(t, {
        changeSamples(data) { data.summary.salas_mais_acessadas = sampleRanking(10); },
        intercept(call, data) {
            if (call.path !== '/api/dashboards/resumo') return;
            if (mode === 'loading') return new Promise((resolve) => { release = () => resolve(json(data.summary)); });
            if (mode === 'erro') return json({ message: 'Falha simulada na consulta dos indicadores.' }, 500);
        },
    });
    await h.open('relatorios'); await h.click(h.id('st-ranking-expandir'));
    mode = failure;
    await h.submit('st-acessos-filtros');
    assert.equal(rankingItems(h).length, 0);
    assert.ok(h.id('st-ranking-expandir').hidden || h.id('st-ranking-expandir').disabled);
    assert.equal(h.id('st-ranking-expandir').getAttribute('aria-expanded'), 'false');
    if (failure === 'loading') {
        release(); await flush();
        assert.equal(rankingItems(h).length, 10); assert.equal(visibleRankingItems(h).length, 3);
    } else {
        assert.equal(h.id('st-acessos-mensagem').dataset.state, 'error');
        assert.match(h.id('st-acessos-mensagem').textContent, /Falha simulada/);
    }
});

test('nome malicioso continua sendo texto seguro quando a quarta sala é expandida', async (t) => {
    const payload = '<img src=x onerror="window.rankingInvadido=true">';
    const h = await setup(t, { changeSamples(data) {
        data.summary.salas_mais_acessadas = sampleRanking(4);
        data.summary.salas_mais_acessadas[3].local = payload;
    } });
    await h.open('relatorios');
    assert.equal(rankingItems(h)[3].hidden, true);
    await h.click(h.id('st-ranking-expandir'));
    assert.equal(rankingItems(h)[3].hidden, false);
    assert.ok(rankingItems(h)[3].textContent.includes(payload));
    assert.equal(rankingItems(h)[3].querySelector('img,script,svg'), null);
    assert.equal(h.id('st-locais-corpo').querySelector('img'), null);
    assert.equal(h.window.rankingInvadido, undefined);
});

test('dashboard mantém gráfico e resumo no topo indicadores gerais no meio e ranking abaixo', async (t) => {
    const h = await setup(t); await h.open('relatorios');
    const primary = h.id('st-dashboard-operacional').querySelector('.st-dashboard-primary');
    const chart = h.id('st-dashboard-chart'); const summary = h.id('st-dashboard-summary');
    const general = h.id('st-dashboard-general'); const ranking = h.id('st-dashboard-ranking');
    const follows = h.window.Node.DOCUMENT_POSITION_FOLLOWING;
    assert.ok(primary.contains(chart)); assert.ok(primary.contains(summary));
    assert.ok(chart.contains(h.id('st-grafico-diario')));
    assert.ok(summary.contains(h.id('st-metricas-acessos')));
    assert.ok(general.contains(h.id('st-metricas-cadastros')));
    assert.ok(general.contains(h.id('st-metrica-visitantes-ativos')));
    assert.ok(ranking.contains(h.id('st-ranking')));
    assert.ok(chart.compareDocumentPosition(summary) & follows);
    assert.ok(primary.compareDocumentPosition(general) & follows);
    assert.ok(general.compareDocumentPosition(ranking) & follows);
    assert.ok(ranking.compareDocumentPosition(h.id('aba-relatorios').querySelector('.st-report-explore')) & follows);
    assert.equal(summary.querySelectorAll('.st-metric').length, 4);
    assert.equal(general.querySelectorAll('.st-metric').length, 4);
    for (const card of [...summary.querySelectorAll('.st-metric'), ...general.querySelectorAll('.st-metric')]) {
        assert.ok(card.querySelector('i[aria-hidden="true"]'));
        assert.ok(card.querySelector('dt')); assert.ok(card.querySelector('dd'));
    }
});

test('expandir o ranking preserva Explorar Relatórios filtros tabelas e a instância do gráfico', async (t) => {
    const h = await setup(t, { changeSamples(data) { data.summary.salas_mais_acessadas = sampleRanking(10); } });
    await h.open('relatorios');
    const ids = ['st-relatorio-ferramentas', ...reportModules.map((name) => `st-relatorio-painel-${name}`)];
    const before = ids.map((id) => h.id(id).outerHTML);
    const explore = h.id('aba-relatorios').querySelector('.st-report-explore').outerHTML;
    const tabs = [...h.id('aba-relatorios').querySelectorAll('[data-st-report-tab]')].map((tab) => tab.outerHTML);
    const graph = h.id('st-grafico-diario').querySelector('svg');
    await h.click(h.id('st-ranking-expandir')); await h.click(h.id('st-ranking-expandir'));
    assert.deepEqual(ids.map((id) => h.id(id).outerHTML), before);
    assert.equal(h.id('aba-relatorios').querySelector('.st-report-explore').outerHTML, explore);
    assert.deepEqual([...h.id('aba-relatorios').querySelectorAll('[data-st-report-tab]')].map((tab) => tab.outerHTML), tabs);
    assert.equal(h.id('st-grafico-diario').querySelector('svg'), graph);
});

test('gráfico vazio mostra mensagem e ícone sem dados fictícios ou novas instâncias', async (t) => {
    const h = await setup(t, { changeSamples(data) {
        data.summary.evolucao_diaria.dias = [];
        data.summary.acessos = { total: 0, autorizados: 0, negados: 0, indefinidos: 0 };
        data.summary.salas_mais_acessadas = []; data.accesses.acessos = []; data.accesses.total = 0;
    } });
    await h.open('relatorios');
    assert.equal(h.id('st-grafico-diario').querySelector('svg'), null);
    assert.ok(h.id('st-grafico-diario').querySelector('[aria-hidden="true"]'));
    assert.match(h.id('st-grafico-diario').textContent, /Nenhuma tentativa/);
    assert.equal(h.id('st-metricas-acessos').querySelector('dd').textContent, '0');
    assert.equal(rankingItems(h).length, 0);
    assert.ok(h.id('st-ranking-expandir').hidden || h.id('st-ranking-expandir').disabled);
});

test('logout recolhe o ranking e a sessão seguinte inicia com Top 3', async (t) => {
    const h = await setup(t, { changeSamples(data) { data.summary.salas_mais_acessadas = sampleRanking(10); } });
    await h.open('relatorios'); await h.click(h.id('st-ranking-expandir'));
    h.window.fazerLogout(); await flush();
    assert.equal(rankingItems(h).length, 0);
    assert.equal(h.id('st-ranking-expandir').getAttribute('aria-expanded'), 'false');
    assert.ok(h.id('st-ranking-expandir').hidden || h.id('st-ranking-expandir').disabled);
    await h.window.fazerLogin(); await flush(); await h.open('relatorios');
    assert.equal(visibleRankingItems(h).length, 3);
    assert.equal(h.id('st-ranking-expandir').getAttribute('aria-expanded'), 'false');
});
