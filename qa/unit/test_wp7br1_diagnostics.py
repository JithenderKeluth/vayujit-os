import json
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from qa.wp7br1_diagnostics import safe_exception


def test_diagnostics_do_not_serialize_sensitive_sql_or_exception_text():
    original = RuntimeError("PRIVATE_KEY password secret content")
    original.sqlstate = "23505"
    original.diag = SimpleNamespace(constraint_name="uq_ad_performance_anomaly_fingerprint")
    error = IntegrityError("SECRET SQL", {"password": "NEVER_PRINT"}, original)
    value = safe_exception(error)
    assert value["exception_type"] == "IntegrityError"
    assert value["sqlstate"] == "23505"
    assert value["constraint"] == "uq_ad_performance_anomaly_fingerprint"
    assert value["raw_error_persisted"] is False
    assert all(
        secret not in json.dumps(value)
        for secret in ["PRIVATE_KEY", "password", "SECRET SQL", "NEVER_PRINT"]
    )
    original.diag.constraint_name = "secret_password_constraint"
    assert safe_exception(error)["constraint"] is None


def test_unknown_exception_class_is_not_arbitrary_output():
    assert safe_exception(RuntimeError("secret"))["exception_type"] == "OTHER_EXCEPTION"
