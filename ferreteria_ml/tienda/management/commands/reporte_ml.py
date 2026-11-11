from django.core.management.base import BaseCommand

from tienda.reports import generate_plot, generate_text_report


class Command(BaseCommand):
    help = 'Genera un reporte simple de recomendaciones / clusters por categoría.'

    def add_arguments(self, parser):
        parser.add_argument('--top', type=int, default=10, help='Cantidad de productos/categorías a mostrar')
        parser.add_argument('--output', type=str, default='', help='Ruta del archivo PNG a generar (opcional)')

    def handle(self, *args, **options):
        top = options['top']
        output = options['output'].strip()

        self.stdout.write(self.style.SUCCESS(generate_text_report(limit=top)))

        if output:
            try:
                saved = generate_plot(output, limit=top)
                self.stdout.write(self.style.SUCCESS(f'Gráfica guardada en: {saved}'))
            except RuntimeError as exc:
                self.stdout.write(self.style.WARNING(f'No se pudo generar la gráfica: {exc}'))
                self.stdout.write(self.style.WARNING('Instala matplotlib para habilitar la exportación PNG.'))
