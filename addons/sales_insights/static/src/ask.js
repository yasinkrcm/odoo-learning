import { Component, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

export class SalesInsightsAsk extends Component {
    static template = "sales_insights.SalesInsightsAsk";

    setup() {
        this.state = useState({ q: "", answer: "" });
    }

    async ask() {
        const q = this.state.q.trim();
        if (!q) return;
        this.state.answer = "…";
        const res = await rpc("/sales_insights/ask_user", { q });
        this.state.answer = res.answer || "—";
    }

    onKeyup(ev) {
        if (ev.key === "Enter") this.ask();
    }
}

patch(WebClient.components, { SalesInsightsAsk });
