import logging
from django.utils import timezone
from .models import Report
import io

# class DatabaseLogHandler(logging.Handler):

#     def emit(self, record):
#         log_entry = LogEntry(
#             logger_name=record.name,
#             level=record.levelname,
#             message=self.format(record),
#             timestamp=timezone.now()
#         )
#         log_entry.save()

class JobLogHandler(logging.StreamHandler):

    def __init__(self, job_logs):
        super().__init__()
        self.job_logs = job_logs

    def emit(self, record):
        job_name = record.name.split(".")[-1]
        if job_name not in self.job_logs:
            self.job_logs[job_name] = io.StringIO()

        log_entry = self.format(record)
        self.job_logs[job_name].write(log_entry + "\n")

class ReportLogHandler(logging.Handler):

    def emit(self, record):
        report_id = getattr(record, 'report_id', None)
        if report_id is not None:
            try:
                report = Report.objects.get(pk=report_id)
                report.comment += self.format(record) + '\n'
                report.save()
            except Report.DoesNotExist:
                pass
            