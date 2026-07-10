"""신규 파서(x/supermetrics) 회귀 테스트 — 실제 문서 구조 축소판으로 검증."""
from admeta.extract import supermetrics, x

# X: 첫 행이 빈 셀, 진짜 헤더는 안쪽 행 (docs.x.com 실제 구조 축소판)
_X_HTML = """
<table><tr><td></td><td></td><td></td><td></td></tr>
<tr><td>Metric</td><td>Description</td><td>Segmentation Available</td><td>Data Type</td></tr>
<tr><td>impressions</td><td>Total number of impressions</td><td>✔</td><td>Array of ints</td></tr>
<tr><td>clicks</td><td>Total clicks</td><td>✔</td><td>Array of ints</td></tr>
</table>
<table><tr><td></td><td></td></tr>
<tr><td>Derived Metric</td><td>Exposed Metric Calculation</td></tr>
<tr><td>CPM</td><td>billed_charge_local_micro/impressions/10</td></tr>
</table>
<table><tr><td></td><td></td></tr>
<tr><td>Segmentation Type</td><td>country param required</td></tr>
<tr><td>AGE</td><td></td></tr>
</table>
"""

# Supermetrics: field-table 클래스 기반 (docs.supermetrics.com 실제 구조 축소판)
_SM_HTML = """
<table class="field-list-table"><tr><td>
<table class="field-table"><tr><td class="field-name">
  <a class="field-anchor"></a>AdvertiserCostUSD<a class="field-link-icon">link</a></td></tr>
<tr><td><table class="field-metadata-table">
  <tr><td class="field-meta-label">Field label</td><td class="field-label">Advertiser cost (USD)</td></tr>
  <tr><td class="field-meta-label">Description</td><td class="field-description">Total cost in USD</td></tr>
  <tr><td class="field-meta-label">Field type</td><td>metric</td></tr>
  <tr><td class="field-meta-label">Data type</td><td><a href="#">float</a></td></tr>
</table></td></tr></table>
</td></tr></table>
"""


def test_x_parses_metric_table_with_inner_header():
    fields = {f.api_name: f for f in x.parse(_X_HTML)}
    assert "impressions" in fields and "clicks" in fields
    assert fields["impressions"].description == "Total number of impressions"
    assert fields["impressions"].category == "metric"
    assert fields["impressions"].data_type == "Array of ints"


def test_x_skips_derived_metric_table():
    names = [f.api_name for f in x.parse(_X_HTML)]
    assert "CPM" not in names
    assert not any("/" in n for n in names), "계산식이 필드명으로 새면 안 됨"


def test_x_segmentation_table_is_dimension():
    fields = {f.api_name: f for f in x.parse(_X_HTML)}
    assert fields["AGE"].category == "dimension"


def test_supermetrics_parses_field_table():
    fields = supermetrics.parse(_SM_HTML)
    assert len(fields) == 1
    f = fields[0]
    assert f.api_name == "AdvertiserCostUSD"          # 링크 아이콘 텍스트 미포함
    assert f.display_name == "Advertiser cost (USD)"
    assert f.description == "Total cost in USD"
    assert f.category == "metric"
    assert f.data_type == "float"
