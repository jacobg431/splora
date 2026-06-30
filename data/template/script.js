'use strict';

// ── Utilities ──────────────────────────────────────────────────────────────

function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const v = bytes / Math.pow(1024, i);
    return (i === 0 ? Math.round(v) : v.toFixed(1)) + ' ' + units[i];
}

function fmtCount(n) {
    return Number(n || 0).toLocaleString();
}

// ── State ──────────────────────────────────────────────────────────────────

const nodeById = {};   // path → data node (with ._parent back-reference)
const elemById = {};   // path → .tree-item DOM element
let selectedPath = null;
let treemap = null, extChart = null, catChart = null;

// ── Data helpers ───────────────────────────────────────────────────────────

function registerAll(node, parent) {
    node._parent = parent ?? null;
    nodeById[node.path] = node;
    node.children?.forEach(c => registerAll(c, node));
}

function toTreemapItem(node) {
    const item = {
        id:     node.path,
        name:   node.name,
        value:  node.size || 0,
        _path:  node.path,
        _count: node.file_count || 0,
    };
    if (node.children?.length) item.children = node.children.map(toTreemapItem);
    return item;
}

// ── Folder tree ────────────────────────────────────────────────────────────

function buildTreeItem(node, depth) {
    const hasDirs = node.children?.length > 0;

    const item = document.createElement('div');
    item.className = 'tree-item';
    item.dataset.path  = node.path;
    item.dataset.depth = depth;
    elemById[node.path] = item;

    const row = document.createElement('div');
    row.className = 'tree-row';
    row.style.paddingLeft = (depth * 14 + 8) + 'px';

    const caret = document.createElement('span');
    caret.className = hasDirs ? 'caret' : 'caret leaf';
    caret.textContent = hasDirs ? '▶' : '';

    const icon = document.createElement('span');
    icon.className = 'tree-icon';
    icon.textContent = '📁';

    const label = document.createElement('span');
    label.className = 'tree-label';
    label.textContent = node.name;

    row.append(caret, icon, label);
    item.append(row);
    row.addEventListener('click', () => selectNode(node.path, 'tree'));

    if (hasDirs) {
        const kids = document.createElement('div');
        kids.className = 'tree-children collapsed';
        item.append(kids);

        caret.addEventListener('click', e => {
            e.stopPropagation();
            if (!kids.dataset.rendered) {
                node.children.forEach(c => kids.append(buildTreeItem(c, depth + 1)));
                kids.dataset.rendered = '1';
            }
            const nowOpen = kids.classList.toggle('collapsed') === false;
            caret.classList.toggle('open', nowOpen);
        });
    }

    return item;
}

// Ensure all ancestors of targetPath are expanded and rendered in the tree.
function expandToPath(targetPath) {
    const chain = [];
    let n = nodeById[targetPath];
    while (n) { chain.unshift(n.path); n = n._parent; }

    for (const p of chain.slice(0, -1)) {
        const el = elemById[p];
        if (!el) continue;
        const kids = el.querySelector(':scope > .tree-children');
        if (!kids) continue;
        if (!kids.dataset.rendered) {
            const d = parseInt(el.dataset.depth, 10);
            nodeById[p].children?.forEach(c => kids.append(buildTreeItem(c, d + 1)));
            kids.dataset.rendered = '1';
        }
        kids.classList.remove('collapsed');
        const caret = el.querySelector(':scope > .tree-row > .caret');
        if (caret) caret.classList.add('open');
    }
}

// ── Selection — single source of truth for bidirectional sync ──────────────

function selectNode(path, source) {
    if (selectedPath === path) return;
    selectedPath = path;
    const node = nodeById[path];
    if (!node) return;

    updateInfo(node);

    // Tree: clear old highlight, expand ancestors if needed, highlight new row
    document.querySelectorAll('.tree-row.active').forEach(el => el.classList.remove('active'));
    if (source !== 'tree') expandToPath(path);
    const el = elemById[path];
    if (el) {
        el.querySelector(':scope > .tree-row')?.classList.add('active');
        el.querySelector(':scope > .tree-row')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    // Treemap: zoom to selected node
    if (source !== 'treemap') {
        treemap?.dispatchAction({ type: 'treemapZoomToNode', targetNodeId: path });
    }
}

// ── Info panel ─────────────────────────────────────────────────────────────

function updateInfo(node) {
    document.getElementById('stat-folder').textContent = node.name;
    document.getElementById('stat-size').textContent = formatBytes(node.size);
    document.getElementById('stat-count').textContent = fmtCount(node.file_count);
    updatePies(node);
}

function updatePies(node) {
    const top = (obj, n) =>
        Object.entries(obj || {})
              .sort((a, b) => b[1] - a[1])
              .slice(0, n)
              .map(([name, value]) => ({ name: name || '(none)', value }));

    const pieOpt = (title, data) => ({
        title: {
            text: title,
            left: 'center',
            top: 6,
            textStyle: { fontSize: 12, fontWeight: 'normal', color: '#6b7280' },
        },
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        series: [{
            type: 'pie',
            radius: ['32%', '62%'],
            top: 30,
            bottom: 4,
            data,
            label: { fontSize: 11, formatter: '{b}\n{d}%' },
            emphasis: { scale: true, scaleSize: 4 },
        }],
    });

    extChart.setOption(pieOpt('Extensions', top(node.extensions, 10)));
    catChart.setOption(pieOpt('Categories', top(node.categories, 11)));
}

// ── Treemap ────────────────────────────────────────────────────────────────

function initTreemap(root) {
    treemap = echarts.init(document.getElementById('treemap-container'));

    treemap.setOption({
        tooltip: {
            formatter: p =>
                `<b>${p.data.name}</b><br>${formatBytes(p.data.value)}<br>${fmtCount(p.data._count)} files`,
        },
        series: [{
            type: 'treemap',
            id: 'main',
            left: 0, right: 0, top: 0, bottom: 0,
            roam: false,
            nodeClick: 'zoomToNode',
            data: [toTreemapItem(root)],
            breadcrumb: {
                show: true,
                bottom: 6,
                height: 22,
                itemStyle: {
                    color: '#f3f4f6',
                    textStyle: { color: '#374151', fontSize: 12 },
                },
            },
            upperLabel: { show: true, height: 26, fontSize: 12, color: '#fff' },
            label:      { show: true, fontSize: 12, formatter: '{b}' },
            itemStyle:  { borderColor: '#fff' },
            levels: [
                { itemStyle: { borderWidth: 4, gapWidth: 4, borderColor: '#c5d0e0' } },
                { itemStyle: { borderWidth: 2, gapWidth: 2 } },
                { itemStyle: { borderWidth: 1, gapWidth: 1 } },
            ],
        }],
    });

    treemap.on('click', params => {
        const path = params.data?._path;
        if (path && nodeById[path]) selectNode(path, 'treemap');
    });
}

// ── Sidebar ────────────────────────────────────────────────────────────────

function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggle  = document.getElementById('sidebar-toggle');
    toggle?.addEventListener('click', () => sidebar?.classList.toggle('collapsed'));
}

// ── Bootstrap ──────────────────────────────────────────────────────────────

async function init() {
    initSidebar();

    let data;
    try {
        const res = await fetch('./data.json');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        data = await res.json();
    } catch {
        document.body.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:center;
                        height:100vh;font-family:system-ui;flex-direction:column;gap:12px;color:#6b7280">
                <div style="font-size:48px">📂</div>
                <div style="font-size:18px;font-weight:600;color:#111">No report data found</div>
                <div style="font-size:13px">
                    Run <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px">splora report</code>
                    to generate a report.
                </div>
            </div>`;
        return;
    }

    const { meta, tree } = data;

    document.title = meta.name ?? 'Splora';

    // Register all nodes with parent back-references
    registerAll(tree, null);

    // Build tree panel: root item + eagerly render its direct children
    const treeRoot = document.getElementById('tree-root');
    treeRoot.append(buildTreeItem(tree, 0));

    const rootEl = elemById[tree.path];
    if (rootEl && tree.children?.length) {
        const kids  = rootEl.querySelector(':scope > .tree-children');
        const caret = rootEl.querySelector(':scope > .tree-row > .caret');
        if (kids) {
            tree.children.forEach(c => kids.append(buildTreeItem(c, 1)));
            kids.dataset.rendered = '1';
            kids.classList.remove('collapsed');
            if (caret) caret.classList.add('open');
        }
    }

    // Init ECharts instances
    extChart = echarts.init(document.getElementById('chart-ext'));
    catChart = echarts.init(document.getElementById('chart-cat'));
    initTreemap(tree);

    // Select root to populate info panel on load
    selectNode(tree.path, 'init');

    window.addEventListener('resize', () => {
        treemap?.resize();
        extChart?.resize();
        catChart?.resize();
    });

    // Resize after the first paint so ECharts reads final CSS Grid dimensions.
    requestAnimationFrame(() => {
        treemap?.resize();
        extChart?.resize();
        catChart?.resize();
    });
}

init();
