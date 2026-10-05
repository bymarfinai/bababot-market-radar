from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "index.html"


class DashboardPS45ShadowUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = DASHBOARD.read_text(encoding="utf-8")

    def test_tab_is_between_positions_and_open_orders(self):
        positions = self.html.index('data-tab="positions"')
        shadow = self.html.index('data-tab="shadow"')
        open_orders = self.html.index('data-tab="openorders"')
        self.assertLess(positions, shadow)
        self.assertLess(shadow, open_orders)

    def test_shadow_pane_has_one_trade_four_protector_columns(self):
        for label in ("V4.2", "V4.3", "BE0.25", "BE0.18"):
            self.assertIn(f"<th>{label}</th>", self.html)
        self.assertIn('id="shadowRows"', self.html)
        self.assertIn('Best / Δ vs V4.2', self.html)

    def test_shadow_detail_and_settlement_ledger_exist(self):
        self.assertIn('id="shadowDetail"', self.html)
        self.assertIn("Virtual Settlement Ledger", self.html)
        self.assertIn("function renderShadowDetail()", self.html)
        self.assertIn("function loadShadowSettlements(parentId,silent)", self.html)

    def test_ui_reads_all_shadow_contract_endpoints(self):
        expected = (
            "/shadow/protection/positions?limit=120",
            "/shadow/protection/contract",
            "/shadow/protection/adapters",
            "/shadow/protection/settlement",
            "/shadow/protection/runtime",
            "/shadow/protection/settlements?parent_id=",
        )
        for path in expected:
            self.assertIn(path, self.html)

    def test_shadow_ui_is_read_only(self):
        start = self.html.index("function shadowBranchValue")
        end = self.html.index("function renderApprovals")
        section = self.html[start:end]
        self.assertNotIn("method:'POST'", section)
        self.assertNotIn('method:"POST"', section)
        self.assertNotIn("/control/", section)

    def test_parity_invalid_trade_is_excluded_from_best_comparison(self):
        self.assertIn(
            "var best=parity.comparison_eligible?cmp.current_best_branch_key:null;",
            self.html,
        )
        self.assertIn("EXCLUDED", self.html)
        self.assertIn("parity invalid", self.html)

    def test_causal_scope_warning_is_visible(self):
        self.assertIn("Prospective causal view.", self.html)
        self.assertIn("research_scope_warning", self.html)

    def test_dormant_backend_has_explicit_empty_state(self):
        self.assertIn("Protection Shadow API not active", self.html)
        self.assertIn("Shadow backend dormant/unavailable.", self.html)

    def test_refresh_populates_shadow_state_and_selected_settlements(self):
        self.assertIn("state.shadow=settledValue(res[16],state.shadow);", self.html)
        self.assertIn("state.shadowAdapters=settledValue(res[18],state.shadowAdapters);", self.html)
        self.assertIn(
            "if(state.selectedShadowParentId)await loadShadowSettlements",
            self.html,
        )
        self.assertIn("renderProtectionShadow()", self.html)

    def test_branch_detail_exposes_required_ps25_fields(self):
        for token in (
            "current_state",
            "dec.lane",
            "dec.action",
            "dec.reason",
            "tel.mfe_pct",
            "tel.mae_pct",
            "tel.remaining_quantity",
            "set.close_reason",
        ):
            self.assertIn(token, self.html)

    def test_shadow_css_has_responsive_branch_grid(self):
        self.assertIn(".shadow-detail-grid{display:grid;grid-template-columns:repeat(4", self.html)
        self.assertIn("@media(max-width:700px)", self.html)

    @unittest.skipUnless(shutil.which("node"), "node runtime not available")
    def test_inline_javascript_passes_node_syntax_check(self):
        match = re.search(r"<script>(.*)</script>", self.html, flags=re.S)
        self.assertIsNotNone(match)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(match.group(1))
            name = fh.name
        proc = subprocess.run(
            ["node", "--check", name],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
