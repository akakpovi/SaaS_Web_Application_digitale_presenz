import logging
from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def generate_report(self, report_id: str) -> dict:
    """Generate report data for a given Report instance."""
    from reports.models import Report
    from reports.services import generate_report_data

    try:
        report = Report.objects.select_related("website", "user").get(id=report_id)
        report.status = Report.Status.PENDING
        report.save(update_fields=["status", "updated_at"])

        data = generate_report_data(
            report.website, report.period_start, report.period_end
        )

        for field, value in data.items():
            setattr(report, field, value)

        report.status = Report.Status.GENERATED
        report.generated_at = timezone.now()
        report.save()

        logger.info(
            "Report %s generated successfully for %s", report_id, report.website.domain
        )
        return {"status": "generated", "report_id": str(report_id)}

    except Report.DoesNotExist:
        logger.error("Report %s not found", report_id)
        return {"error": "not_found"}
    except Exception as exc:
        logger.exception("generate_report failed for %s", report_id)
        try:
            from reports.models import Report

            Report.objects.filter(id=report_id).update(status=Report.Status.FAILED)
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(name="reports.tasks.generate_monthly_reports")
def generate_monthly_reports() -> dict:
    """
    Beat task: generate monthly reports for all active websites.
    Runs on the 1st of each month.
    """
    from datetime import date
    from reports.models import Report
    from websites.models import Website

    today = date.today()
    # Previous month
    first_of_this_month = today.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)

    websites = Website.objects.filter(is_active=True).select_related("owner")
    created = 0

    for website in websites:
        report, was_created = Report.objects.get_or_create(
            website=website,
            period=Report.Period.MONTHLY,
            period_start=first_of_prev_month,
            defaults={
                "user": website.owner,
                "period_end": last_of_prev_month,
                "status": Report.Status.PENDING,
            },
        )
        if was_created:
            generate_report.delay(str(report.id))
            created += 1

    logger.info("generate_monthly_reports: created %d reports", created)
    return {"created": created}
