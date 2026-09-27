import pandas as pd
from django.test import SimpleTestCase

from estatemind.intelligence.valuation.inference.location import normalize_city, normalize_governorate
from ml.shared import listings_dataset as lds


class LocationNormalizationTests(SimpleTestCase):
    def test_messy_governorate_values(self):
        self.assertEqual(normalize_governorate('Benarous'), 'ben arous')
        self.assertEqual(normalize_governorate('3100 KAIROUAN (ka)'), 'kairouan')
        self.assertEqual(normalize_governorate('Ain Zaghouan Nord à La Marsa'), 'tunis')
        self.assertEqual(normalize_governorate('Gabs', 'Gabs Sud'), 'gabes')
        self.assertEqual(normalize_governorate('Médenine'), 'medenine')

    def test_city_resolves_governorate_when_field_is_junk(self):
        self.assertEqual(normalize_governorate('2', 'Ariana Ville'), 'ariana')
        self.assertEqual(normalize_governorate('Autres villes', 'Hammamet'), 'nabeul')

    def test_unresolvable_is_unknown(self):
        self.assertEqual(normalize_governorate('', 'Atlantis'), 'unknown')
        self.assertEqual(normalize_city(''), 'unknown')


def _row(**kw):
    base = dict(record_id='r', description='x', transaction_type='sale', property_type='Appartement',
                price_tnd=200_000.0, surface_m2=100.0, price_per_m2=2000.0, rooms=3.0, bedrooms=2.0,
                bathrooms=1.0, governorate='Tunis', city='La Marsa', location_raw='', latitude=36.9,
                longitude=10.3)
    base.update(kw)
    return base


class DatasetRuleTests(SimpleTestCase):
    def test_cleaning_rules_are_applied_and_counted(self):
        raw = pd.DataFrame([
            _row(),
            _row(transaction_type='rent'),
            _row(price_tnd=900.0),                       # rent posted as sale
            _row(surface_m2=5.0, price_tnd=50_000.0),    # implausible surface
            _row(),                                      # duplicate of the first
            _row(property_type='Terrain', surface_m2=500.0, price_tnd=150_000.0, bedrooms=0.0),
        ])
        df, card = lds.clean(raw)
        self.assertEqual(len(df), 2)
        self.assertEqual(card['removed'], {'not_sale_or_other_type': 1, 'price_out_of_range': 1,
                                           'surface_out_of_range': 1, 'price_per_m2_out_of_range': 0,
                                           'duplicate_listing': 1})
        apt = df[df['property_type'] == 'appartement'].iloc[0]
        self.assertEqual((apt['governorate'], apt['city']), ('tunis', 'la marsa'))
        self.assertEqual(apt['rooms'], 3)            # bedrooms + 1, as serving derives it
        land = df[df['property_type'] == 'terrain'].iloc[0]
        self.assertEqual(land['rooms'], 0)

    def test_priors_come_from_training_rows_only(self):
        train = pd.DataFrame({'property_type': ['appartement'] * 3, 'city': ['a'] * 3, 'governorate': ['g'] * 3,
                              'price_per_m2': [1000.0, 2000.0, 3000.0]})
        priors = lds.fit_priors(train)['appartement__sale']
        self.assertEqual(priors['city_governorate_price_m2'], {'a__g': 2000.0})
        feats = lds.add_features(pd.DataFrame({'property_type': ['appartement'], 'city': ['b'], 'governorate': ['g'],
                                               'surface_m2': [50.0]}), {'appartement__sale': priors})
        self.assertEqual(feats.iloc[0]['local_avg_price_m2'], 2000.0)   # unseen city -> governorate prior
        self.assertEqual(feats.iloc[0]['size_x_local_price'], 100_000.0)

    def test_real_dataset_split_has_no_shared_listing(self):
        ds = lds.build()
        self.assertEqual(ds.card['listings_in_both_splits'], 0)
        self.assertEqual(set(ds.train.columns) >= set(lds.FEATURES), True)
        self.assertLess(abs(ds.card['test_rows'] / ds.card['output_rows'] - lds.TEST_SHARE), 0.02)


class TrainServeConsistencyTests(SimpleTestCase):
    """Models from ml.valuation.train_catboost_bundle must predict the same through
    the serving path (raw API-style inputs) as on the training feature frame."""

    def test_served_prediction_matches_training_features(self):
        import numpy as np

        from config.paths import ARTIFACTS_DIR
        from estatemind.intelligence.valuation.inference.model_registry import ModelHandle, ModelRegistry
        from estatemind.intelligence.valuation.inference.request_mapper import map_request

        dirs = sorted((ARTIFACTS_DIR / 'valuation' / 'models').glob('estate_v2_*'))
        if not dirs:
            self.skipTest('no trained v2 valuation models on disk')
        ds = lds.build()
        api_type = {'appartement': 'apartment', 'maison': 'house', 'terrain': 'land'}
        for ptype, api in api_type.items():
            path = dirs[-1] / f'bytype__{ptype}__catboost.joblib'
            handle = ModelRegistry().maybe_load_bundle(
                ModelHandle(scope='by_type', property_type=ptype, model_name='catboost', path=path, metrics={}))
            X, _, part = ds.xy('test', ptype)
            X, part = X.head(25), part.head(25)
            direct = np.expm1(handle.estimator.predict(X[lds.FEATURES]))
            served = [handle.bundle.predict(map_request({
                'property_type': api, 'governorate': r['governorate_raw'], 'city': r['city_raw'],
                'size_m2': r['surface_m2'], 'bedrooms': r['bedrooms'], 'bathrooms': r['bathrooms'],
                'latitude': r['latitude'], 'longitude': r['longitude']}), {'avg_price_per_m2': None}).estimated_price
                for _, r in part.iterrows()]
            np.testing.assert_allclose(served, direct, rtol=0.005, err_msg=ptype)
