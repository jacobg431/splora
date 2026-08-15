import { formatBytes, fmtCount } from '../data.js';

export function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggle  = document.getElementById('sidebar-toggle');
    toggle?.addEventListener('click', () => sidebar?.classList.toggle('collapsed'));
}

export function renderMeta(meta) {
    const set = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };
    set('meta-name',  meta.name ?? 'Splora');
    set('meta-root',  meta.root ?? '');
    set('meta-files', fmtCount(meta.total_files));
    set('meta-size',  formatBytes(meta.total_size));

    const partial = document.getElementById('meta-partial');
    if (partial) partial.classList.toggle('hidden', !meta.partial);
}
