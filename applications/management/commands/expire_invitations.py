from django.core.management.base import BaseCommand

from applications.services import expire_old_invitations


class Command(BaseCommand):
    help = "Expire invitations that have been pending for more than 24 hours"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Number of hours after which to expire pending invitations (default: 24)",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        count = expire_old_invitations(hours=hours)

        if count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Expired {count} invitation(s) older than {hours} hours.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"No invitations to expire (checked for >{hours} hours).")
            )
