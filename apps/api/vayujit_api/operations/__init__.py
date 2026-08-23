"""Owner-scoped operational read models."""


def __getattr__(name: str):
    if name == "BackupRecord":
        from vayujit_api.operations.models import BackupRecord

        return BackupRecord
    raise AttributeError(name)


__all__ = ["BackupRecord"]
