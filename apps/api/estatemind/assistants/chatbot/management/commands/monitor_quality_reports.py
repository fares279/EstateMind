"""
Django management command to monitor and display daily quality reports.

Usage:
    python manage.py monitor_quality_reports --days=7 --daily
    python manage.py monitor_quality_reports --latest
    python manage.py monitor_quality_reports --alerts
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from estatemind.assistants.chatbot.models import (
    ResponseQualityDailyReport,
    IntentAccuracyMetric,
    RewardModelVersion,
    ChatbotResponseLog
)


class Command(BaseCommand):
    help = "Monitor daily quality reports and metrics"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Show reports for last N days (default: 7)'
        )
        parser.add_argument(
            '--daily',
            action='store_true',
            help='Show daily detail breakdown'
        )
        parser.add_argument(
            '--latest',
            action='store_true',
            help='Show latest report only'
        )
        parser.add_argument(
            '--alerts',
            action='store_true',
            help='Show only alerts and anomalies'
        )
        parser.add_argument(
            '--trends',
            action='store_true',
            help='Show trends and forecasts'
        )

    def handle(self, *args, **options):
        days = options['days']
        show_daily = options['daily']
        latest_only = options['latest']
        alerts_only = options['alerts']
        show_trends = options['trends']

        if latest_only:
            self._show_latest_report()
        elif alerts_only:
            self._show_alerts()
        elif show_trends:
            self._show_trends(days)
        elif show_daily:
            self._show_daily_breakdown(days)
        else:
            self._show_summary(days)

    def _show_latest_report(self):
        """Show the latest daily quality report"""
        self.stdout.write("\n📊 LATEST DAILY QUALITY REPORT\n")

        latest = ResponseQualityDailyReport.objects.latest('report_date')

        self.stdout.write(f"Generated: {latest.generated_at}")
        self.stdout.write(f"Report Date: {latest.report_date}\n")

        self.stdout.write("RESPONSE METRICS:")
        self.stdout.write(f"  Total responses: {latest.total_responses}")
        self.stdout.write(f"  Good (≥0.85): {latest.good_count} ({100*latest.good_count/latest.total_responses if latest.total_responses else 0:.1f}%)")
        self.stdout.write(f"  Acceptable (0.70-0.85): {latest.acceptable_count} ({100*latest.acceptable_count/latest.total_responses if latest.total_responses else 0:.1f}%)")
        self.stdout.write(f"  Poor (<0.70): {latest.poor_count} ({100*latest.poor_count/latest.total_responses if latest.total_responses else 0:.1f}%)")

        self.stdout.write("\nDIMENSION SCORES:")
        self.stdout.write(f"  Relevance:     {latest.avg_relevance_score:.3f} (target: ≥0.65)")
        self.stdout.write(f"  Groundedness:  {latest.avg_groundedness_score:.3f} (target: ≥0.80)")
        self.stdout.write(f"  Length OK:     {100*latest.avg_length_score:.1f}% (target: ≥95%)")
        self.stdout.write(f"  Attribution:   {latest.avg_attribution_score:.3f} (target: ≥0.85)")

        self.stdout.write(f"\nOVERALL SCORE: {latest.avg_overall_score:.3f}/1.0 (target: ≥0.70)")

        self.stdout.write(f"\nGROUNDING STATUS:")
        self.stdout.write(f"  Fully grounded:    {latest.fully_grounded_count} responses")
        self.stdout.write(f"  With disclaimers:  {latest.total_responses - latest.fully_grounded_count} responses")
        self.stdout.write(f"  Grounding rate:    {latest.grounding_rate:.1%} (target: ≥90%)")

        # Feedback stats
        feedback_stat = ChatbotResponseLog.objects.filter(
            created_at__date=latest.report_date
        ).exclude(user_feedback__isnull=True)

        if feedback_stat.exists():
            thumbs_up = feedback_stat.filter(user_feedback='thumbs_up').count()
            thumbs_down = feedback_stat.filter(user_feedback='thumbs_down').count()
            total_feedback = thumbs_up + thumbs_down
            self.stdout.write(f"\nUSER FEEDBACK:")
            self.stdout.write(f"  👍 Thumbs up:   {thumbs_up}")
            self.stdout.write(f"  👎 Thumbs down: {thumbs_down}")
            if total_feedback > 0:
                self.stdout.write(f"  Positive ratio: {100*thumbs_up/total_feedback:.1f}%")

    def _show_summary(self, days):
        """Show summary report for last N days"""
        self.stdout.write(f"\n📊 QUALITY METRICS SUMMARY (Last {days} Days)\n")

        cutoff = timezone.now().date() - timedelta(days=days)
        reports = ResponseQualityDailyReport.objects.filter(
            report_date__gte=cutoff
        ).order_by('report_date')

        if not reports.exists():
            self.stdout.write("No reports available for this period")
            return

        # Calculate averages
        avg_overall = sum(r.avg_overall_score for r in reports) / len(reports)
        avg_grounding = sum(r.grounding_rate for r in reports) / len(reports)
        avg_good_pct = sum(r.good_count/r.total_responses for r in reports if r.total_responses) / len(reports)

        self.stdout.write("PERIOD AVERAGES:")
        self.stdout.write(f"  Overall Quality Score: {avg_overall:.3f}/1.0")
        self.stdout.write(f"  Grounding Rate: {avg_grounding:.1%}")
        self.stdout.write(f"  Good Responses: {100*avg_good_pct:.1f}%")

        # Show key days
        self.stdout.write(f"\nDAY-BY-DAY SUMMARY:")
        for report in reports:
            emoji = self._get_quality_emoji(report.avg_overall_score)
            self.stdout.write(
                f"  {emoji} {report.report_date}: "
                f"score={report.avg_overall_score:.2f}, "
                f"grounding={report.grounding_rate:.1%}, "
                f"good={report.good_count}/{report.total_responses}"
            )

    def _show_daily_breakdown(self, days):
        """Show detailed daily breakdown"""
        self.stdout.write(f"\n📊 DETAILED QUALITY BREAKDOWN (Last {days} Days)\n")

        cutoff = timezone.now().date() - timedelta(days=days)
        reports = ResponseQualityDailyReport.objects.filter(
            report_date__gte=cutoff
        ).order_by('report_date')

        for report in reports:
            self.stdout.write(f"\n{report.report_date} ({report.generated_at.strftime('%H:%M:%S')})")
            self.stdout.write("─" * 70)

            self.stdout.write(f"  Responses:     {report.total_responses:4d}")
            self.stdout.write(f"    Good:        {report.good_count:4d} ({100*report.good_count/report.total_responses if report.total_responses else 0:5.1f}%)")
            self.stdout.write(f"    Acceptable:  {report.acceptable_count:4d} ({100*report.acceptable_count/report.total_responses if report.total_responses else 0:5.1f}%)")
            self.stdout.write(f"    Poor:        {report.poor_count:4d} ({100*report.poor_count/report.total_responses if report.total_responses else 0:5.1f}%)")

            self.stdout.write(f"\n  Scores:")
            self.stdout.write(f"    Relevance:      {report.avg_relevance_score:.3f}")
            self.stdout.write(f"    Groundedness:   {report.avg_groundedness_score:.3f}")
            self.stdout.write(f"    Attribution:    {report.avg_attribution_score:.3f}")
            self.stdout.write(f"    Overall:        {report.avg_overall_score:.3f}")

            self.stdout.write(f"\n  Grounding:     {report.grounding_rate:.1%} ({report.fully_grounded_count} fully grounded)")

    def _show_alerts(self):
        """Show only alerts and anomalies"""
        self.stdout.write("\n🚨 ALERTS & ANOMALIES\n")

        latest = ResponseQualityDailyReport.objects.latest('report_date')

        alerts = []

        # Check quality score
        if latest.avg_overall_score < 0.70:
            alerts.append(
                (2, f"❌ Quality score {latest.avg_overall_score:.2f} below target 0.70")
            )
        elif latest.avg_overall_score < 0.75:
            alerts.append(
                (1, f"⚠️  Quality score {latest.avg_overall_score:.2f} approaching target")
            )

        # Check grounding rate
        if latest.grounding_rate < 0.85:
            alerts.append(
                (2, f"❌ Grounding rate {latest.grounding_rate:.1%} below target 90%")
            )
        elif latest.grounding_rate < 0.90:
            alerts.append(
                (1, f"⚠️  Grounding rate {latest.grounding_rate:.1%} approaching target")
            )

        # Check relevance
        if latest.avg_relevance_score < 0.65:
            alerts.append(
                (2, f"❌ Relevance score {latest.avg_relevance_score:.2f} below target")
            )

        # Check groundedness
        if latest.avg_groundedness_score < 0.80:
            alerts.append(
                (2, f"❌ Groundedness score {latest.avg_groundedness_score:.2f} below target")
            )

        # Check intent accuracy
        try:
            latest_accuracy = IntentAccuracyMetric.objects.latest('evaluated_at')
            if latest_accuracy.accuracy < 0.80:
                alerts.append(
                    (2, f"❌ Intent accuracy {latest_accuracy.accuracy:.1%} below target 80%")
                )
            elif latest_accuracy.accuracy < 0.82:
                alerts.append(
                    (1, f"⚠️  Intent accuracy {latest_accuracy.accuracy:.1%} slightly below 82.5% baseline")
                )
        except:
            pass

        if not alerts:
            self.stdout.write("✅ No alerts. All metrics within target ranges.")
            return

        # Sort by severity (2=critical, 1=warning)
        alerts.sort(key=lambda x: -x[0])

        self.stdout.write(f"Found {len(alerts)} alert(s):\n")
        for severity, message in alerts:
            self.stdout.write(message)

    def _show_trends(self, days):
        """Show trends and forecasts"""
        self.stdout.write(f"\n📈 TREND ANALYSIS (Last {days} Days)\n")

        cutoff = timezone.now().date() - timedelta(days=days)
        reports = ResponseQualityDailyReport.objects.filter(
            report_date__gte=cutoff
        ).order_by('report_date')

        if len(reports) < 3:
            self.stdout.write("Not enough data for trend analysis (need ≥3 days)")
            return

        scores = [r.avg_overall_score for r in reports]
        grounding_rates = [r.grounding_rate for r in reports]

        # Calculate trend
        score_trend = "↑" if scores[-1] > scores[0] else "↓" if scores[-1] < scores[0] else "→"
        grounding_trend = "↑" if grounding_rates[-1] > grounding_rates[0] else "↓" if grounding_rates[-1] < grounding_rates[0] else "→"

        self.stdout.write("OVERALL QUALITY SCORE:")
        self.stdout.write(f"  Start: {scores[0]:.3f}")
        self.stdout.write(f"  End:   {scores[-1]:.3f}")
        self.stdout.write(f"  Trend: {score_trend} ({scores[-1] - scores[0]:+.3f})")

        self.stdout.write("\nGROUNDING RATE:")
        self.stdout.write(f"  Start: {grounding_rates[0]:.1%}")
        self.stdout.write(f"  End:   {grounding_rates[-1]:.1%}")
        self.stdout.write(f"  Trend: {grounding_trend} ({(grounding_rates[-1] - grounding_rates[0])*100:+.1f}pp)")

        # Forecast
        if len(scores) >= 7:
            recent_trend = sum((scores[i+1] - scores[i] for i in range(-3, 0))) / 3
            forecast_7d = scores[-1] + (recent_trend * 7)
            self.stdout.write(f"\nFORECAST (7 days out):")
            self.stdout.write(f"  Projected score: {forecast_7d:.3f}")
            if forecast_7d < 0.70:
                self.stdout.write("  🚨 WARNING: Projected score below target!")

    def _get_quality_emoji(self, score):
        """Get emoji for quality score"""
        if score >= 0.85:
            return "🟢"
        elif score >= 0.70:
            return "🟡"
        else:
            return "🔴"
