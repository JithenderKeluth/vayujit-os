"""Pure filesystem/native-pipeline tests; never contacts Docker or a database."""

import hashlib
import importlib.util
import io
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def module():
    source = (
        Path(__file__).resolve().parents[2] / "scripts/local_migration_rehearsal.py"
    )
    spec = importlib.util.spec_from_file_location("local_rehearsal", source)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.mark.parametrize("path", ["C:/data", "C:/data/sub", "C:/"])
def test_backup_cannot_overlap_source_storage(module, path):
    assert not module.outside(Path(path), [Path("C:/data")])


def test_backup_folder_with_spaces_is_supported(module):
    assert module.outside(Path("C:/vayujit-os db encr bkp"), [Path("C:/data")])


def test_only_known_created_container_id_and_exact_marker_can_be_cleaned(module):
    meta = {"id": "created-id", "label": {module.LABEL: "token"}}
    assert module.owned_container(meta, "token", "created-id")
    assert not module.owned_container(meta, "token", None)
    assert not module.owned_container(meta, "other", "created-id")
    assert not module.owned_container(meta, "token", "other-id")


def test_rehearsal_preservation_projection_maps_only_known_version_names(module):
    sql = module.fingerprint_sql(
        "video_generations", ["id", "storyboardversion"], migrated=True
    )
    assert '"storyboard_version" AS "storyboardversion"' in sql
    assert sql.startswith("SELECT")
    assert '"storyboard_version"' not in module.fingerprint_sql(
        "other", ["storyboardversion"], migrated=True
    )
    assert module.quote('a"; DROP DATABASE other;--') == '"a""; DROP DATABASE other;--"'


def test_native_pipeline_preserves_non_utf8_bytes_and_hash(module):
    output = io.BytesIO()
    data = b"\x00\xff\x80PGDMP\r\n"
    result = module.transfer(
        [sys.executable, "-c", f"import sys;sys.stdout.buffer.write({data!r})"],
        None,
        output_file=output,
    )
    assert output.getvalue() == data
    assert result == {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def test_successful_native_stderr_is_not_a_failure(module):
    result = module.transfer(
        [
            sys.executable,
            "-c",
            "import sys;sys.stderr.write('warning');sys.stdout.buffer.write(b'ok')",
        ],
        None,
    )
    assert result["bytes"] == 2


@pytest.mark.parametrize("side", ["producer", "consumer"])
def test_nonzero_native_exit_is_never_certified(module, side):
    producer = [sys.executable, "-c", "import sys;sys.stdout.write('data');sys.exit(7)"]
    consumer = None
    if side == "consumer":
        producer = [sys.executable, "-c", "import sys;sys.stdout.write('data')"]
        consumer = [sys.executable, "-c", "import sys;sys.stdin.read();sys.exit(9)"]
    with pytest.raises(module.SafeFailure) as error:
        module.transfer(producer, consumer)
    assert error.value.exit_code == (7 if side == "producer" else 9)


def test_owned_pipeline_timeout_fails_closed(module):
    with pytest.raises(module.SafeFailure, match="binary_transfer_timeout"):
        module.transfer(
            [sys.executable, "-c", "import time;time.sleep(5)"], None, timeout=0.2
        )


@pytest.mark.parametrize(
    "output,expected",
    [
        (
            b"password=secret postgresql://private NativeFailure",
            "native_operation_failed",
        ),
        (
            b"secret WP6A_VIDEO_VERSION_SCHEMA_UNSUPPORTED secret",
            "WP6A_VIDEO_VERSION_SCHEMA_UNSUPPORTED",
        ),
        (b"sensitive SQL UndefinedColumn data", "native_UndefinedColumn"),
    ],
)
def test_native_diagnostics_never_echo_sensitive_output(module, output, expected):
    assert module.native_failure_code(output) == expected


@pytest.mark.parametrize(
    "index,stderr,code",
    [
        (0, b"AGE-SECRET-KEY-private", "binary_producer_failed"),
        (
            1,
            b'FATAL: database "private-name" does not exist',
            "restore_database_unavailable",
        ),
        (
            1,
            b"connection: Connection refused password=private",
            "restore_connection_unavailable",
        ),
        (1, b"unsupported version customer-record", "restore_dump_version_unsupported"),
        (1, b"private customer record", "binary_consumer_failed"),
    ],
)
def test_binary_failure_diagnostics_are_allowlisted(module, index, stderr, code):
    assert module.binary_failure_code(index, stderr) == code


def test_classified_consumer_failure_retains_exit_code_without_sensitive_output(module):
    with pytest.raises(module.SafeFailure) as failure:
        module.transfer(
            [sys.executable, "-c", "print('test')"],
            [
                sys.executable,
                "-c",
                (
                    "import sys;sys.stdin.read();"
                    "sys.stderr.write('customer-secret');sys.exit(11)"
                ),
            ],
            classify_failures=True,
        )
    assert failure.value.code == "binary_consumer_failed"
    assert failure.value.exit_code == 11
    assert "customer-secret" not in str(failure.value)
