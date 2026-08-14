import {
    nodeById, formatBytes, fmtCount, registerAll, loadData,
} from './data.js';
import { buildTreeItem, expandToPath, expandNode, setActive, elemById } from './ui/tree.js';
import { initSidebar, renderMeta } from './ui/sidebar.js';
import { Donut } from './widgets/donut.js';
import { Treemap } from './widgets/treemap.js';

let selectedPath = null;
let treemap = null;
let extDonut = null, catDonut = null;

function selectNode(path, source) {
    if (selectedPath === path) return;
    selectedPath = path;
    const node = nodeById[path];
    if (!node) return;

    updateInfo(node);

    if (source !== 'tree') expandToPath(path, selectNode);
    setActive(path);

    if (source !== 'treemap') treemap?.showNode(node);
}

function updateInfo(node) {
    updateStatCards(node);
    updateDonuts(node);
}

function updateStatCards(node) {
    document.getElementById('stat-folder').textContent = node.name;
    document.getElementById('stat-size').textContent   = formatBytes(node.size);
    document.getElementById('stat-count').textContent  = fmtCount(node.file_count);
}

function topEntries(obj, n) {
    return Object.entries(obj || {})
        .sort((a, b) => b[1] - a[1])
        .slice(0, n)
        .map(([name, value]) => ({ name: name || '(none)', value }));
}

function updateDonuts(node) {
    extDonut.setData(topEntries(node.extensions, 10));
    catDonut.setData(topEntries(node.categories, 11));
}

function initTreemap(root) {
    treemap = new Treemap(document.getElementById('treemap-container'), {
        formatValue: formatBytes,
        formatCount: fmtCount,
    }).mount();
    treemap.on('select', path => selectNode(path, 'treemap'));
    treemap.setData(root);
}

function initCharts() {
    extDonut = new Donut(document.getElementById('chart-ext'), { title: 'Extensions', formatValue: fmtCount }).mount();
    catDonut = new Donut(document.getElementById('chart-cat'), { title: 'Categories', formatValue: fmtCount }).mount();
}

async function loadReport() {
    try {
        return await loadData();
    } catch {
        return null;
    }
}

function renderNoData() {
    document.body.innerHTML = `
        <div class="no-data">
            <div class="no-data-icon">📂</div>
            <div class="no-data-title">No report data found</div>
            <div class="no-data-hint">Run <code>splora report</code> to generate a report.</div>
        </div>`;
}

function buildTree(tree) {
    document.getElementById('tree-root').append(buildTreeItem(tree, 0, selectNode));
    const rootEl = elemById[tree.path];
    if (rootEl) expandNode(rootEl, selectNode);
}

async function init() {
    initSidebar();

    const data = await loadReport();
    if (!data) {
        renderNoData();
        return;
    }

    const { meta, tree } = data;
    document.title = meta.name ?? 'Splora';
    renderMeta(meta);
    registerAll(tree, null);

    buildTree(tree);
    initCharts();
    initTreemap(tree);
    selectNode(tree.path, 'init');
}

init();
