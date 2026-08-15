export function polarToXY(cx, cy, r, angle) {
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

export function annularSectorPath(cx, cy, rInner, rOuter, a0, a1) {
    const span = a1 - a0;
    if (span >= Math.PI * 2 - 1e-6) return fullRingPath(cx, cy, rInner, rOuter);

    const large = span > Math.PI ? 1 : 0;
    const [ox0, oy0] = polarToXY(cx, cy, rOuter, a0);
    const [ox1, oy1] = polarToXY(cx, cy, rOuter, a1);
    const [ix1, iy1] = polarToXY(cx, cy, rInner, a1);
    const [ix0, iy0] = polarToXY(cx, cy, rInner, a0);

    return [
        `M ${ox0} ${oy0}`,
        `A ${rOuter} ${rOuter} 0 ${large} 1 ${ox1} ${oy1}`,
        `L ${ix1} ${iy1}`,
        `A ${rInner} ${rInner} 0 ${large} 0 ${ix0} ${iy0}`,
        'Z',
    ].join(' ');
}

function fullRingPath(cx, cy, rInner, rOuter) {
    return [
        `M ${cx - rOuter} ${cy}`,
        `A ${rOuter} ${rOuter} 0 1 0 ${cx + rOuter} ${cy}`,
        `A ${rOuter} ${rOuter} 0 1 0 ${cx - rOuter} ${cy}`,
        'Z',
        `M ${cx - rInner} ${cy}`,
        `A ${rInner} ${rInner} 0 1 0 ${cx + rInner} ${cy}`,
        `A ${rInner} ${rInner} 0 1 0 ${cx - rInner} ${cy}`,
        'Z',
    ].join(' ');
}

export function donutArcs(data, startAngle = -Math.PI / 2) {
    const total = data.reduce((sum, d) => sum + (d.value || 0), 0) || 1;
    let angle = startAngle;
    return data.map(d => {
        const a0 = angle;
        const a1 = angle + ((d.value || 0) / total) * Math.PI * 2;
        angle = a1;
        return { name: d.name, value: d.value || 0, a0, a1 };
    });
}

// Squarified treemap layout (Bruls, Huizing & van Wijk, 2000). Returns a rect
// { item, x, y, w, h } per input item, sized proportionally to item.value.
export function squarify(items, rect) {
    const result = [];
    const positive = items.filter(it => it.value > 0);
    const total = positive.reduce((sum, it) => sum + it.value, 0);
    if (total <= 0 || rect.w <= 0 || rect.h <= 0) return result;

    const scale = (rect.w * rect.h) / total;
    const queue = positive
        .map(it => ({ item: it, area: it.value * scale }))
        .sort((a, b) => b.area - a.area);

    let { x, y, w, h } = rect;
    let row = [];

    for (const cell of queue) {
        const side = Math.min(w, h);
        if (row.length === 0 || worstRatio(row, side) >= worstRatio([...row, cell], side)) {
            row.push(cell);
        } else {
            const placed = placeRow(row, x, y, w, h);
            result.push(...placed.rects);
            ({ x, y, w, h } = placed.remaining);
            row = [cell];
        }
    }
    if (row.length) result.push(...placeRow(row, x, y, w, h).rects);
    return result;
}

function worstRatio(row, side) {
    let sum = 0, max = -Infinity, min = Infinity;
    for (const cell of row) {
        sum += cell.area;
        if (cell.area > max) max = cell.area;
        if (cell.area < min) min = cell.area;
    }
    const sum2 = sum * sum;
    const side2 = side * side;
    return Math.max((side2 * max) / sum2, sum2 / (side2 * min));
}

function placeRow(row, x, y, w, h) {
    const sum = row.reduce((acc, cell) => acc + cell.area, 0);
    const rects = [];
    if (w >= h) {
        const colW = sum / h;
        let offset = y;
        for (const cell of row) {
            const cellH = cell.area / colW;
            rects.push({ item: cell.item, x, y: offset, w: colW, h: cellH });
            offset += cellH;
        }
        return { rects, remaining: { x: x + colW, y, w: w - colW, h } };
    }
    const rowH = sum / w;
    let offset = x;
    for (const cell of row) {
        const cellW = cell.area / rowH;
        rects.push({ item: cell.item, x: offset, y, w: cellW, h: rowH });
        offset += cellW;
    }
    return { rects, remaining: { x, y: y + rowH, w, h: h - rowH } };
}
