from django.test import SimpleTestCase

from estatemind.intelligence.forecast.services import national_index as ni


class NationalIndexTests(SimpleTestCase):
    def test_series_covers_2000_to_2025(self):
        series = ni._series()['apartment']
        self.assertEqual(series[0][:2], (2000, 1))
        self.assertGreaterEqual(series[-1][:2], (2025, 4))

    def test_chosen_method_beats_the_flat_trend_for_every_type(self):
        for ptype in ni.SERIES:
            mae = ni.backtest(ptype)['mae_12m_pp']
            self.assertEqual(min(mae, key=mae.get), ni.CHOSEN, ptype)
            self.assertLess(mae[ni.CHOSEN], mae['flat'])

    def test_interval_widens_with_the_horizon(self):
        widths = [ni.interval_halfwidth('apartment', m) for m in (0, 1, 6, 11)]
        self.assertEqual(widths[0], 0.0)
        self.assertEqual(widths, sorted(widths))
        self.assertLess(widths[-1], 0.25)
