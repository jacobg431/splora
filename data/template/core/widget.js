export class Widget {
    constructor(el, options = {}) {
        this.el = typeof el === 'string' ? document.getElementById(el) : el;
        this.options = options;
        this.data = null;
        this._handlers = new Map();
        this._ro = null;
    }

    mount() {
        if (typeof ResizeObserver !== 'undefined' && this.el) {
            this._ro = new ResizeObserver(() => this.resize());
            this._ro.observe(this.el);
        }
        return this;
    }

    setData(data) {
        this.data = data;
        this.render();
        return this;
    }

    render() {}

    resize() {
        this.render();
    }

    destroy() {
        this._ro?.disconnect();
        this._ro = null;
        this._handlers.clear();
        if (this.el) this.el.replaceChildren();
    }

    on(event, handler) {
        if (!this._handlers.has(event)) this._handlers.set(event, new Set());
        this._handlers.get(event).add(handler);
        return this;
    }

    off(event, handler) {
        this._handlers.get(event)?.delete(handler);
        return this;
    }

    emit(event, payload) {
        this._handlers.get(event)?.forEach(h => h(payload));
        return this;
    }
}
