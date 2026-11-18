/* DOM simulado com contratos reais exportados pelo Pytest; nenhuma conexão externa. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');
const root = path.resolve(__dirname, '../../../..'), output = process.env.SAFE_TRACK_FRONTEND_ARTIFACTS;
const html = readFileSync(path.join(output, 'index-renderizado.html'), 'utf8');
const samples = JSON.parse(readFileSync(path.join(output, 'permissions-api.json'), 'utf8'));
const original = readFileSync(path.join(root, 'src/app/static/script.js'), 'utf8');
const script = readFileSync(path.join(root, 'src/app/static/permissions.js'), 'utf8');
const admin = readFileSync(path.join(root, 'src/app/static/admin.js'), 'utf8');
const nav = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map((m) => m[1]).find((s) => s.includes('window.mudarAba ='));
const copy = (v) => JSON.parse(JSON.stringify(v));
const json = (v, status = 200) => new Response(JSON.stringify(v), { status, headers: { 'Content-Type': 'application/json' } });
async function flush() { for (let n = 0; n < 15; n++) await new Promise(setImmediate); }
async function setup(t, { role = 'roots', intercept = null, change = null } = {}) {
    const data = copy(samples); if (change) change(data);
    const errors = [], calls = [], confirmations = [];
    const console = new VirtualConsole(); console.on('jsdomError', (error) => errors.push(error.message));
    const dom = new JSDOM(html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ''), { url: 'http://safe-track.test/', runScripts: 'dangerously', virtualConsole: console });
    const w = dom.window, id = (name) => w.document.getElementById(name);
    let accept = true;
    w.io = () => ({ on() {} }); w.lottie = { loadAnimation: () => ({ addEventListener() {} }) };
    w.scrollTo = () => {}; w.alert = () => {}; w.confirm = (text) => { confirmations.push(text); return accept; };
    const people = new Map([[data.person.pessoa.id, copy(data.person.pessoa)], [data.expired_person.pessoa.id, copy(data.expired_person.pessoa)]]);
    const rows = [...copy(data.person.permissoes), ...copy(data.room_all.autorizacoes).filter((r) => r.pessoa.id !== data.person.pessoa.id)];
    for (const row of rows) people.set(row.pessoa.id, row.pessoa);
    const page = (list, params, key, extras) => {
        const pagina = Number(params.get('pagina') || 1), limite = Number(params.get('limite') || 25);
        return { ...extras, [key]: list.slice((pagina - 1) * limite, pagina * limite), total: list.length, pagina, limite };
    };
    w.fetch = async (url, options = {}) => {
        const parsed = new URL(url, 'http://safe-track.test');
        const c = { path: parsed.pathname, params: parsed.searchParams, method: options.method || 'GET', headers: options.headers,
            body: options.body ? JSON.parse(options.body) : null, signal: options.signal };
        calls.push(c); if (intercept) { const response = await intercept(c, data); if (response !== undefined) return response; }
        if (c.path === '/login') return json({ access_token: `${role}-token-ficticio`, user_type: role });
        if (c.path === '/listar_locais') return json(data.locals);
        if (c.path === '/visualizar_todos_usuarios') return json(data.accounts);
        const p = c.path.match(/^\/pessoas\/(\d+)\/permissoes(?:\/(\d+)(\/revogar)?)?$/);
        const room = c.path.match(/^\/locais\/(\d+)\/autorizacoes$/);
        if ((p || room) && role !== 'roots') return json({ message: 'Acesso negado' }, 403);
        if (p) {
            const personId = Number(p[1]), localId = Number(p[2]);
            if (!people.has(personId)) return json({ message: 'Pessoa não encontrada.' }, 404);
            if (c.method === 'GET') return json(page(rows.filter((r) => r.pessoa.id === personId).sort((a, b) => a.local.id - b.local.id), c.params, 'permissoes', { pessoa: people.get(personId) }));
            let row = rows.find((r) => r.pessoa.id === personId && r.local.id === localId);
            if (!row) { row = { pessoa: people.get(personId), local: data.locals.locais.find((l) => l.id === localId), inicio: null, expiracao: null, revogada: false }; rows.push(row); }
            if (p[3]) row.revogada = true; else Object.assign(row, c.body);
            row.situacao = row.revogada ? 'revogada' : row.inicio && new Date(row.inicio) > new Date() ? 'agendada' : row.expiracao && new Date(row.expiracao) <= new Date() ? 'expirada' : 'vigente';
            row.acesso_efetivo = row.situacao === 'vigente' && row.pessoa.status_credencial === 'ativo';
            return json({ permissao: row });
        }
        if (room) {
            const local = data.locals.locais.find((l) => l.id === Number(room[1]));
            const state = c.params.get('situacao');
            return json(page(rows.filter((r) => r.local.id === local.id && (state ? state === 'todas' || r.situacao === state : r.acesso_efetivo)), c.params, 'autorizacoes', { local }));
        }
        return json({ objetos: [], tags: [], usuarios: [] });
    };
    // O eval único reproduz o escopo lexical compartilhado dos scripts clássicos do navegador.
    w.eval(`${original}\n${nav}\n${admin}\n${script}`);
    t.after(() => { dom.window.close(); assert.deepEqual(errors, []); });
    await w.fazerLogin(); await flush();
    const submit = async (name) => { id(name).dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true })); await flush(); };
    const person = async (value = data.ids.person) => { w.mudarAba('usuarios'); id('st-person-search').elements.pessoa.value = value; await submit('st-person-search'); };
    const room = async (filter = '') => { w.mudarAba('locais'); id('st-local-search').elements.local.value = data.ids.room; id('st-local-search').elements.situacao.value = filter; await submit('st-local-search'); };
    const edit = async (value) => { id('st-permission-local').value = value; id('st-permission-local').dispatchEvent(new w.Event('change')); await flush(); };
    return { w, id, data, calls, rows, confirmations, submit, person, room, edit, confirm: (value) => { accept = value; },
        writes: () => calls.filter((c) => c.path.startsWith('/pessoas/') && c.method !== 'GET') };
}
const click = async (button) => { button.click(); await flush(); };
const action = (h, body, label, row = 0) => [...h.id(body).rows[row].querySelectorAll('button')].find((b) => b.textContent === label);

test('login não acrescenta consultas de permissões; ações ficam nas tabelas de Pessoas/Locais', async (t) => {
    const h = await setup(t);
    assert.equal(h.calls.filter((c) => /^\/(pessoas|locais)\//.test(c.path)).length, 0);
    await click(h.id('tabela-usuarios').querySelector(`[data-st-person-permissions="${h.data.ids.person}"]`));
    assert.equal(h.id('st-person-detail').hidden, false);
    assert.equal(h.id('aba-usuarios').classList.contains('hidden'), false);
    await click(h.id('tabela-locais').querySelector('[data-st-room-permissions]'));
    assert.equal(h.id('st-local-detail').hidden, false);
});
test('pessoa mostra identificação, RFID, tipo, credencial e permissões sem acesso universal', async (t) => {
    const h = await setup(t); await h.person();
    assert.match(h.id('st-person-summary').textContent, /Usuário comum/);
    assert.ok(h.id('st-person-summary').textContent.includes(String(h.data.person.pessoa.credencial_rfid)));
    assert.equal(h.id('st-person-rows').rows.length, 2);
    assert.match(h.id('st-person-rows').textContent, /Vigente.*Permitido.*Revogada.*Negado/s);
    assert.equal(h.calls.find((c) => c.path.startsWith('/pessoas/')).headers.Authorization, 'Bearer roots-token-ficticio');
});
test('visitante expirado mantém permissão vigente e acesso negado, com validade global visível', async (t) => {
    const h = await setup(t); await h.person(h.data.ids.expired);
    assert.match(h.id('st-person-summary').textContent, /Visitante.*Expirada/s);
    assert.match(h.id('st-person-rows').textContent, /Vigente.*Negado/s);
    assert.match(h.id('st-person-summary').textContent, /até/);
});
test('consulta por sala distingue autorizados agora de todas e dos quatro estados individuais', async (t) => {
    const h = await setup(t); await h.room();
    assert.ok(!h.id('st-local-rows').textContent.includes(h.data.expired_person.pessoa.nome));
    assert.equal(h.calls.filter((c) => c.path.endsWith('/autorizacoes')).at(-1).params.has('situacao'), false);
    await h.room('todas'); assert.ok(h.id('st-local-rows').textContent.includes(h.data.expired_person.pessoa.nome));
    for (const state of ['vigente', 'agendada', 'expirada', 'revogada']) {
        await h.room(state); assert.equal(h.calls.filter((c) => c.path.endsWith('/autorizacoes')).at(-1).params.get('situacao'), state);
    }
});
test('concessão sem prazo envia somente datas nulas e revogada false para o par escolhido', async (t) => {
    const h = await setup(t); await h.person(); await h.edit(h.data.ids.third); await h.submit('st-permission-form');
    assert.deepEqual(h.writes()[0].body, { inicio: null, expiracao: null, revogada: false });
    assert.equal(h.writes()[0].path, `/pessoas/${h.data.ids.person}/permissoes/${h.data.ids.third}`);
    assert.equal(h.writes()[0].method, 'PUT'); assert.match(h.id('st-person-message').textContent, /salva/);
});
test('concessão converte horário do navegador para UTC sem enviar campos de dispositivos', async (t) => {
    const h = await setup(t); await h.person(); await h.edit(h.data.ids.third);
    const form = h.id('st-permission-form'); form.elements.inicio.value = '2027-01-01T10:30'; form.elements.expiracao.value = '2027-01-01T12:30';
    await h.submit('st-permission-form');
    assert.deepEqual(h.writes()[0].body, { inicio: '2027-01-01T13:30:00.000Z', expiracao: '2027-01-01T15:30:00.000Z', revogada: false });
    assert.match(h.id('st-permission-timezone').textContent, /America\/Sao_Paulo/);
});
test('editar vigência de revogada preserva estado e microssegundos do início omitido', async (t) => {
    const h = await setup(t); await h.person(); await h.edit(h.data.ids.second);
    h.id('st-permission-form').elements.expiracao.value = ''; await h.submit('st-permission-form');
    assert.deepEqual(h.writes()[0].body, { expiracao: null });
    assert.equal(h.rows.find((r) => r.local.id === h.data.ids.second).revogada, true);
    assert.equal(h.rows.find((r) => r.local.id === h.data.ids.second).inicio, '2026-01-01T10:30:00.123456Z');
    assert.equal(h.id('st-permission-reactivate').hidden, false);
});
test('formulário inalterado e intervalo invertido não gravam', async (t) => {
    const h = await setup(t); await h.person(); await h.edit(h.data.ids.second); await h.submit('st-permission-form');
    assert.equal(h.writes().length, 0); assert.match(h.id('st-editor-message').textContent, /Nenhuma alteração/);
    h.id('st-permission-form').elements.inicio.value = '2035-01-01T10:00'; await h.submit('st-permission-form');
    assert.equal(h.writes().length, 0); assert.equal(h.id('st-editor-message').dataset.state, 'error');
});
test('reativação é explícita, confirmada e envia apenas revogada false', async (t) => {
    const h = await setup(t); await h.person(); await h.edit(h.data.ids.second);
    h.confirm(false); await click(h.id('st-permission-reactivate')); assert.equal(h.writes().length, 0);
    h.confirm(true); await click(h.id('st-permission-reactivate'));
    assert.deepEqual(h.writes()[0].body, { revogada: false });
    assert.equal(h.id('st-permission-reactivate').hidden, true);
});
test('revogar uma sala preserva a pessoa e a permissão da outra sala; cancelar não grava', async (t) => {
    const h = await setup(t); await h.person(); h.confirm(false);
    await click(action(h, 'st-person-rows', 'Revogar')); assert.equal(h.writes().length, 0);
    h.confirm(true); const other = copy(h.rows.find((r) => r.local.id === h.data.ids.second));
    await click(action(h, 'st-person-rows', 'Revogar'));
    assert.equal(h.writes()[0].method, 'POST'); assert.equal(h.writes()[0].body, null);
    assert.equal(h.writes()[0].path, `/pessoas/${h.data.ids.person}/permissoes/${h.data.ids.room}/revogar`);
    assert.deepEqual(h.rows.find((r) => r.local.id === h.data.ids.second), other);
    assert.match(h.id('st-person-summary').textContent, /Usuário comum/);
    assert.ok(action(h, 'st-person-rows', 'Revogar').disabled);
});
test('sala permite gerenciar pessoa existente e conceder para outra pessoa pelo ID', async (t) => {
    const h = await setup(t); await h.room('todas'); await click(action(h, 'st-local-rows', 'Gerenciar'));
    assert.equal(h.id('aba-usuarios').classList.contains('hidden'), false);
    assert.equal(h.id('st-permission-local').value, String(h.data.ids.room));
    await h.room(); h.id('st-local-add').elements.pessoa.value = h.data.ids.expired; await h.submit('st-local-add');
    assert.match(h.id('st-person-summary').textContent, /Visitante.*Expirada/s);
});
for (const kind of ['person', 'local']) test(`paginação ${kind} envia página e limite sem alterar os filtros`, async (t) => {
    const h = await setup(t, { intercept(c, data) {
        if (c.method !== 'GET' || (kind === 'person' ? !/^\/pessoas\/\d+\/permissoes$/.test(c.path) : !c.path.endsWith('/autorizacoes'))) return;
        const page = Number(c.params.get('pagina')); return json({ ...(kind === 'person' ? data.person : data.room_all), pagina: page, limite: 25, total: 26 });
    } });
    if (kind === 'person') await h.person(); else await h.room('todas');
    await click(h.id(`st-${kind}-next`)); assert.match(h.id(`st-${kind}-page`).textContent, /Página 2 de 2/);
    assert.ok(h.id(`st-${kind}-next`).disabled); await click(h.id(`st-${kind}-prev`));
    assert.match(h.id(`st-${kind}-page`).textContent, /Página 1 de 2/);
});
for (const status of [400, 404, 409, 500]) test(`HTTP ${status} na consulta é apresentado e não revela dados anteriores`, async (t) => {
    let fail = false;
    const h = await setup(t, { intercept(c) { if (fail && c.path.startsWith('/pessoas/')) return json({ message: `Erro de teste ${status}` }, status); } });
    await h.person(); fail = true; await h.person(999);
    assert.equal(h.id('st-person-detail').hidden, true); assert.match(h.id('st-person-message').textContent, new RegExp(String(status)));
});
for (const role of ['users', 'visitante']) test(`${role} recebe 403 e não tem editor nem envia gravações`, async (t) => {
    const h = await setup(t, { role }); await h.person(); await h.room();
    assert.equal(h.id('st-person-detail').hidden, true); assert.equal(h.id('st-local-detail').hidden, true);
    assert.match(h.id('st-local-message').textContent, /somente Root/); assert.equal(h.writes().length, 0);
});
test('401 limpa consultas de pessoa e sala, com instrução para entrar novamente', async (t) => {
    let expire = false;
    const h = await setup(t, { intercept(c) { if (expire && c.path.endsWith('/autorizacoes')) return json({}, 401); } });
    await h.person(); await h.room(); expire = true; await h.room();
    assert.equal(h.id('st-person-summary').textContent, ''); assert.equal(h.id('st-local-rows').textContent, '');
    assert.match(h.id('st-person-message').textContent, /Entre novamente/);
});
test('resposta de pessoa anterior não substitui a consulta mais recente', async (t) => {
    let resolve;
    const h = await setup(t, { intercept(c, data) {
        if (c.path === `/pessoas/${data.ids.person}/permissoes`) return new Promise((r) => { resolve = () => r(json(data.person)); });
    } });
    await h.person(); await h.person(h.data.ids.expired); resolve(); await flush();
    assert.ok(h.id('st-person-summary').textContent.includes(h.data.expired_person.pessoa.nome));
});
test('logout limpa os componentes e descarta resposta pendente da sessão anterior', async (t) => {
    let pending = false, resolve;
    const h = await setup(t, { intercept(c, data) { if (pending && c.path.startsWith('/pessoas/')) return new Promise((r) => { resolve = () => r(json(data.person)); }); } });
    await h.person(); await h.room(); pending = true; await h.person(); h.w.fazerLogout(); await flush(); resolve(); await flush();
    for (const name of ['st-person-summary', 'st-person-rows', 'st-local-rows']) assert.equal(h.id(name).textContent, '');
    assert.equal(h.id('st-permission-form').hidden, true); assert.equal(h.id('st-person-search').elements.pessoa.value, '');
});
test('texto recebido é exibido como texto, sem executar HTML', async (t) => {
    const attack = '<img src=x onerror="window.hacked=true">';
    const h = await setup(t, { change(data) { data.person.pessoa.nome = attack; data.person.permissoes.forEach((p) => { p.pessoa.nome = attack; }); data.person.permissoes[0].local.endereco = attack; } });
    await h.person(); assert.ok(h.id('st-person-summary').textContent.includes(attack));
    assert.equal(h.id('st-person-summary').querySelector('img'), null); assert.equal(h.id('st-person-rows').querySelector('img'), null);
    assert.equal(h.w.hacked, undefined);
});
test('falha de rede e JSON inválido têm mensagem visível', async (t) => {
    let mode = 'network';
    const h = await setup(t, { intercept(c) { if (c.path.startsWith('/pessoas/')) { if (mode === 'network') throw new Error('Falha de rede simulada'); return new Response('HTML inválido'); } } });
    await h.person(); assert.match(h.id('st-person-message').textContent, /Falha de rede/);
    mode = 'json'; await h.person(); assert.match(h.id('st-person-message').textContent, /resposta inválida/);
});
test('gravação pendente bloqueia submissão duplicada e conflito 409 mantém o editor', async (t) => {
    let resolve;
    const h = await setup(t, { intercept(c) { if (c.method === 'PUT') return new Promise((r) => { resolve = () => r(json({ message: 'Conflito de teste' }, 409)); }); } });
    await h.person(); await h.edit(h.data.ids.third); await h.submit('st-permission-form'); await h.submit('st-permission-form');
    assert.equal(h.writes().length, 1); assert.equal(h.id('st-permission-save').disabled, true);
    resolve(); await flush(); assert.equal(h.id('st-permission-save').disabled, false); assert.equal(h.id('st-permission-form').hidden, false);
    assert.match(h.id('st-editor-message').textContent, /Conflito/);
});
