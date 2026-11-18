/* Gestão de permissões limitada a Pessoas/Locais. Reutiliza o JWT humano atual. */
(() => {
    'use strict';
    const id = (name) => document.getElementById(name);
    const personForm = id('st-person-search'), localForm = id('st-local-search');
    if (!personForm || !localForm) return;
    const pageSize = 25, slots = {}, quiet = Symbol('resposta descartada');
    let epoch = 0, sessionToken = null, person = null, personPage = 1;
    let room = null, roomPage = 1, roomFilter = '', editor = null, writing = null;
    const token = () => typeof jwtToken === 'string' ? jwtToken : null;
    const types = { users: 'Usuário comum', visitante: 'Visitante', roots: 'Root' };
    const states = { ativo: 'Ativa', inativo: 'Inativa', revogado: 'Revogada', sem_credencial: 'Sem credencial cadastrada',
        agendado: 'Agendada', expirado: 'Expirada', vigente: 'Vigente', agendada: 'Agendada', expirada: 'Expirada', revogada: 'Revogada' };
    const date = (value, empty = 'Sem limite') => value ? new Date(value).toLocaleString('pt-BR') : empty;
    const credentialPeriod = (p) => p.inicio_credencial || p.expiracao_credencial
        ? `${date(p.inicio_credencial)} até ${date(p.expiracao_credencial)}` : 'Sem prazo global';
    const localDate = (value) => {
        if (!value) return '';
        const instant = new Date(value);
        return new Date(instant.getTime() - instant.getTimezoneOffset() * 60000).toISOString().slice(0, -1);
    };
    function message(target, text = '', state = '') {
        id(target).textContent = text; id(target).dataset.state = state;
    }
    function cancel(slot) { slots[slot]?.controller.abort(); delete slots[slot]; }
    function reset() {
        epoch++; Object.keys(slots).forEach(cancel);
        person = room = editor = writing = null;
        personPage = roomPage = 1; roomFilter = '';
        personForm.reset(); localForm.reset(); id('st-local-add').reset(); id('st-permission-form').reset();
        for (const name of ['st-person-detail', 'st-local-detail', 'st-permission-form']) id(name).hidden = true;
        for (const name of ['st-person-summary', 'st-person-rows', 'st-local-rows', 'st-local-name', 'st-person-page', 'st-local-page', 'st-editor-state']) id(name).replaceChildren();
        id('st-permission-local').replaceChildren(new Option('Selecione uma sala…', ''));
        for (const name of ['st-person-message', 'st-local-message', 'st-editor-message']) message(name);
        sessionToken = token(); syncButtons();
    }
    function begin(slot) {
        if (token() !== sessionToken) reset();
        cancel(slot);
        const context = { slot, epoch, token: token(), controller: new AbortController() };
        slots[slot] = context; return context;
    }
    function current(context) {
        return context.epoch === epoch && context.token === token() && slots[context.slot] === context;
    }
    async function api(path, context, options = {}) {
        if (!current(context)) throw quiet;
        if (!context.token) throw new Error('Entre com uma conta Root para administrar permissões.');
        const response = await fetch(path, { ...options, signal: context.controller.signal,
            headers: { Authorization: `Bearer ${context.token}`, ...(options.body ? { 'Content-Type': 'application/json' } : {}) } });
        if (!current(context)) throw quiet;
        if (response.status === 401 || response.status === 403) {
            const text = response.status === 401 ? 'Sessão inválida ou expirada. Entre novamente.' : 'Acesso negado: somente Root administra permissões.';
            reset(); message('st-person-message', text, 'error'); message('st-local-message', text, 'error'); throw quiet;
        }
        let data;
        try { data = await response.json(); }
        catch { throw new Error('A API retornou uma resposta inválida. Tente novamente.'); }
        if (!current(context)) throw quiet;
        if (!response.ok) throw new Error(data.message || data.error || `Não foi possível concluir a operação (HTTP ${response.status}).`);
        return data;
    }
    function failure(error, context, target) {
        if (error !== quiet && error.name !== 'AbortError' && current(context)) message(target, error.message || 'Falha ao conectar com a API.', 'error');
    }
    function number(value) { const n = Number(value); if (!Number.isSafeInteger(n) || n < 1) throw new Error('Informe um ID inteiro positivo.'); return n; }
    function cell(row, value) { const td = row.insertCell(); td.textContent = value ?? '—'; return td; }
    function button(parent, label, action, write = false, disabled = false) {
        const b = document.createElement('button'); b.type = 'button'; b.textContent = label;
        if (write) { b.dataset.stPermissionWrite = ''; b.dataset.unavailable = String(disabled); }
        b.disabled = disabled || (write && !!writing); b.addEventListener('click', action); parent.append(b); return b;
    }
    function syncButtons() {
        document.querySelectorAll('.st-permissions [data-st-permission-write]').forEach((b) => { b.disabled = !!writing || b.dataset.unavailable === 'true'; });
    }
    function pager(kind, data) {
        const pages = Math.max(1, Math.ceil(data.total / data.limite));
        id(`st-${kind}-page`).textContent = `Página ${data.pagina} de ${pages} · ${data.total} permissão(ões)`;
        id(`st-${kind}-prev`).disabled = data.pagina <= 1;
        id(`st-${kind}-next`).disabled = data.pagina * data.limite >= data.total;
    }
    function summary(p) {
        const list = id('st-person-summary'); list.replaceChildren();
        for (const [label, value] of [['Pessoa', `${p.nome} · ID ${p.id}`], ['Tipo', types[p.tipo_user] || p.tipo_user],
            ['RFID', p.credencial_rfid ?? 'Sem vínculo'], ['Credencial', states[p.status_credencial] || p.status_credencial], ['Validade global', credentialPeriod(p)]]) {
            const group = document.createElement('div'), dt = document.createElement('dt'), dd = document.createElement('dd');
            dt.textContent = label; dd.textContent = value; group.append(dt, dd); list.append(group);
        }
    }
    function empty(body, columns, text) { const td = cell(body.insertRow(), text); td.colSpan = columns; }
    async function loadPerson(personId, page = 1, selectedRoom = null) {
        const context = begin('person'); cancel('editor');
        person = editor = null; id('st-person-detail').hidden = id('st-permission-form').hidden = true;
        message('st-editor-message'); message('st-person-message', 'Consultando pessoa…');
        try {
            personId = number(personId); personForm.elements.pessoa.value = personId;
            const [data, places] = await Promise.all([
                api(`/pessoas/${personId}/permissoes?pagina=${page}&limite=${pageSize}`, context), api('/listar_locais', context),
            ]);
            if (!current(context)) return;
            person = data.pessoa; personPage = data.pagina; summary(person);
            const select = id('st-permission-local'); select.replaceChildren(new Option('Selecione uma sala…', ''));
            for (const place of places.locais) select.add(new Option(`${place.endereco} · ID ${place.id}`, place.id));
            const body = id('st-person-rows'); body.replaceChildren();
            for (const permission of data.permissoes) {
                const row = body.insertRow(); cell(row, `${permission.local.endereco} · ID ${permission.local.id}`);
                cell(row, date(permission.inicio)); cell(row, date(permission.expiracao)); cell(row, states[permission.situacao]);
                cell(row, permission.acesso_efetivo ? 'Permitido' : 'Negado'); const actions = row.insertCell();
                button(actions, 'Editar', () => { select.value = String(permission.local.id); loadEditor(permission.local.id, permission); });
                button(actions, 'Revogar', () => revoke(permission), true, permission.revogada);
            }
            if (!data.permissoes.length) empty(body, 6, 'Nenhuma permissão nesta página. Selecione uma sala abaixo para conceder acesso.');
            pager('person', data); id('st-person-detail').hidden = false; message('st-person-message');
            if (selectedRoom !== null) { select.value = String(selectedRoom); await loadEditor(selectedRoom); }
        } catch (error) { failure(error, context, 'st-person-message'); }
    }
    async function loadEditor(localId, knownPermission) {
        const context = begin('editor'); editor = null; id('st-permission-form').hidden = true;
        message('st-editor-message', 'Consultando autorização da sala…');
        try {
            if (!person) return;
            const personId = person.id; localId = number(localId);
            let permission = knownPermission ?? null;
            // A consulta paginada impede sobrescrever às cegas um vínculo já existente fora da página atual.
            if (knownPermission === undefined) {
                for (let page = 1; ; page++) {
                    const data = await api(`/pessoas/${personId}/permissoes?pagina=${page}&limite=100`, context);
                    permission = data.permissoes.find((p) => p.local.id === localId) ?? null;
                    if (permission || page * data.limite >= data.total || data.permissoes.some((p) => p.local.id > localId)) break;
                }
            }
            if (!current(context)) return;
            editor = { personId, localId, permission };
            const form = id('st-permission-form'); form.reset();
            for (const name of ['inicio', 'expiracao']) form.elements[name].value = localDate(permission?.[name]);
            editor.original = { inicio: form.elements.inicio.value, expiracao: form.elements.expiracao.value };
            id('st-permission-save').textContent = permission ? 'Salvar vigência' : 'Conceder autorização';
            id('st-permission-reactivate').hidden = !permission?.revogada;
            id('st-editor-state').textContent = permission
                ? `Permissão ${states[permission.situacao].toLowerCase()}. Salvar vigência preserva o estado de revogação.`
                : 'Nenhuma permissão cadastrada para esta pessoa nesta sala.';
            id('st-permission-timezone').textContent = `Horários no fuso deste navegador: ${Intl.DateTimeFormat().resolvedOptions().timeZone}.`;
            form.hidden = false; message('st-editor-message'); syncButtons();
        } catch (error) { failure(error, context, 'st-editor-message'); }
    }
    async function loadRoom(localId, page = 1, filter = roomFilter) {
        const context = begin('room'); room = null; id('st-local-detail').hidden = true;
        message('st-local-message', 'Consultando autorizações…');
        try {
            localId = number(localId); localForm.elements.local.value = localId;
            const query = new URLSearchParams({ pagina: page, limite: pageSize });
            if (filter) query.set('situacao', filter);
            const data = await api(`/locais/${localId}/autorizacoes?${query}`, context);
            if (!current(context)) return;
            room = data.local; roomPage = data.pagina; roomFilter = filter; localForm.elements.situacao.value = filter;
            id('st-local-name').textContent = `${room.endereco} · ID ${room.id}`;
            const body = id('st-local-rows'); body.replaceChildren();
            for (const permission of data.autorizacoes) {
                const row = body.insertRow(), p = permission.pessoa;
                cell(row, `${p.nome} · ID ${p.id}`); cell(row, types[p.tipo_user] || p.tipo_user); cell(row, p.credencial_rfid);
                cell(row, `${states[p.status_credencial] || p.status_credencial} · ${credentialPeriod(p)}`);
                cell(row, date(permission.inicio)); cell(row, date(permission.expiracao)); cell(row, states[permission.situacao]);
                cell(row, permission.acesso_efetivo ? 'Permitido' : 'Negado'); const actions = row.insertCell();
                button(actions, 'Gerenciar', () => openPerson(p.id, permission.local.id));
                button(actions, 'Revogar', () => revoke(permission), true, permission.revogada);
            }
            if (!data.autorizacoes.length) empty(body, 9, 'Nenhuma pessoa encontrada para este filtro.');
            pager('local', data); id('st-local-detail').hidden = false; message('st-local-message');
        } catch (error) { failure(error, context, 'st-local-message'); }
    }
    async function write(personId, localId, body, revokeOnly = false) {
        if (writing) return;
        const context = begin('write'); writing = context; syncButtons();
        message('st-editor-message'); message('st-person-message'); message('st-local-message');
        try {
            await api(`/pessoas/${personId}/permissoes/${localId}${revokeOnly ? '/revogar' : ''}`, context,
                { method: revokeOnly ? 'POST' : 'PUT', ...(revokeOnly ? {} : { body: JSON.stringify(body) }) });
            if (!current(context)) return;
            const reload = [];
            if (person?.id === personId) reload.push(loadPerson(personId, personPage, localId));
            if (room?.id === localId) reload.push(loadRoom(localId, roomPage, roomFilter));
            await Promise.all(reload);
            if (!current(context)) return;
            const text = revokeOnly ? 'Autorização desta sala revogada. As demais permissões foram preservadas.' : 'Autorização salva. A liberação depende também da validade da credencial.';
            if (person?.id === personId) message('st-person-message', text, 'success');
            if (room?.id === localId) message('st-local-message', text, 'success');
        } catch (error) {
            if (person?.id === personId) failure(error, context, 'st-editor-message');
            if (room?.id === localId) failure(error, context, 'st-local-message');
        } finally { if (writing === context) { writing = null; syncButtons(); } }
    }
    function revoke(permission) {
        if (writing || !confirm(`Revogar o acesso de ${permission.pessoa.nome} à sala ${permission.local.endereco}?`)) return;
        write(permission.pessoa.id, permission.local.id, null, true);
    }
    function openPerson(personId, localId = null) {
        window.mudarAba('usuarios'); loadPerson(personId, 1, localId);
        id('st-person-permissions').scrollIntoView?.({ block: 'start', behavior: 'smooth' });
    }
    personForm.addEventListener('submit', (event) => { event.preventDefault(); loadPerson(personForm.elements.pessoa.value); });
    localForm.addEventListener('submit', (event) => { event.preventDefault(); loadRoom(localForm.elements.local.value, 1, localForm.elements.situacao.value); });
    id('st-local-add').addEventListener('submit', (event) => { event.preventDefault(); if (room) openPerson(id('st-local-add').elements.pessoa.value, room.id); });
    id('st-permission-local').addEventListener('change', (event) => {
        if (event.target.value) loadEditor(event.target.value);
        else { cancel('editor'); editor = null; id('st-permission-form').hidden = true; message('st-editor-message'); }
    });
    id('st-person-prev').addEventListener('click', () => person && loadPerson(person.id, personPage - 1));
    id('st-person-next').addEventListener('click', () => person && loadPerson(person.id, personPage + 1));
    id('st-local-prev').addEventListener('click', () => room && loadRoom(room.id, roomPage - 1, roomFilter));
    id('st-local-next').addEventListener('click', () => room && loadRoom(room.id, roomPage + 1, roomFilter));
    id('st-permission-form').addEventListener('submit', (event) => {
        event.preventDefault(); if (!editor || writing) return;
        try {
            const form = event.target, body = {}, values = {};
            for (const name of ['inicio', 'expiracao']) {
                values[name] = form.elements[name].value ? new Date(form.elements[name].value).toISOString() : null;
                if (!editor.permission || form.elements[name].value !== editor.original[name]) body[name] = values[name];
            }
            if (values.inicio && values.expiracao && values.inicio >= values.expiracao) throw new Error('O início deve ser anterior à expiração.');
            if (!editor.permission) body.revogada = false;
            if (!Object.keys(body).length) { message('st-editor-message', 'Nenhuma alteração na vigência.'); return; }
            write(editor.personId, editor.localId, body);
        } catch (error) { message('st-editor-message', error.message, 'error'); }
    });
    id('st-permission-reactivate').addEventListener('click', () => {
        if (!editor?.permission?.revogada || writing) return;
        if (confirm('Reativar esta autorização mantendo a vigência salva? Alterações nas datas devem ser salvas antes.')) write(editor.personId, editor.localId, { revogada: false });
    });
    for (const [table, attribute, action] of [['tabela-usuarios', 'data-st-person-permissions', openPerson], ['tabela-locais', 'data-st-room-permissions', (value) => {
        loadRoom(value, 1, ''); id('st-local-permissions').scrollIntoView?.({ block: 'start', behavior: 'smooth' });
    }]]) id(table).addEventListener('click', (event) => {
        const target = event.target.closest(`button[${attribute}]`); if (target) action(target.getAttribute(attribute));
    });
    // Observa a tela existente; não altera login, logout ou a emissão de JWT.
    new MutationObserver(() => {
        if (id('tela-login').style.display !== 'none' || token() !== sessionToken) reset();
    }).observe(id('tela-login'), { attributes: true, attributeFilter: ['style'] });
    reset();
})();
