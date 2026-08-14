import { nodeById } from '../data.js';

export const elemById = {};

// Bootstrap Icons "chevron-right" (MIT).
const CHEVRON_SVG =
    '<svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor" xmlns="http://www.w3.org/2000/svg">' +
    '<path fill-rule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z"/></svg>';

function createCaret(hasDirs) {
    const caret = document.createElement('span');
    caret.className = hasDirs ? 'caret' : 'caret leaf';
    if (hasDirs) caret.innerHTML = CHEVRON_SVG;
    return caret;
}

function createRow(node, depth, caret, onSelect) {
    const label = document.createElement('span');
    label.className = 'tree-label';
    label.textContent = node.name;

    const row = document.createElement('div');
    row.className = 'tree-row';
    row.style.paddingLeft = (depth * 14 + 8) + 'px';
    row.append(caret, label);
    row.addEventListener('click', () => onSelect(node.path, 'tree'));
    return row;
}

function renderChildren(kids, node, depth, onSelect) {
    if (kids.dataset.rendered) return;
    node.children?.forEach(c => kids.append(buildTreeItem(c, depth + 1, onSelect)));
    kids.dataset.rendered = '1';
}

function attachToggle(caret, kids, node, depth, onSelect) {
    caret.addEventListener('click', e => {
        e.stopPropagation();
        renderChildren(kids, node, depth, onSelect);
        const open = kids.classList.toggle('collapsed') === false;
        caret.classList.toggle('open', open);
    });
}

export function buildTreeItem(node, depth, onSelect) {
    const hasDirs = node.children?.length > 0;

    const item = document.createElement('div');
    item.className = 'tree-item';
    item.dataset.path  = node.path;
    item.dataset.depth = depth;
    elemById[node.path] = item;

    const caret = createCaret(hasDirs);
    item.append(createRow(node, depth, caret, onSelect));

    if (hasDirs) {
        const kids = document.createElement('div');
        kids.className = 'tree-children collapsed';
        item.append(kids);
        attachToggle(caret, kids, node, depth, onSelect);
    }

    return item;
}

export function expandNode(el, onSelect) {
    const kids = el.querySelector(':scope > .tree-children');
    if (!kids) return;
    const depth = parseInt(el.dataset.depth, 10);
    renderChildren(kids, nodeById[el.dataset.path], depth, onSelect);
    kids.classList.remove('collapsed');
    el.querySelector(':scope > .tree-row > .caret')?.classList.add('open');
}

export function expandToPath(targetPath, onSelect) {
    const chain = [];
    let n = nodeById[targetPath];
    while (n) { chain.unshift(n.path); n = n._parent; }

    for (const p of chain.slice(0, -1)) {
        const el = elemById[p];
        if (el) expandNode(el, onSelect);
    }
}

export function setActive(path) {
    document.querySelectorAll('.tree-row.active').forEach(el => el.classList.remove('active'));
    const el = elemById[path];
    if (el) {
        const row = el.querySelector(':scope > .tree-row');
        row?.classList.add('active');
        row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
}
