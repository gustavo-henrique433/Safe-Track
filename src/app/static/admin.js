/* Integração das novas abas. O JWT continua somente em memória. */
(() => {
    'use strict';
    const byId = (id) => document.getElementById(id);
    const formField = (form, name) => form.elements.namedItem(name);
    const state = { root: false, token: null, epoch: 0, visitorPage: 1, accessPage: 1, activityPage: 1,
        visitorFilters: {}, accessFilters: {}, activityFilters: {}, activityLoaded: false, edit: null };
    const requests = new Set();
    let visitorRequest = 0, accessRequest = 0, activityRequest = 0, dialogRequest = 0, referenceRequest = 0;
    let initialVisitor = null, previousFocus = null;
    const dialog = byId('st-visitante-dialogo');
    const visitorForm = byId('st-visitante-formulario');
    const localZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const number = new Intl.NumberFormat('pt-BR');
    const localTime = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
    const utcTime = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short', timeZone: 'UTC' });

    function node(tag, classes = '', text = null) {
        const item = document.createElement(tag);
        if (classes) item.className = classes;
        if (text !== null) item.textContent = String(text);
        return item;
    }

    function message(id, text = '', kind = '') {
        byId(id).textContent = text;
        byId(id).dataset.state = kind;
    }

    function ignored(error) { return error.name === 'AbortError' || !state.root; }
    function cancelled() { return new DOMException('Consulta cancelada.', 'AbortError'); }

    async function request(path, options = {}, binary = false) {
        if (!state.root || !state.token) throw cancelled();
        const epoch = state.epoch;
        const controller = new AbortController();
        requests.add(controller);
        try {
            let response;
            try {
                response = await fetch(path, { ...options, signal: controller.signal,
                    headers: { ...options.headers, Authorization: `Bearer ${state.token}` } });
            } catch (error) {
                if (error.name === 'AbortError') throw error;
                throw new Error('Falha na conexão. Tente novamente.');
            }
            if (epoch !== state.epoch) throw cancelled();
            if (response.status === 401) {
                window.fazerLogout();
                window.alert('Sua sessão expirou. Entre novamente para continuar.');
                throw cancelled();
            }
            if (binary && response.ok) {
                const blob = await response.blob();
                if (epoch !== state.epoch) throw cancelled();
                return blob;
            }
            let data;
            try { data = await response.json(); }
            catch (_) { throw new Error('Não foi possível ler a resposta. Tente novamente.'); }
            if (epoch !== state.epoch) throw cancelled();
            if (!response.ok) throw new Error(data.message || data.error || 'Não foi possível realizar a operação.');
            return data;
        } finally { requests.delete(controller); }
    }

    function jsonOptions(method, data) {
        return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) };
    }

    function url(path, filters) {
        const params = new URLSearchParams(filters);
        return params.size ? `${path}?${params}` : path;
    }

    function filtersFrom(form) {
        if (!form.reportValidity()) return null;
        return Object.fromEntries([...new FormData(form)].filter(([, value]) => value !== ''));
    }

    function time(value, utc = true) {
        return value ? (utc ? utcTime : localTime).format(new Date(value)) : 'Não registrado';
    }

    function badge(value) {
        const labels = { ativo: 'Ativo', agendado: 'Agendado', expirado: 'Expirado', revogado: 'Revogado' };
        const positive = ['ativo', 'Liberado', 'sucesso'].includes(value);
        const negative = ['expirado', 'revogado', 'Negado', 'falha'].includes(value);
        return node('span', `st-badge ${positive ? 'bg-emerald-500/20 text-emerald-300' : negative ?
            'bg-red-500/20 text-red-300' : 'bg-gray-700 text-gray-300'}`, labels[value] || value || 'Indefinido');
    }

    function emptyTable(id, columns, text) {
        const cell = node('td', 'text-gray-400', text);
        cell.colSpan = columns;
        const row = node('tr');
        row.append(cell);
        byId(id).replaceChildren(row);
    }

    function tableRow(body, cells) {
        const row = node('tr');
        for (const value of cells) {
            const cell = node('td');
            cell.append(value instanceof Node ? value : document.createTextNode(String(value ?? 'Não registrado')));
            row.append(cell);
        }
        body.append(row);
    }

    function action(label, callback, classes = 'text-indigo-300') {
        const button = node('button', `st-button ${classes}`, label);
        button.type = 'button';
        button.addEventListener('click', callback);
        return button;
    }

    function pager(prefix, page, total, size, busy = false) {
        byId(`${prefix}-anterior`).disabled = busy || page <= 1;
        byId(`${prefix}-proxima`).disabled = busy || page * size >= total;
        byId(`${prefix}-pagina`).textContent = `${number.format(total)} registro(s) · Página ${page} de ${Math.max(1, Math.ceil(total / size))}`;
    }

    function disablePager(prefix) {
        byId(`${prefix}-anterior`).disabled = byId(`${prefix}-proxima`).disabled = true;
    }

    function currentLocalIds() {
        return [...byId('st-visitante-locais').querySelectorAll('input:checked')].map((input) => Number(input.value));
    }

    function localInput(value) {
        const date = new Date(value);
        return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 19);
    }

    async function visitorReferences(selected = currentLocalIds()) {
        const sequence = ++referenceRequest;
        byId('st-visitante-salvar').disabled = true;
        byId('st-visitante-referencias').disabled = true;
        try {
            const [places, tags] = await Promise.all([request('/listar_locais'), request('/vizualizar_todos_rfid')]);
            if (sequence !== referenceRequest || !dialog.open) return;
            const checks = places.locais.map((place) => {
                const label = node('label', 'flex items-start gap-2 text-sm text-gray-300');
                const input = node('input', 'mt-1 accent-indigo-500');
                input.type = 'checkbox';
                input.value = String(place.id);
                input.checked = selected.includes(place.id);
                label.append(input, document.createTextNode(`${place.endereco} (#${place.id})`));
                return label;
            });
            byId('st-visitante-locais').replaceChildren(...checks);
            if (!checks.length) byId('st-visitante-locais').append(node('p', 'text-sm text-amber-300', 'Cadastre um local no módulo Salas e Locais antes de salvar.'));
            const uids = tags.objetos.filter((tag) => tag.tipo === 'livre').map((tag) => String(tag.uid));
            if (state.edit?.credencial_rfid != null) uids.push(String(state.edit.credencial_rfid));
            byId('st-visitante-tags').replaceChildren(...[...new Set(uids)].map((uid) => {
                const option = node('option'); option.value = uid; return option;
            }));
            byId('st-visitante-salvar').disabled = checks.length === 0;
        } finally {
            if (sequence === referenceRequest) byId('st-visitante-referencias').disabled = false;
        }
    }

    async function openVisitor(id = null) {
        if (!state.root) return;
        const sequence = ++dialogRequest;
        previousFocus = document.activeElement;
        visitorForm.reset();
        initialVisitor = null;
        state.edit = null;
        message('st-visitante-formulario-mensagem', 'Carregando tags e locais…');
        byId('st-visitante-salvar').disabled = true;
        byId('st-visitante-referencias').disabled = true;
        byId('st-visitante-dialogo-titulo').textContent = id ? 'Editar permissões do visitante' : 'Novo visitante';
        byId('st-visitante-salvar').textContent = id ? 'Salvar permissões' : 'Cadastrar visitante';
        byId('st-visitante-senha-campo').hidden = Boolean(id);
        byId('st-visitante-identificacao-nota').hidden = !id;
        for (const name of ['nome', 'email', 'senha']) formField(visitorForm, name).disabled = Boolean(id);
        formField(visitorForm, 'senha').required = !id;
        formField(visitorForm, 'credencial_rfid').required = !id;
        dialog.showModal();
        try {
            if (id) {
                const { visitante } = await request(`/visitantes/${id}`);
                if (sequence !== dialogRequest || !dialog.open) return;
                state.edit = visitante;
                for (const name of ['nome', 'email', 'credencial_rfid']) formField(visitorForm, name).value = visitante[name] ?? '';
                for (const name of ['inicio', 'expiracao']) formField(visitorForm, name).value = localInput(visitante[name]);
                initialVisitor = Object.fromEntries(['credencial_rfid', 'inicio', 'expiracao'].map((name) => [name, formField(visitorForm, name).value]));
                initialVisitor.locais = visitante.locais.map((place) => place.id);
            }
            await visitorReferences(initialVisitor?.locais || []);
            if (sequence === dialogRequest && dialog.open) message('st-visitante-formulario-mensagem');
        } catch (error) {
            if (!ignored(error) && sequence === dialogRequest) message('st-visitante-formulario-mensagem', error.message, 'error');
        }
    }

    async function saveVisitor(event) {
        event.preventDefault();
        if (!state.root || byId('st-visitante-salvar').disabled) return;
        if (!visitorForm.reportValidity()) return;
        const locals = currentLocalIds();
        const start = new Date(formField(visitorForm, 'inicio').value);
        const end = new Date(formField(visitorForm, 'expiracao').value);
        if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || start >= end) {
            message('st-visitante-formulario-mensagem', 'O início deve ser anterior à expiração.', 'error'); return;
        }
        if (!locals.length || locals.length > 100) {
            message('st-visitante-formulario-mensagem', 'Selecione de 1 a 100 locais autorizados.', 'error'); return;
        }
        const editing = state.edit;
        const payload = {};
        for (const name of ['credencial_rfid', 'inicio', 'expiracao']) {
            if (!editing || formField(visitorForm, name).value !== initialVisitor[name]) {
                payload[name] = name === 'inicio' ? start.toISOString() : name === 'expiracao' ? end.toISOString() : formField(visitorForm, name).value;
            }
        }
        if (!editing || JSON.stringify([...locals].sort((a, b) => a - b)) !== JSON.stringify([...initialVisitor.locais].sort((a, b) => a - b))) payload.locais = locals;
        if (!editing) for (const name of ['nome', 'email', 'senha']) payload[name] = formField(visitorForm, name).value;
        if (!Object.keys(payload).length) { message('st-visitante-formulario-mensagem', 'Nenhuma alteração para salvar.'); return; }
        byId('st-visitante-salvar').disabled = true;
        message('st-visitante-formulario-mensagem', 'Salvando…');
        try {
            await request(editing ? `/visitantes/${editing.id}` : '/visitantes', jsonOptions(editing ? 'PUT' : 'POST', payload));
            formField(visitorForm, 'senha').value = '';
            dialog.close();
            await loadVisitors(1);
            if (state.root) message('st-visitantes-mensagem', editing ? 'Permissões atualizadas. Uma credencial revogada permanece revogada.' : 'Visitante cadastrado com sucesso.', 'success');
        } catch (error) { if (!ignored(error)) message('st-visitante-formulario-mensagem', error.message, 'error'); }
        finally { byId('st-visitante-salvar').disabled = false; }
    }

    async function revokeVisitor(visitor, button) {
        if (!window.confirm(`Revogar a credencial de ${visitor.nome}? Ela deixará de autorizar novos acessos e não será reativada ao editar o período.`)) return;
        button.disabled = true;
        try {
            await request(`/visitantes/${visitor.id}/revogar`, { method: 'POST' });
            await loadVisitors(state.visitorPage);
            if (state.root) message('st-visitantes-mensagem', 'Credencial revogada. O histórico foi mantido.', 'success');
        } catch (error) { if (!ignored(error)) message('st-visitantes-mensagem', error.message, 'error'); }
        finally { button.disabled = false; }
    }

    async function loadVisitors(page = 1, filters = state.visitorFilters) {
        const sequence = ++visitorRequest;
        disablePager('st-visitantes');
        message('st-visitantes-mensagem', 'Carregando visitantes…');
        emptyTable('st-visitantes-corpo', 6, 'Carregando…');
        try {
            const data = await request(url('/visitantes', { ...filters, pagina: page, limite: filters.limite || 25 }));
            if (sequence !== visitorRequest) return;
            if (data.total && page > Math.ceil(data.total / data.limite)) return loadVisitors(Math.ceil(data.total / data.limite), filters);
            state.visitorPage = page; state.visitorFilters = { ...filters };
            const body = byId('st-visitantes-corpo'); body.replaceChildren();
            for (const visitor of data.visitantes) {
                const identity = node('div', 'space-y-1');
                identity.append(node('p', 'font-bold text-white', `${visitor.nome} (#${visitor.id})`), node('p', 'text-xs text-gray-400', visitor.email));
                const validity = node('div', 'text-xs space-y-2');
                validity.append(node('p', '', `Início: ${time(visitor.inicio, false)}`), node('p', '', `Expiração: ${time(visitor.expiracao, false)}`));
                const actions = node('div', 'flex flex-wrap gap-1');
                actions.append(action('Permissões', () => openVisitor(visitor.id)), action('Histórico', () => {
                    byId('st-acessos-filtros').reset();
                    formField(byId('st-acessos-filtros'), 'visitante').value = visitor.id;
                    window.mudarAba('relatorios');
                }));
                const revoke = action('Revogar', (event) => revokeVisitor(visitor, event.currentTarget), 'text-red-300');
                revoke.disabled = visitor.status === 'revogado'; actions.append(revoke);
                tableRow(body, [identity, visitor.credencial_rfid, validity, visitor.locais.map((place) => `${place.endereco} (#${place.id})`).join('; ') || 'Nenhum local', badge(visitor.status), actions]);
            }
            if (!data.visitantes.length) emptyTable('st-visitantes-corpo', 6, 'Nenhum visitante encontrado com os filtros aplicados.');
            pager('st-visitantes', data.pagina, data.total, data.limite);
            message('st-visitantes-mensagem');
        } catch (error) {
            if (!ignored(error) && sequence === visitorRequest) {
                emptyTable('st-visitantes-corpo', 6, 'Não foi possível carregar os visitantes.');
                message('st-visitantes-mensagem', error.message, 'error');
            }
        }
    }

    function metrics(id, data, labels) {
        byId(id).replaceChildren(...Object.entries(labels).map(([key, label]) => {
            const item = node('div', 'st-metric');
            item.append(node('dt', '', label), node('dd', '', data[key] == null ? 'Indisponível' : number.format(data[key])));
            return item;
        }));
    }

    function svgNode(tag, attributes = {}, text = null) {
        const item = document.createElementNS('http://www.w3.org/2000/svg', tag);
        for (const [name, value] of Object.entries(attributes)) item.setAttribute(name, String(value));
        if (text !== null) item.textContent = text;
        return item;
    }

    function dailyChart(series) {
        const rows = series.dias;
        const host = byId('st-grafico-diario'); host.replaceChildren();
        const body = byId('st-diaria-corpo'); body.replaceChildren();
        byId('st-grafico-limite').textContent = series.ha_dias_anteriores ?
            `Exibindo os últimos ${series.limite_dias_com_registros} dias com eventos. Há dias anteriores no recorte; os totais incluem todos os registros.` :
            'Dias em UTC, somente quando há eventos registrados.';
        if (!rows.length) {
            host.append(dashboardEmptyState('fa-chart-line', 'Nenhuma tentativa registrada no recorte.'));
            emptyTable('st-diaria-corpo', 5, 'Nenhum dia com registros.'); return;
        }
        for (const row of rows) tableRow(body, [row.data, row.autorizados, row.negados, row.indefinidos, row.total]);
        const svg = svgNode('svg', { viewBox: '0 0 720 250', class: 'st-chart', role: 'img', 'aria-labelledby': 'st-diario-titulo-svg' });
        svg.append(svgNode('title', { id: 'st-diario-titulo-svg' }, 'Evolução diária: autorizados, negados e indefinidos. Os valores completos estão na tabela por dia.'));
        const peak = Math.max(1, ...rows.flatMap((row) => [row.autorizados, row.negados, row.indefinidos]));
        const step = Math.max(1, Math.ceil(peak / 4));
        const ceiling = Math.ceil(peak / step) * step;
        const x = (index) => rows.length === 1 ? 380 : 55 + index / (rows.length - 1) * 625;
        const y = (value) => 205 - value / ceiling * 180;
        for (let value = 0; value <= ceiling; value += step) {
            svg.append(svgNode('line', { x1: 55, x2: 680, y1: y(value), y2: y(value), stroke: '#374151' }));
            svg.append(svgNode('text', { x: 45, y: y(value) + 4, fill: '#9ca3af', 'text-anchor': 'end', 'font-size': 12 }, number.format(value)));
        }
        for (const index of new Set([0, Math.floor((rows.length - 1) / 2), rows.length - 1])) {
            svg.append(svgNode('text', { x: x(index), y: 235, fill: '#9ca3af', 'text-anchor': 'middle', 'font-size': 12 }, rows[index].data.split('-').reverse().join('/')));
        }
        for (const [key, color, label] of [['autorizados', '#34d399', 'Autorizados'], ['negados', '#f87171', 'Negados'], ['indefinidos', '#d1d5db', 'Indefinidos']]) {
            const line = svgNode('polyline', { points: rows.map((row, index) => `${x(index)},${y(row[key])}`).join(' '), fill: 'none', stroke: color, 'stroke-width': 2.5 });
            line.append(svgNode('title', {}, label)); svg.append(line);
            if (rows.length === 1) svg.append(svgNode('circle', { cx: x(0), cy: y(rows[0][key]), r: 4, fill: color }));
        }
        host.append(svg);
    }

    function dashboardEmptyState(icon, text) {
        const empty = node('div', 'st-dashboard-empty');
        const symbol = node('i', `fa-solid ${icon}`);
        symbol.setAttribute('aria-hidden', 'true');
        empty.append(symbol, node('p', '', text));
        return empty;
    }

    function decorateDashboardMetrics() {
        const groups = [
            ['st-metricas-acessos', ['total', 'autorizados', 'negados', 'indefinidos'], ['fa-layer-group', 'fa-circle-check', 'fa-circle-xmark', 'fa-circle-question']],
            ['st-metricas-cadastros', ['objetos', 'tags', 'locais'], ['fa-boxes-stacked', 'fa-tags', 'fa-map-location-dot']],
        ];
        for (const [id, keys, icons] of groups) {
            [...byId(id).children].forEach((card, index) => {
                card.dataset.stDashboardMetric = keys[index];
                const icon = node('i', `fa-solid ${icons[index]} st-dashboard-metric-icon`);
                icon.setAttribute('aria-hidden', 'true');
                card.prepend(icon);
            });
        }
    }

    function setDashboardRankingExpanded(expanded) {
        const items = [...byId('st-ranking').querySelectorAll('[data-st-ranking-item]')];
        const canExpand = items.length > 3;
        const showAll = canExpand && expanded;
        items.forEach((item, index) => { item.hidden = !showAll && index >= 3; });
        const control = byId('st-ranking-expandir');
        control.hidden = !canExpand;
        control.disabled = !canExpand;
        control.setAttribute('aria-expanded', String(showAll));
        control.textContent = showAll ? 'Mostrar menos' : 'Ver ranking disponível (até 10 salas)';
        byId('st-ranking-resumo').textContent = showAll ? 'Ranking disponível de acessos autorizados no recorte.' : 'Top 3 de acessos autorizados no recorte.';
    }

    byId('st-ranking-expandir').addEventListener('click', () => {
        setDashboardRankingExpanded(byId('st-ranking-expandir').getAttribute('aria-expanded') !== 'true');
    });

    function renderSummary(data) {
        for (const [id, value] of [['st-metrica-visitantes-ativos', data.visitantes.ativos],
            ['st-patrimonio-total', data.cadastros.objetos], ['st-locais-total', data.cadastros.locais]]) {
            byId(id).textContent = value == null ? 'Indisponível' : number.format(value);
        }
        metrics('st-metricas-cadastros', data.cadastros, { objetos: 'Patrimônios cadastrados', tags_rfid: 'Tags RFID cadastradas', locais: 'Locais cadastrados' });
        metrics('st-metricas-visitantes', data.visitantes, { cadastrados: 'Cadastrados', ativos: 'Ativos', agendados: 'Agendados', expirados: 'Expirados', revogados: 'Revogados' });
        metrics('st-metricas-acessos', data.acessos, { total: 'Total de tentativas', autorizados: 'Acessos autorizados', negados: 'Acessos negados', indefinidos: 'Acessos indefinidos' });
        decorateDashboardMetrics();
        dailyChart(data.evolucao_diaria);
        const ranking = byId('st-ranking'); ranking.replaceChildren();
        const maximum = Math.max(1, ...data.salas_mais_acessadas.map((place) => place.autorizados));
        for (const place of data.salas_mais_acessadas) {
            const item = node('li');
            item.setAttribute('data-st-ranking-item', '');
            const position = node('span', 'st-dashboard-rank-position', `${ranking.children.length + 1}º`);
            const label = node('div', 'st-dashboard-rank-label flex justify-between gap-3 text-sm');
            label.append(node('span', 'break-words', place.local ?? `Local #${place.id_local} sem cadastro disponível`), node('span', 'font-bold text-emerald-300', number.format(place.autorizados)));
            const track = node('div', 'st-rank-track'); const fill = node('div', 'st-rank-fill');
            fill.style.width = `${place.autorizados / maximum * 100}%`; track.append(fill); item.append(position, label, track); ranking.append(item);
        }
        if (!data.salas_mais_acessadas.length) {
            const empty = node('li', 'st-dashboard-ranking-empty');
            empty.append(dashboardEmptyState('fa-door-open', 'Nenhum acesso registrado no período'));
            ranking.append(empty);
        }
        setDashboardRankingExpanded(false);
        const locations = byId('st-locais-corpo'); locations.replaceChildren();
        for (const place of data.salas_mais_acessadas) tableRow(locations, [
            place.local ?? `Local #${place.id_local} sem cadastro disponível`, place.autorizados]);
        if (!data.salas_mais_acessadas.length) emptyTable('st-locais-corpo', 2, 'Nenhum acesso autorizado no recorte.');
        const labels = { requisicoes_http: 'Requisições à API', retiradas_e_movimentacoes_de_objetos: 'Retiradas e movimentações de objetos' };
        byId('st-indisponiveis').replaceChildren(...data.indisponiveis.map((item) => node('li', '', `${labels[item.indicador] || item.indicador}: indisponível. ${item.motivo}`)));
    }

    function renderAccesses(data) {
        const body = byId('st-acessos-corpo'); body.replaceChildren();
        for (const row of data.acessos) tableRow(body, [time(row.horario), row.local ?? `Local #${row.id_local} sem cadastro disponível`, row.id_rfid,
            row.visitante_id == null ? 'Não identificado no evento' : `${row.visitante_nome ?? 'Visitante'} (#${row.visitante_id})`, badge(row.status_tentativa)]);
        if (!data.acessos.length) emptyTable('st-acessos-corpo', 5, 'Nenhuma tentativa encontrada com os filtros aplicados.');
        state.accessPage = data.pagina;
        pager('st-acessos', data.pagina, data.total, data.limite);
    }

    function describeRecut(filters) {
        const labels = { inicio: 'De', fim: 'Até (inclusivo)', local: 'Local #', visitante: 'Visitante #', resultado: 'Resultado', objeto: 'Objeto #', usuario: 'Usuário #', acao: 'Ação' };
        return Object.keys(filters).length ? Object.entries(filters).map(([key, value]) => `${labels[key]} ${value}`).join(' · ') : 'Todo o histórico, sem filtros.';
    }

    let accessReady = false, csvBusy = false;
    function updateCsvButton() { byId('st-acessos-csv').disabled = !state.root || !accessReady || csvBusy; }

    function clearDashboard() {
        accessReady = false; updateCsvButton(); disablePager('st-acessos');
        for (const id of ['st-metricas-cadastros', 'st-metricas-visitantes', 'st-metricas-acessos', 'st-grafico-diario', 'st-ranking', 'st-indisponiveis', 'st-diaria-corpo']) byId(id).replaceChildren();
        setDashboardRankingExpanded(false);
        byId('st-grafico-limite').textContent = '';
        byId('st-acessos-recorte').textContent = '';
        for (const id of ['st-metrica-visitantes-ativos', 'st-patrimonio-total', 'st-locais-total']) byId(id).textContent = '—';
        byId('st-locais-corpo').replaceChildren();
        emptyTable('st-acessos-corpo', 5, 'Aguardando consulta.');
    }

    async function refreshDashboard(filters = filtersFrom(byId('st-acessos-filtros'))) {
        if (!filters) return;
        const sequence = ++accessRequest;
        clearDashboard();
        message('st-acessos-mensagem', 'Carregando indicadores e acessos…');
        try {
            const [summary, report] = await Promise.all([
                request(url('/api/dashboards/resumo', filters)),
                request(url('/api/relatorios/acessos', { ...filters, pagina: 1, limite: 25 })),
            ]);
            if (sequence !== accessRequest) return;
            state.accessFilters = { ...filters };
            renderSummary(summary); renderAccesses(report);
            accessReady = true; updateCsvButton();
            byId('st-acessos-recorte').textContent = `${describeRecut(filters)} · Atualizado em ${time(summary.gerado_em)} UTC.`;
            message('st-acessos-mensagem');
        } catch (error) {
            if (!ignored(error) && sequence === accessRequest) {
                emptyTable('st-acessos-corpo', 5, 'Não foi possível carregar o relatório.');
                message('st-acessos-mensagem', error.message, 'error');
            }
        }
    }

    async function loadAccessPage(page) {
        const sequence = ++accessRequest;
        disablePager('st-acessos');
        message('st-acessos-mensagem', 'Carregando página de acessos…');
        try {
            const data = await request(url('/api/relatorios/acessos', { ...state.accessFilters, pagina: page, limite: 25 }));
            if (sequence !== accessRequest) return;
            renderAccesses(data); message('st-acessos-mensagem');
        } catch (error) { if (!ignored(error) && sequence === accessRequest) message('st-acessos-mensagem', error.message, 'error'); }
    }

    async function filterLocals() {
        try {
            const data = await request('/listar_locais');
            for (const select of document.querySelectorAll('[data-st-locais]')) {
                const selected = select.value;
                const options = data.locais.map((place) => { const option = node('option', '', `${place.endereco} (#${place.id})`); option.value = place.id; return option; });
                const all = node('option', '', 'Todos os locais'); all.value = '';
                if (selected && !options.some((option) => option.value === selected)) { const missing = node('option', '', `Local #${selected} sem cadastro disponível`); missing.value = selected; options.push(missing); }
                select.replaceChildren(all, ...options); select.value = selected;
            }
            message('st-locais-mensagem');
        } catch (error) { if (!ignored(error)) message('st-locais-mensagem', `Filtro de locais: ${error.message}`, 'error'); }
    }

    async function downloadCsv() {
        if (!accessReady || csvBusy) return;
        const epoch = state.epoch;
        const filters = { ...state.accessFilters };
        csvBusy = true; updateCsvButton();
        message('st-acessos-mensagem', 'Preparando CSV com os filtros aplicados…');
        try {
            const blob = await request(url('/api/relatorios/acessos.csv', filters), {}, true);
            const address = URL.createObjectURL(blob);
            const anchor = node('a'); anchor.href = address; anchor.download = 'safe-track-acessos.csv';
            document.body.append(anchor); anchor.click(); anchor.remove();
            setTimeout(() => URL.revokeObjectURL(address), 1000);
            if (JSON.stringify(filters) === JSON.stringify(state.accessFilters)) message('st-acessos-mensagem', 'CSV preparado para download.', 'success');
        } catch (error) { if (!ignored(error)) message('st-acessos-mensagem', error.message, 'error'); }
        finally { if (epoch === state.epoch) { csvBusy = false; updateCsvButton(); } }
    }

    async function loadActivities(page = 1, filters = state.activityFilters) {
        if (!filters) return;
        const sequence = ++activityRequest;
        disablePager('st-atividades');
        emptyTable('st-atividades-corpo', 5, 'Carregando atividades…');
        message('st-atividades-mensagem', 'Carregando atividades…');
        try {
            const data = await request(url('/api/relatorios/atividades', { ...filters, pagina: page, limite: 25 }));
            if (sequence !== activityRequest) return;
            state.activityPage = data.pagina; state.activityFilters = { ...filters }; state.activityLoaded = true;
            const body = byId('st-atividades-corpo'); body.replaceChildren();
            const labels = { buscar_objeto_id: 'Consulta por ID', buscar_objeto_uid: 'Consulta por UID' };
            for (const row of data.atividades) tableRow(body, [time(row.horario), row.id_objeto == null ? 'Não registrado' : `${row.objeto ?? 'Objeto'} (#${row.id_objeto})`,
                row.id_usuario == null ? 'Não registrado' : `Usuário #${row.id_usuario}`, labels[row.acao] || row.acao, badge(row.status_tentativa)]);
            if (!data.atividades.length) emptyTable('st-atividades-corpo', 5, 'Nenhuma atividade encontrada com os filtros aplicados.');
            byId('st-atividades-recorte').textContent = describeRecut(filters);
            pager('st-atividades', data.pagina, data.total, data.limite); message('st-atividades-mensagem');
        } catch (error) {
            if (!ignored(error) && sequence === activityRequest) {
                emptyTable('st-atividades-corpo', 5, 'Não foi possível carregar as atividades.');
                message('st-atividades-mensagem', error.message, 'error');
            }
        }
    }

    function clearSession() {
        const wasPrivate = ['aba-visitantes', 'aba-relatorios'].some((id) => !byId(id).classList.contains('hidden'));
        state.root = false; state.token = null; state.epoch++;
        for (const controller of requests) controller.abort(); requests.clear();
        visitorRequest++; accessRequest++; activityRequest++; dialogRequest++; referenceRequest++;
        if (dialog.open) dialog.close();
        state.edit = initialVisitor = null;
        state.visitorPage = state.accessPage = state.activityPage = 1;
        state.visitorFilters = {}; state.accessFilters = {}; state.activityFilters = {}; state.activityLoaded = false;
        csvBusy = false; clearDashboard();
        for (const item of document.querySelectorAll('[data-safe-track-admin]')) { item.hidden = true; item.classList.add('hidden'); }
        for (const id of ['aba-visitantes', 'aba-relatorios']) byId(id).classList.add('hidden');
        for (const id of ['st-visitantes-filtros', 'st-acessos-filtros', 'st-atividades-filtros', 'st-visitante-formulario']) byId(id).reset();
        for (const id of ['st-visitantes-corpo', 'st-atividades-corpo', 'st-visitante-locais', 'st-visitante-tags']) byId(id).replaceChildren();
        for (const id of ['st-visitantes-mensagem', 'st-acessos-mensagem', 'st-atividades-mensagem', 'st-visitante-formulario-mensagem', 'st-locais-mensagem']) message(id);
        for (const prefix of ['st-visitantes', 'st-acessos', 'st-atividades']) { disablePager(prefix); byId(`${prefix}-pagina`).textContent = 'Nenhuma consulta realizada.'; }
        byId('st-atividades-recorte').textContent = '';
        byId('st-atividades-painel').open = false;
        if (wasPrivate) window.voltarAoDashboard();
    }

    function setSession(role, token) {
        clearSession();
        state.root = role === 'roots' && Boolean(token);
        state.token = state.root ? token : null;
        for (const item of document.querySelectorAll('[data-safe-track-admin]')) { item.hidden = !state.root; item.classList.toggle('hidden', !state.root); }
    }

    function allowSection(id) { return !['visitantes', 'relatorios'].includes(id) || state.root; }

    // Navegação exclusivamente visual: não altera filtros, páginas ou consultas.
    function selectReportModule(name) {
        const tabs = [...byId('aba-relatorios').querySelectorAll('[data-st-report-tab]')];
        if (!tabs.some((tab) => tab.dataset.stReportTab === name)) return;
        for (const tab of tabs) {
            const selected = tab.dataset.stReportTab === name;
            tab.setAttribute('aria-selected', String(selected));
            tab.tabIndex = selected ? 0 : -1;
        }
        for (const panel of byId('aba-relatorios').querySelectorAll('[data-st-report-panel]')) {
            panel.hidden = panel.dataset.stReportPanel !== name;
        }
        byId('st-relatorio-ferramentas').hidden = !['acessos', 'exportacao'].includes(name);
        byId('st-relatorio-ferramentas-titulo').textContent = name === 'exportacao' ? 'Consultar e exportar acessos' : 'Filtros de acesso';
        if (name === 'patrimonio' && state.root) byId('st-atividades-painel').open = true;
    }

    const reportTabs = [...byId('aba-relatorios').querySelectorAll('[data-st-report-tab]')];
    reportTabs.forEach((tab, index) => {
        tab.addEventListener('click', () => selectReportModule(tab.dataset.stReportTab));
        tab.addEventListener('keydown', (event) => {
            let next;
            if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % reportTabs.length;
            else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index - 1 + reportTabs.length) % reportTabs.length;
            else if (event.key === 'Home') next = 0;
            else if (event.key === 'End') next = reportTabs.length - 1;
            else return;
            event.preventDefault();
            reportTabs[next].focus();
            selectReportModule(reportTabs[next].dataset.stReportTab);
        });
    });

    function open(id) {
        if (!state.root) return;
        if (id === 'visitantes') loadVisitors(1, filtersFrom(byId('st-visitantes-filtros')) || {});
        if (id === 'relatorios') {
            selectReportModule('acessos');
            filterLocals(); refreshDashboard();
            if (byId('st-atividades-painel').open) loadActivities(1, filtersFrom(byId('st-atividades-filtros')));
        }
    }

    byId('st-visitantes-fuso').textContent = `Validade exibida no fuso do navegador: ${localZone}.`;
    byId('st-visitante-formulario-fuso').textContent = `Informe as datas e os horários no fuso do navegador (${localZone}).`;
    byId('st-visitante-novo').addEventListener('click', () => openVisitor());
    byId('st-visitante-fechar').addEventListener('click', () => dialog.close());
    visitorForm.addEventListener('submit', saveVisitor);
    byId('st-visitante-referencias').addEventListener('click', () => {
        message('st-visitante-formulario-mensagem', 'Atualizando tags e locais…');
        visitorReferences().then(() => { if (state.root && dialog.open) message('st-visitante-formulario-mensagem'); })
            .catch((error) => { if (!ignored(error)) message('st-visitante-formulario-mensagem', error.message, 'error'); });
    });
    dialog.addEventListener('close', () => {
        dialogRequest++; referenceRequest++;
        visitorForm.reset(); formField(visitorForm, 'senha').value = '';
        state.edit = initialVisitor = null;
        byId('st-visitante-locais').replaceChildren(); byId('st-visitante-tags').replaceChildren();
        if (state.root && previousFocus?.isConnected) previousFocus.focus();
    });
    byId('st-visitantes-filtros').addEventListener('submit', (event) => { event.preventDefault(); const filters = filtersFrom(event.currentTarget); if (filters) loadVisitors(1, filters); });
    byId('st-visitantes-anterior').addEventListener('click', () => loadVisitors(state.visitorPage - 1));
    byId('st-visitantes-proxima').addEventListener('click', () => loadVisitors(state.visitorPage + 1));
    byId('st-acessos-filtros').addEventListener('submit', (event) => { event.preventDefault(); refreshDashboard(); });
    byId('st-acessos-limpar').addEventListener('click', () => { byId('st-acessos-filtros').reset(); refreshDashboard(); });
    byId('st-acessos-anterior').addEventListener('click', () => loadAccessPage(state.accessPage - 1));
    byId('st-acessos-proxima').addEventListener('click', () => loadAccessPage(state.accessPage + 1));
    byId('st-acessos-csv').addEventListener('click', downloadCsv);
    byId('st-atividades-painel').addEventListener('toggle', () => { if (state.root && byId('st-atividades-painel').open && !state.activityLoaded) loadActivities(1, filtersFrom(byId('st-atividades-filtros'))); });
    byId('st-atividades-filtros').addEventListener('submit', (event) => { event.preventDefault(); loadActivities(1, filtersFrom(event.currentTarget)); });
    byId('st-atividades-limpar').addEventListener('click', () => { byId('st-atividades-filtros').reset(); loadActivities(1, {}); });
    byId('st-atividades-anterior').addEventListener('click', () => loadActivities(state.activityPage - 1));
    byId('st-atividades-proxima').addEventListener('click', () => loadActivities(state.activityPage + 1));
    window.SafeTrackAdmin = Object.freeze({ setSession, clearSession, allowSection, open });
})();
