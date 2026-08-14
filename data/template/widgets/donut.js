import { Widget } from '../core/widget.js';
import { svgEl, svgRoot, clear } from '../core/svg.js';
import { COLORS, SERIES } from '../core/theme.js';
import { annularSectorPath, polarToXY, donutArcs } from '../core/layout.js';

const EMPHASIS = 6;
const LABEL_MIN_ANGLE = 0.38;

function truncate(text, max) {
    return text.length > max ? text.slice(0, max - 1) + '…' : text;
}

export class Donut extends Widget {
    constructor(el, options = {}) {
        super(el, options);
        this.title = options.title ?? '';
        this.formatValue = options.formatValue ?? (v => String(v));
        this._segments = [];
        this._geom = null;
        this._total = 0;
        this._centerBig = null;
        this._centerSmall = null;
    }

    render() {
        if (!this.el) return;
        clear(this.el);

        const w = this.el.clientWidth;
        const h = this.el.clientHeight;
        if (!w || !h || !this.data?.length) return;

        this._geom = this._layout(w, h);
        this._total = this.data.reduce((sum, d) => sum + (d.value || 0), 0);

        const svg = svgRoot(w, h);
        if (this.title) svg.append(this._titleText(w));
        svg.append(this._ring());
        svg.append(this._arcLabels());
        svg.append(this._center());
        this.el.append(svg);

        this._resetCenter();
    }

    _layout(w, h) {
        const pad = 8;
        const titleH = this.title ? 22 : 0;
        const top = pad + titleH;
        const size = Math.min(w - pad * 2, h - top - pad);
        const rOuter = Math.max(size / 2 - EMPHASIS, 0);
        return { cx: w / 2, cy: top + size / 2, rOuter, rInner: rOuter * 0.6 };
    }

    _titleText(w) {
        return svgEl('text', {
            x: w / 2, y: 15,
            'text-anchor': 'middle',
            'font-size': 12,
            fill: COLORS.muted,
        }, this.title);
    }

    _ring() {
        const { cx, cy, rInner, rOuter } = this._geom;
        const g = svgEl('g');
        this._segments = donutArcs(this.data).map((arc, i) => {
            const path = svgEl('path', {
                d: annularSectorPath(cx, cy, rInner, rOuter, arc.a0, arc.a1),
                fill: SERIES[i % SERIES.length],
                stroke: COLORS.surface,
                'stroke-width': 2,
                'fill-rule': 'evenodd',
                class: 'donut-seg',
            });
            path.addEventListener('pointerenter', () => this._emphasize(i));
            path.addEventListener('pointerleave', () => this._deemphasize());
            g.append(path);
            return { ...arc, path, pct: this._total ? arc.value / this._total : 0 };
        });
        return g;
    }

    _arcLabels() {
        const { cx, cy, rInner, rOuter } = this._geom;
        const rMid = (rInner + rOuter) / 2;
        const g = svgEl('g', { 'pointer-events': 'none' });
        for (const seg of this._segments) {
            if (seg.a1 - seg.a0 < LABEL_MIN_ANGLE) continue;
            const [x, y] = polarToXY(cx, cy, rMid, (seg.a0 + seg.a1) / 2);
            g.append(svgEl('text', {
                x, y,
                'text-anchor': 'middle',
                'dominant-baseline': 'central',
                'font-size': 11,
                fill: '#0b1020',
            }, truncate(seg.name, 8)));
        }
        return g;
    }

    _center() {
        const { cx, cy } = this._geom;
        const g = svgEl('g', { 'pointer-events': 'none' });
        this._centerBig = svgEl('text', {
            x: cx, y: cy - 2,
            'text-anchor': 'middle',
            'dominant-baseline': 'central',
            'font-size': 20, 'font-weight': 700,
            fill: COLORS.text,
        });
        this._centerSmall = svgEl('text', {
            x: cx, y: cy + 16,
            'text-anchor': 'middle',
            'dominant-baseline': 'central',
            'font-size': 11,
            fill: COLORS.muted,
        });
        g.append(this._centerBig, this._centerSmall);
        return g;
    }

    _emphasize(i) {
        const { cx, cy, rInner, rOuter } = this._geom;
        this._segments.forEach((seg, j) => {
            seg.path.style.opacity = j === i ? '1' : '0.4';
        });
        const seg = this._segments[i];
        seg.path.setAttribute('d', annularSectorPath(cx, cy, rInner, rOuter + EMPHASIS, seg.a0, seg.a1));
        this._setCenter(`${Math.round(seg.pct * 100)}%`, `${truncate(seg.name, 12)} · ${this.formatValue(seg.value)}`);
    }

    _deemphasize() {
        const { cx, cy, rInner, rOuter } = this._geom;
        this._segments.forEach(seg => {
            seg.path.style.opacity = '1';
            seg.path.setAttribute('d', annularSectorPath(cx, cy, rInner, rOuter, seg.a0, seg.a1));
        });
        this._resetCenter();
    }

    _resetCenter() {
        this._setCenter(this.formatValue(this._total), 'total');
    }

    _setCenter(big, small) {
        if (this._centerBig) this._centerBig.textContent = big;
        if (this._centerSmall) this._centerSmall.textContent = small;
    }
}
