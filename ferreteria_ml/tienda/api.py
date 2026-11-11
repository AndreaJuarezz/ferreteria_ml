from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Producto
from .recommender import recomendaciones_hibridas


@api_view(['GET'])
def productos_api(request):
    productos = Producto.objects.all()[:50]

    data = [
        {
            "id": p.id,
            "nombre": p.nombre,
            "precio": p.precio
        }
        for p in productos
    ]

    return Response(data)


@api_view(['GET'])
def recomendaciones_api(request):
    """Devuelve recomendaciones para un usuario.

    Parámetros GET:
    - usuario: id del usuario (opcional). Si no se provee, devuelve productos aleatorios.
    - limite: número máximo de resultados (default 10)
    """
    usuario = request.GET.get('usuario')
    limite = int(request.GET.get('limite', 10))

    try:
        usuario_id = int(usuario) if usuario is not None else None
    except ValueError:
        return Response({'error': 'usuario debe ser un entero'}, status=400)

    if usuario_id is None:
        # fallback: productos aleatorios
        productos = Producto.objects.order_by('?')[:limite]
    else:
        productos = recomendaciones_hibridas(usuario_id, limite=limite)

    data = [
        {
            'id': p.id,
            'nombre': p.nombre,
            'categoria_id': p.categoria_id,
            'precio': p.precio,
        }
        for p in productos
    ]

    return Response(data)