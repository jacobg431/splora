import { COLORS, SERIES, DARK_TOOLTIP } from './core/theme.js';
import {
    nodeById, formatBytes, fmtCount, registerAll, toTreemapItem, loadData,
} from './data.js';
import { buildTreeItem, expandToPath, expandNode, setActive, elemById } from './ui/tree.js';
import { initSidebar, renderMeta } from './ui/sidebar.js';
import { Donut } from './widgets/donut.js';

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

    if (source !== 'treemap') {
        treemap?.dispatchAction({ type: 'treemapZoomToNode', targetNodeId: path });
    }
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

function treemapOption(root) {
    return {
        color: SERIES,
        backgroundColor: 'transparent',
        tooltip: {
            formatter: p =>
                `<b>${p.data.name}</b><br>${formatBytes(p.data.value)}<br>${fmtCount(p.data._count)} files`,
            ...DARK_TOOLTIP,
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
                    color: COLORS.surfaceRaised,
                    borderColor: 'transparent',
                    textStyle: { color: COLORS.muted, fontSize: 12 },
                },
                emphasis: { itemStyle: { color: COLORS.accent, textStyle: { color: '#0b1020' } } },
            },
            upperLabel: { show: true, height: 26, fontSize: 12, color: '#fff' },
            label:      { show: true, fontSize: 12, color: '#0b1020', formatter: '{b}' },
            itemStyle:  { borderColor: COLORS.canvas, gapWidth: 2 },
            levels: [
                { itemStyle: { borderWidth: 3, gapWidth: 3, borderColor: COLORS.canvas } },
                { itemStyle: { borderWidth: 2, gapWidth: 2, borderColor: COLORS.canvas } },
                { itemStyle: { borderWidth: 1, gapWidth: 1, borderColor: COLORS.canvas } },
            ],
        }],
    };
}

function initTreemap(root) {
    treemap = echarts.init(document.getElementById('treemap-container'));
    treemap.setOption(treemapOption(root));
    treemap.on('click', params => {
        const path = params.data?._path;
        if (path && nodeById[path]) selectNode(path, 'treemap');
    });
}

function initCharts() {
    extDonut = new Donut(document.getElementById('chart-ext'), { title: 'Extensions', formatValue: fmtCount }).mount();
    catDonut = new Donut(document.getElementById('chart-cat'), { title: 'Categories', formatValue: fmtCount }).mount();
}

function resizeAll() {
    treemap?.resize();
}

function wireResize() {
    window.addEventListener('resize', resizeAll);
    requestAnimationFrame(resizeAll);
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
    wireResize();
}

init();
