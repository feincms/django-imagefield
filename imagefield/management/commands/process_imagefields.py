import multiprocessing as mp
import sys
from fnmatch import fnmatch
from functools import partial

from django.core.management.base import BaseCommand, CommandError

from imagefield.fields import IMAGEFIELDS


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--all", action="store_true", dest="all", help="Process all fields."
        )
        parser.add_argument(
            "--force",
            action="store_true",
            dest="force",
            help="Force processing of images even if they exist already.",
        )
        parser.add_argument(
            "--housekeep",
            choices=["blank-on-failure"],
            default="",
            help="Run house-keeping tasks.",
        )
        parser.add_argument(
            "--no-parallel",
            action="store_true",
            dest="no_parallel",
            help="Process images sequentially without parallelization.",
        )
        parser.add_argument(
            "field",
            nargs="*",
            type=str,
            help="Fields to process (globs are allowed): {}".format(
                " ".join(sorted(f.field_label for f in IMAGEFIELDS))
            ),
        )

        # TODO --clear for removing previously generated images.

    def handle(self, **options):
        self._fields = self._compile_imagefield_labels(options)

        for field in sorted(IMAGEFIELDS, key=lambda f: f.field_label):
            if field.field_label in self._fields:
                self._process_field(field, options)

    def _compile_imagefield_labels(self, options):
        if options["all"]:
            return type("c", (), {"__contains__": lambda *a: True})()
        elif options["field"]:
            fields = set()
            known = [f.field_label for f in IMAGEFIELDS]
            unknown = set()
            for field in options["field"]:
                if new := {f for f in known if fnmatch(f, field)}:
                    fields |= new
                else:
                    unknown.add(field)

            if unknown:
                raise CommandError(
                    "Unknown imagefields: {}".format(", ".join(sorted(unknown)))
                )
            return fields
        else:
            self.print_help(sys.argv[0], sys.argv[1])
            sys.exit(1)

    def _process_field(self, field, options):
        queryset = field.model._default_manager.exclude(**{field.name: ""}).order_by(
            "-pk"
        )
        count = queryset.count()
        self.stdout.write(
            "{} - {} objects - {}".format(
                field.field_label,
                count,
                ", ".join(sorted(field.formats.keys())) or "<no formats!>",
            )
        )
        self.stdout.write("\r|{}| {}/{}".format(" " * 50, 0, count), ending="")

        if field._fallback:
            _process_instance(
                field.model(),
                field,
                housekeep=None,
                force=options.get("force"),
            )

        fn = partial(
            _process_instance,
            field=field,
            housekeep=options.get("housekeep"),
            force=options.get("force"),
        )

        if options.get("no_parallel"):
            for index, (instance, errors) in enumerate(
                map(fn, queryset.iterator(chunk_size=100))
            ):
                if errors:
                    self.stderr.write("\n".join(errors))

                progress = "*" * (50 * index // count)
                self.stdout.write(
                    f"\r|{progress.ljust(50)}| {index + 1}/{count}", ending=""
                )

                # Save instance once for good measure; fills in width/height
                # if not done already
                instance._skip_generate_files = True
                instance.save()
        else:
            pool = mp.Pool()
            try:
                for index, (instance, errors) in enumerate(
                    pool.imap(fn, queryset.iterator(chunk_size=100))
                ):
                    if errors:
                        self.stderr.write("\n".join(errors))

                    progress = "*" * (50 * index // count)
                    self.stdout.write(
                        f"\r|{progress.ljust(50)}| {index + 1}/{count}", ending=""
                    )

                    # Save instance once for good measure; fills in width/height
                    # if not done already
                    instance._skip_generate_files = True
                    instance.save()

            finally:
                pool.close()
                pool.join()

        self.stdout.write("\r|{}| {}/{}".format("*" * 50, count, count))


def _process_instance(instance, field, housekeep, **kwargs):
    fieldfile = getattr(instance, field.name)
    for key in field.formats:
        try:
            fieldfile.process(key, **kwargs)
        except Exception as exc:
            if housekeep == "blank-on-failure":
                field.save_form_data(instance, "")

            return instance, [
                f"Error while processing {fieldfile.name} ({field.field_label}, #{instance.pk}):\n{exc}\n"
            ]

    return instance, None
