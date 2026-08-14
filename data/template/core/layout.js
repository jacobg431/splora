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
