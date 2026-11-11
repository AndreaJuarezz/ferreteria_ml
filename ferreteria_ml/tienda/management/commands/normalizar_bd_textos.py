from django.core.management.base import BaseCommand
from django.db import transaction

from tienda.models import Categoria, Producto
from tienda.reports import strip_accents


class Command(BaseCommand):
    help = 'Normaliza los textos de Categoria y Producto a ASCII sin acentos.'

    def handle(self, *args, **options):
        updated_categories = 0
        updated_products = 0
        updated_descriptions = 0

        with transaction.atomic():
            for categoria in Categoria.objects.all():
                nuevo = strip_accents(categoria.nombre)
                if nuevo != categoria.nombre:
                    categoria.nombre = nuevo
                    categoria.save(update_fields=['nombre'])
                    updated_categories += 1

            for producto in Producto.objects.all():
                cambios = []

                nuevo_nombre = strip_accents(producto.nombre)
                if nuevo_nombre != producto.nombre:
                    producto.nombre = nuevo_nombre
                    cambios.append('nombre')
                    updated_products += 1

                nueva_descripcion = strip_accents(producto.descripcion)
                if nueva_descripcion != producto.descripcion:
                    producto.descripcion = nueva_descripcion
                    cambios.append('descripcion')
                    updated_descriptions += 1

                if cambios:
                    producto.save(update_fields=cambios)

        self.stdout.write(self.style.SUCCESS(
            f'Categorias actualizadas: {updated_categories} | Productos actualizados: {updated_products} | Descripciones actualizadas: {updated_descriptions}'
        ))
