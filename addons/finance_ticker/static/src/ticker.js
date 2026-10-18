import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { NavBar } from "@web/webclient/navbar/navbar";
import { WebClient } from "@web/webclient/webclient";

const REFRESH_MS = 60 * 1000;

export class FinanceTicker extends Component {
    static template = "finance_ticker.FinanceTicker";
    static props = {};

    setup() {
        this.state = useState({ items: [], error: false });
        onWillStart(() => this.load());
        this.timer = setInterval(() => this.load(), REFRESH_MS);
        onWillUnmount(() => clearInterval(this.timer));
    }

    async load() {
        try {
            const res = await rpc("/finance_ticker/data", {});
            this.state.items = res.items || [];
            this.state.error = !!res.error;
        } catch {
            this.state.error = true;
        }
    }

    format(item) {
        const d = ["usd", "eur"].includes(item.key) ? 2 : 0;
        return new Intl.NumberFormat("tr-TR", {
            minimumFractionDigits: d,
            maximumFractionDigits: d,
        }).format(item.value);
    }

    pct(item) {
        return Math.abs(item.change).toFixed(2);
    }

    trend(item) {
        return item.change < 0 ? "down" : "up";
    }

    sparkline(item) {
        const h = item.history && item.history.length > 1 ? item.history : [item.value, item.value];
        const min = Math.min(...h);
        const max = Math.max(...h);
        const range = max - min || 1;
        const w = 56;
        const height = 16;
        return h
            .map((v, i) => {
                const x = (i / (h.length - 1)) * w;
                const y = height - ((v - min) / range) * (height - 2) - 1;
                return `${x.toFixed(1)},${y.toFixed(1)}`;
            })
            .join(" ");
    }
}

patch(WebClient.components, { FinanceTicker });

patch(NavBar.prototype, {
    setup() {
        super.setup(...arguments);
        this.commandService = useService("command");
    },
    openFinder() {
        this.commandService.openMainPalette({ searchValue: "" });
    },
});