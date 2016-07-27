from django.db.models import Func, IntegerField


class DayOfWeek(Func):
    function = 'DAYOFWEEK'
    output_field=IntegerField()

    def as_sqlite(self, *args, **kwargs):
        self.template = "CAST (STRFTIME('%%w', %(expressions)s) AS INTEGER)"
        return super().as_sql(*args, **kwargs)

    def as_postgresql(self, *args, **kwargs):
        self.template = "EXTRACT(DOW FROM %(expressions)s)"
        return super().as_sql(*args, **kwargs)

class Hour(Func):
    function = 'HOUR'
    output_field=IntegerField()

    def as_sqlite(self, *args, **kwargs):
        self.template = "CAST (STRFTIME('%%H', %(expressions)s) AS INTEGER)"
        return super().as_sql(*args, **kwargs)

    def as_postgresql(self, *args, **kwargs):
        self.template = "EXTRACT(HOUR FROM %(expressions)s)"
        return super().as_sql(*args, **kwargs)

