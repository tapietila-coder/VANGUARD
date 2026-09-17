from vanguard.core.models import IntegrationStatus
from vanguard.integrations.adapters import DispatchAdapter, MarshalAdapter, StewardAdapter, WatchtowerAdapter


def test_dispatch_adapter_degrades_gracefully_when_unreachable():
    # Nothing should be listening on this port during tests; if something legitimately
    # is, the adapter would (correctly) report CONNECTED instead — either way it must
    # not raise or fabricate data.
    adapter = DispatchAdapter(base_url="http://127.0.0.1:8799", timeout_seconds=0.5)
    report = adapter.status()
    assert report.status in (IntegrationStatus.CONNECTED, IntegrationStatus.NOT_CONNECTED)
    assert report.integration == "dispatch"


def test_stub_adapters_report_not_connected():
    for adapter_cls in (StewardAdapter, WatchtowerAdapter, MarshalAdapter):
        report = adapter_cls().status()
        assert report.status == IntegrationStatus.NOT_CONNECTED
