const NS = 'http://www.w3.org/2000/svg';

export function svgEl(tag, attrs = {}, children = []) {
    const el = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) {
        if (v == null) continue;
        el.setAttribute(k, String(v));
    }
    if (typeof children === 'string') {
        el.textContent = children;
    } else {
        for (const c of children) el.append(c);
    }
    return el;
}

export function svgRoot(width, height) {
    return svgEl('svg', {
        viewBox: `0 0 ${width} ${height}`,
        width: '100%',
        height: '100%',
        preserveAspectRatio: 'none',
    });
}

export function clear(el) {
    if (el) el.replaceChildren();
}
