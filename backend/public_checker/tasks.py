from celery import shared_task

@shared_task(name="public_checker.run_public_scan")
def run_public_scan(domain: str, scan_id: str):
    pass
