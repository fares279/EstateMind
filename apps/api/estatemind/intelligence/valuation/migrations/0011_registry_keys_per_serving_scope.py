"""Key ValuationModelVersion rows by the scope they serve ('valuation:<scope>').

Rows were named after the model family ('catboost', 'et') or 'CatBoost_<Type>'
while serving looked up 'CatBoost_<Type>' from the French property type, so
serving never used the registry. Each row gets the key of the scope its
artifact serves. A scope keeps its existing champion, if any; nothing is
promoted (sync_registry_from_artifacts registers what discovery serves).
Other versions become 0%-traffic challengers — none of them was ever served.
"""
from pathlib import Path

from django.db import migrations

ALIASES = {'apartment': 'appartement', 'house': 'maison', 'land': 'terrain', 'villa': 'maison',
           'commercial': 'commercial', 'all': 'global'}


def _scope_and_family(row):
    stem = Path(row.artifact_path.replace('\\', '/')).stem.lower()
    parts = stem.split('__')
    if stem.startswith('bytype__') and len(parts) >= 3:
        return parts[1], parts[2]
    if stem.startswith('global__'):
        return 'global', parts[1] if len(parts) >= 2 else 'catboost'
    name = row.model_name.lower().replace('catboost_', '').replace('valuation:', '')
    return ALIASES.get(name, name or 'appartement'), 'catboost'


def rekey(apps, schema_editor):
    Version = apps.get_model('valuation', 'ValuationModelVersion')
    alias = schema_editor.connection.alias
    rows = list(Version.objects.using(alias).order_by('created_at', 'id'))
    by_key = {}
    for row in rows:
        scope, family = _scope_and_family(row)
        row.model_name = f'valuation:{scope}'
        by_key.setdefault(row.model_name, []).append((row, family))

    for key, entries in by_key.items():
        # Never promote here: a scope without a champion keeps none, and serving falls
        # back to artifact discovery (the same files the old champions were). Promoting
        # 'the CatBoost row' turned unapproved 0%-traffic challengers into champions.
        champions = [r for r, _ in entries if r.status == 'champion']
        keep = max(champions, key=lambda r: (r.promoted_at is not None, r.promoted_at, r.created_at)) \
            if champions else None
        for row, _ in entries:
            if row is keep:
                row.status, row.ab_traffic_pct = 'champion', 100
            elif row.status in ('champion', 'challenger'):
                row.status, row.ab_traffic_pct = 'challenger', 0
            row.save(update_fields=['model_name', 'status', 'ab_traffic_pct'])


class Migration(migrations.Migration):

    dependencies = [
        ("valuation", "0010_artifact_paths_relative"),
    ]

    operations = [
        migrations.RunPython(rekey, migrations.RunPython.noop),
    ]
