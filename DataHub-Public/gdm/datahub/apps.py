from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'datahub'

    # def ready(self):
    # from piplineUpdater import updater
    # updater.start()