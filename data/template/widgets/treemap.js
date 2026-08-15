import { Widget } from '../core/widget.js';
import { svgEl, svgRoot, clear } from '../core/svg.js';
import { COLORS, SERIES } from '../core/theme.js';
import { squarify } from '../core/layout.js';

const GAP = 3;
const RADIUS = 4;
const FILES_FILL = '#3a4056';
const CHAR_PX = 7;

function truncate(text, maxPx) {
    const max = Math.floor(maxPx / CHAR_PX);
    if (max <= 0) return '';
    return text.length > max ? text.slice(0, max - 1) + '…' : text;
}

export class Treemap extends Widget {
    constructor(el, options = {}) {
        super(el, options);
        this.formatValue = options.formatValue ?? (v => String(v));
        this.formatCount = options.formatCount ?? (v => String(v));
        this._root = null;
        this._current = null;
        this._selectedPath = null;
    }

    setData(root) {
        this._root = root;
        this._current = root;
        this.data = root;
        this.render();
        return this;
    }

    showNode(node) {
        if (!node) return;
        this._current = node.children?.length ? node : (node._parent ?? node);
        this._selectedPath = node.path;
        this.render();
    }

    render() {
        if (!this.el || !this._current) return;
        clear(this.el);
        this.el.append(this._breadcrumb());

        const canvas = document.createElement('div');
        canvas.className = 'tm-canvas';
        this.el.append(canvas);

        const w = canvas.clientWidth;
        const h = canvas.clientHeight;
        if (w && h) canvas.append(this._svg(w, h));
    }

    _breadcrumb() {
        const bar = document.createElement('div');
        bar.className = 'tm-breadcrumb';

        const chain = [];
        for (let n = this._current; n; n = n._parent) chain.unshift(n);

        chain.forEach((node, i) => {
            if (i > 0) {
                const sep = document.createElement('span');
                sep.className = 'tm-sep';
                sep.textContent = '›';
                bar.append(sep);
            }
            bar.append(this._crumb(node, i === chain.length - 1));
        });
        return bar;
    }

    _crumb(node, isCurrent) {
        const el = document.createElement(isCurrent ? 'span' : 'button');
        el.className = 'tm-crumb' + (isCurrent ? ' current' : '');
        el.textContent = node.name;
        if (!isCurrent) {
            el.addEventListener('click', () => {
                this._current = node;
                this._selectedPath = node.path;
                this.render();
                this.emit('select', node.path);
            });
        }
        return el;
    }

    _svg(w, h) {
        const svg = svgRoot(w, h);
        const rects = squarify(this._items(), { x: GAP, y: GAP, w: w - GAP * 2, h: h - GAP * 2 });
        for (const rect of rects) svg.append(this._tile(rect));
        return svg;
    }

    _items() {
        const node = this._current;
        const children = (node.children ?? []).map((child, i) => ({
            node: child,
            value: child.size || 0,
            fill: SERIES[i % SERIES.length],
            text: '#0b1020',
        }));

        const childrenSize = children.reduce((sum, c) => sum + c.value, 0);
        const childrenFiles = (node.children ?? []).reduce((sum, c) => sum + (c.file_count || 0), 0);
        const ownSize = (node.size || 0) - childrenSize;
        if (ownSize > 0 && children.length) {
            children.push({
                node: { name: '(files)', path: null, size: ownSize, file_count: (node.file_count || 0) - childrenFiles },
                value: ownSize,
                fill: FILES_FILL,
                text: COLORS.muted,
            });
        }

        if (!children.length) {
            children.push({ node, value: node.size || 1, fill: SERIES[0], text: '#0b1020' });
        }
        return children;
    }

    _tile({ item, x, y, w, h }) {
        const iw = Math.max(w - GAP, 0);
        const ih = Math.max(h - GAP, 0);
        const selected = item.node.path && item.node.path === this._selectedPath;

        const g = svgEl('g', { class: 'tm-tile' });
        g.append(svgEl('rect', {
            x: x + GAP / 2, y: y + GAP / 2, width: iw, height: ih, rx: RADIUS,
            fill: item.fill,
            stroke: selected ? COLORS.accent : 'none',
            'stroke-width': selected ? 2 : 0,
        }));
        g.append(svgEl('title', {},
            `${item.node.name}\n${this.formatValue(item.node.size)} · ${this.formatCount(item.node.file_count)} files`));

        if (iw > 46 && ih > 24) g.append(this._label(item, x + GAP / 2, y + GAP / 2, iw, ih));

        if (item.node.path) {
            g.style.cursor = 'pointer';
            g.addEventListener('click', () => this._onClick(item.node));
        }
        return g;
    }

    _label(item, x, y, iw, ih) {
        const g = svgEl('g', { 'pointer-events': 'none' });
        g.append(svgEl('text', {
            x: x + 7, y: y + 17,
            'font-size': 12, 'font-weight': 600, fill: item.text,
        }, truncate(item.node.name, iw - 12)));

        if (ih > 42) {
            g.append(svgEl('text', {
                x: x + 7, y: y + 33,
                'font-size': 11, fill: item.text, 'fill-opacity': 0.75,
            }, truncate(this.formatValue(item.node.size), iw - 12)));
        }
        return g;
    }

    _onClick(node) {
        if (node.children?.length) this._current = node;
        this._selectedPath = node.path;
        this.render();
        this.emit('select', node.path);
    }
}
