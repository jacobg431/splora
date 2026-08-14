export const nodeById = {};

export function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const v = bytes / Math.pow(1024, i);
    return (i === 0 ? Math.round(v) : v.toFixed(1)) + ' ' + units[i];
}

export function fmtCount(n) {
    return Number(n || 0).toLocaleString();
}

export function registerAll(node, parent) {
    node._parent = parent ?? null;
    nodeById[node.path] = node;
    node.children?.forEach(c => registerAll(c, node));
}

export async function loadData() {
    const res = await fetch('./data.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}
