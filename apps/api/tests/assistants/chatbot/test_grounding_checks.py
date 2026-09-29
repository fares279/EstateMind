from django.test import SimpleTestCase

from estatemind.assistants.chatbot.services.hallucination_guard import HallucinationGuard
from estatemind.assistants.chatbot.services.response_quality_monitor import ResponseQualityMonitor


def _grounded(text, context):
    return HallucinationGuard().validate_response(text, context)['is_grounded']


class HallucinationGuardTests(SimpleTestCase):
    def test_small_numbers_are_not_matched_within_ten(self):
        # the old check accepted any number within 10 of a retrieved value
        self.assertFalse(_grounded('Prices rose 5% last year.', {'growth_pct': 12.0}))
        self.assertFalse(_grounded('There are 3 listings.', {'listing_count': 11}))

    def test_rounded_values_are_grounded(self):
        self.assertTrue(_grounded('The median is 3,423 TND/m².', {'median_price_per_sqm': 3423.4}))
        self.assertTrue(_grounded('Growth of 4.2% is forecast.', {'growth_pct_12m': 4.18}))
        self.assertTrue(_grounded('About 1,850 TND per m².', {'ppm': 1850}))

    def test_thousands_separator_is_not_a_decimal_point(self):
        # '1,850' used to be read as 1.85
        self.assertFalse(_grounded('About 1,850 TND per m².', {'ppm': 1.85}))

    def test_percent_of_a_stored_fraction(self):
        self.assertTrue(_grounded('Yield is 5.2%.', {'gross_yield': 0.052}))

    def test_large_numbers_need_to_be_close(self):
        self.assertTrue(_grounded('Estimated at 394,989 TND.', {'price': 394989}))
        self.assertFalse(_grounded('Estimated at 420,000 TND.', {'price': 394989}))


class SourceAttributionTests(SimpleTestCase):
    def test_source_tag_is_recognised(self):
        # the pattern had a capital S and was run on lower-cased text, so it never matched
        monitor = ResponseQualityMonitor()
        self.assertTrue(monitor._check_source_attribution('Median 3,423 TND/m². [Source: EstateMind listings]'))
        self.assertFalse(monitor._check_source_attribution('Prices are high.'))


class GuardUnitsAndSignsTests(SimpleTestCase):
    def test_durations_and_scales_are_not_statistics(self):
        self.assertTrue(_grounded('A rising 12-month outlook (4.0%).', {'growth_pct_12m': 4.0}))
        self.assertTrue(_grounded('Opportunity score 39/100.', {'score': 39}))

    def test_negative_figures_keep_their_sign(self):
        self.assertTrue(_grounded('The forecast projects -8.7% change.', {'growth_pct_12m': -8.7}))
        self.assertFalse(_grounded('The forecast projects -8.7% change.', {'growth_pct_12m': 8.7}))
