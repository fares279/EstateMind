import datetime as dt

from django.test import SimpleTestCase, TestCase

from estatemind.intelligence.valuation.models import ValuationModelVersion as V
from estatemind.intelligence.valuation.services.model_registry import (
    ValuationModelRegistry,
    artifact_family,
    registry_key,
)


class RegistryKeyTests(SimpleTestCase):
    def test_english_and_french_names_share_a_key(self):
        self.assertEqual(registry_key('apartment'), 'valuation:appartement')
        self.assertEqual(registry_key('Appartement'), 'valuation:appartement')
        self.assertEqual(registry_key('house'), 'valuation:maison')
        self.assertEqual(registry_key('villa'), 'valuation:maison')
        self.assertEqual(registry_key('land'), 'valuation:terrain')
        self.assertEqual(registry_key('all'), 'valuation:global')

    def test_artifact_family(self):
        self.assertEqual(artifact_family('valuation/models/models_estateprocessor/bytype__maison__et.joblib'), 'et')
        self.assertEqual(artifact_family(r'C:\x\global__catboost.joblib'), 'catboost')
        self.assertEqual(artifact_family('valuation/valuation_model.joblib'), 'catboost')


def _version(key, version, status, pct, artifact='valuation/models/models_estateprocessor/bytype__appartement__catboost.joblib'):
    return V.objects.create(model_name=key, version=version, artifact_path=artifact, training_date=dt.date(2026, 1, 1),
                            training_data_hash='', status=status, ab_traffic_pct=pct)


class RegistrySelectionTests(TestCase):
    def setUp(self):
        self.reg = ValuationModelRegistry()
        self.champ = _version('valuation:appartement', 'a', 'champion', 100)

    def test_champion_serves_and_handle_matches_discovery_shape(self):
        handle, version = self.reg.get_active_model('apartment')
        self.assertEqual(version, self.champ)
        self.assertEqual((handle.scope, handle.property_type, handle.model_name), ('by_type', 'appartement', 'catboost'))

    def test_zero_traffic_challenger_is_never_served(self):
        _version('valuation:appartement', 'b', 'challenger', 0)
        for user_id in (0, 5, 99):
            self.assertEqual(self.reg.get_active_model('appartement', user_id=user_id)[1], self.champ)

    def test_challenger_gets_its_traffic_share(self):
        chal = _version('valuation:appartement', 'b', 'challenger', 30)
        self.assertEqual(self.reg.get_active_model('appartement', user_id=129)[1], chal)   # 29 < 30
        self.assertEqual(self.reg.get_active_model('appartement', user_id=130)[1], self.champ)
        self.assertEqual(self.reg.get_active_model('appartement')[1], self.champ)          # anonymous

    def test_scope_without_champion_uses_global_champion(self):
        glob = _version('valuation:global', 'g', 'champion', 100,
                        artifact='valuation/models/models_estateprocessor/global__catboost.joblib')
        handle, version = self.reg.get_active_model('commercial')
        self.assertEqual(version, glob)
        self.assertEqual((handle.scope, handle.property_type), ('global', 'all'))

    def test_promote_only_retires_the_same_scope(self):
        other = _version('valuation:maison', 'm', 'champion', 100,
                         artifact='valuation/models/models_estateprocessor/bytype__maison__catboost.joblib')
        new = _version('valuation:appartement', 'b', 'challenger', 0)
        self.reg.promote(new.id, promoted_by='test')
        self.champ.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.champ.status, 'retired')
        self.assertEqual(other.status, 'champion')
        self.assertEqual(self.reg.get_active_model('appartement')[1].id, new.id)

    def test_register_challenger_keeps_explicit_zero_traffic(self):
        v = self.reg.register_challenger(artifact_path='x.joblib', model_name='valuation:appartement', version='z',
                                         ab_traffic_pct=0)
        self.assertEqual(v.ab_traffic_pct, 0)


class RegistrySyncTaskTests(TestCase):
    def test_one_champion_per_scope_and_idempotent(self):
        from estatemind.intelligence.valuation.tasks import sync_registry_from_artifacts
        first = sync_registry_from_artifacts.apply().result
        if not first['created']:
            self.skipTest('no valuation artifacts on disk')
        champions = list(V.objects.filter(status='champion').values_list('model_name', flat=True))
        self.assertEqual(len(champions), len(set(champions)))
        self.assertFalse(V.objects.filter(status='challenger', ab_traffic_pct__gt=0).exists())
        self.assertEqual(sync_registry_from_artifacts.apply().result['created'], 0)
