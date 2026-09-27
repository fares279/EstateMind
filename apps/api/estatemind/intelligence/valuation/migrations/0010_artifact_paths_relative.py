"""Store ValuationModelVersion.artifact_path relative to ARTIFACTS_DIR.

Rows written before this held absolute paths from the machine that trained
the model (e.g. C:\\Users\\...\\backend\\valuation\\artifacts\\models\\...),
which do not exist on any other machine or container. Paths that can be
mapped into ARTIFACTS_DIR are rewritten; anything else is left unchanged.
ValuationRequest.model_artifact is a historical record and is not touched.
"""
from django.db import migrations


def relativise(apps, schema_editor):
    from config.paths import ARTIFACTS_DIR, resolve_artifact_ref, to_artifact_ref

    ValuationModelVersion = apps.get_model("valuation", "ValuationModelVersion")
    alias = schema_editor.connection.alias
    root = ARTIFACTS_DIR.resolve()
    for row in ValuationModelVersion.objects.using(alias).all():
        resolved = resolve_artifact_ref(row.artifact_path)
        try:
            resolved.resolve().relative_to(root)
        except ValueError:
            continue  # outside ARTIFACTS_DIR: leave as is
        ref = to_artifact_ref(resolved)
        if ref != row.artifact_path:
            row.artifact_path = ref
            row.save(update_fields=["artifact_path"])


class Migration(migrations.Migration):

    dependencies = [
        ("valuation", "0009_remove_delegationforecast_moved_to_forecast"),
    ]

    operations = [
        migrations.RunPython(relativise, migrations.RunPython.noop),
    ]
