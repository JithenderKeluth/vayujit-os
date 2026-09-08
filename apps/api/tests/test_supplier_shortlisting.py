from vayujit_api.intelligence.shortlisting_service import DEFAULT_WEIGHTS, system_doctor


def test_shortlisting_contracts_are_registered() -> None:
    assert sum(DEFAULT_WEIGHTS.values()) == 100
    doctor = system_doctor()
    assert doctor["shortlisting_engine"] == "registered"
    assert doctor["external_dispatch"] == "disabled"
