from pathlib import Path


def test_navigation_registers_separate_content_crm_without_removing_biblioteca():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")

    assert '("CRM de contenido", "ContentCRM")' in source
    assert "self._build_content_crm_frame()" in source
    assert "def refresh_content_crm_roots(self):" in source
    assert "def show_content_crm_detail(self, root_id):" in source
