from backend.services.tts_backend import _singing_capabilities_for


class MalformedSingingBackend:
    id = "malformed-singing"
    singing_capabilities = {1, "singing_conversion"}


def test_malformed_mixed_type_singing_capabilities_fail_closed() -> None:
    assert _singing_capabilities_for(MalformedSingingBackend) == []
