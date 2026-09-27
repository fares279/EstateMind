"""Key ValuationModelVersion rows by the scope they serve ('valuation:<scope>').

Rows were named after the model family ('catboost', 'et') or 'CatBoost_<Type>'
while serving looked up 'CatBoost_<Type>' from the French property type, so
serving never used the registry. Each row gets the key of the scope its
artifact serves. Each scope keeps one champion: an existing champion if there
is one, otherwise the CatBoost artifact (what artifact discovery serves).
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
        champions = [r for r, _ in entries if r.status == 'champion']
        if champions:
            keep = max(champions, key=lambda r: (r.promoted_at is not None, r.promoted_at, r.created_at))
        else:
            live = [(r, f) for r, f in entries if r.status in ('champion', 'challenger')]
            catboost = [r for r, f in live if f == 'catboost']
            keep = (catboost or [r for r, _ in live] or [None])[0]
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
