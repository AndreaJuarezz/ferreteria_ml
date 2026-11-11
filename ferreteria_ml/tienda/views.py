from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from .models import Categoria, Producto, Carrito, ItemCarrito, Orden, DetalleOrden, Interaccion
from .recommender import recomendaciones_hibridas
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from .forms import RegistroForm, ProductoForm
from .reports import category_summary, generate_plot_base64, generate_text_report, strip_accents, top_products_by_interaction, total_interactions


MAX_CART_QUANTITY = 20


def get_active_carrito(user):
    carrito = Carrito.objects.filter(usuario=user).order_by('-creado').first()
    if carrito is None:
        carrito = Carrito.objects.create(usuario=user)
    return carrito


def _redirect_back_or(request, fallback_name='dashboard'):
    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect(fallback_name)


def landing(request):
    productos_destacados = []
    destacados = top_products_by_interaction(limit=4)

    if destacados:
        productos_por_id = {
            producto.id: producto
            for producto in Producto.objects.select_related('categoria').filter(
                id__in=[item['producto_id'] for item in destacados],
                stock__gt=0,
            )
        }

        for item in destacados:
            producto = productos_por_id.get(item['producto_id'])
            if producto is None:
                continue
            producto.feature_score = item.get('score', 0) or 0
            producto.feature_vistas = item.get('vistas', 0)
            producto.feature_carritos = item.get('carritos', 0)
            producto.feature_compras = item.get('compras', 0)
            productos_destacados.append(producto)

    if not productos_destacados:
        productos_destacados = list(
            Producto.objects.select_related('categoria')
            .filter(stock__gt=0)
            .order_by('-stock', 'nombre')[:4]
        )

    return render(request, 'landing.html', {
        'productos_destacados': productos_destacados,
    })


def dashboard(request):
    productos = Producto.objects.select_related('categoria').all()[:20]

    recomendaciones = []
    if request.user.is_authenticated:
        recomendaciones = recomendaciones_hibridas(request.user.id, limite=8)

    total_productos = Producto.objects.count()
    total_compras = Orden.objects.filter(usuario=request.user).count() if request.user.is_authenticated else 0

    return render(request, 'dashboard.html', {
        'productos': productos,
        'recomendaciones': recomendaciones,
        'total_productos': total_productos,
        'total_compras': total_compras,
    })


def productos_list(request):
    if not request.user.is_authenticated:
        return redirect('login')

    categorias = Categoria.objects.order_by('nombre')
    productos = Producto.objects.select_related('categoria').order_by('nombre')

    categoria_id = request.GET.get('categoria', '').strip()
    q = request.GET.get('q', '').strip()

    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)

    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(categoria__nombre__icontains=q)
        )

    return render(request, 'productos_list.html', {
        'productos': productos,
        'categorias': categorias,
        'categoria_activa': categoria_id,
        'query': q,
    })


def producto_create(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save()
            messages.success(request, f'Producto creado: {strip_accents(producto.nombre)}')
            return redirect('productos_list')
    else:
        form = ProductoForm()

    return render(request, 'producto_form.html', {'form': form, 'mode': 'crear'})


def producto_update(request, producto_id):
    if not request.user.is_authenticated:
        return redirect('login')

    producto = get_object_or_404(Producto, id=producto_id)

    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, f'Producto actualizado: {strip_accents(producto.nombre)}')
            return redirect('productos_list')
    else:
        form = ProductoForm(instance=producto)

    return render(request, 'producto_form.html', {'form': form, 'mode': 'editar', 'producto': producto})


def producto_delete(request, producto_id):
    if not request.user.is_authenticated:
        return redirect('login')

    producto = get_object_or_404(Producto, id=producto_id)

    if request.method == 'POST':
        nombre = strip_accents(producto.nombre)
        producto.delete()
        messages.success(request, f'Producto eliminado: {nombre}')
        return redirect('productos_list')

    return render(request, 'producto_confirm_delete.html', {'producto': producto})


def agregar_carrito(request, producto_id):
    """Agregar producto al carrito (CREAR/UPDATE)"""
    if not request.user.is_authenticated:
        return redirect('login')

    producto = get_object_or_404(Producto, id=producto_id)

    if producto.stock <= 0:
        messages.error(request, f'{strip_accents(producto.nombre)} está agotado y no se puede agregar al carrito.')
        return _redirect_back_or(request, 'ver_producto')

    raw_cantidad = request.POST.get('cantidad') or request.GET.get('cantidad') or '1'
    try:
        cantidad = int(raw_cantidad)
    except (TypeError, ValueError):
        messages.error(request, 'La cantidad debe ser un número entero válido.')
        return _redirect_back_or(request, 'ver_producto')

    if cantidad < 1:
        messages.error(request, 'Debes agregar al menos 1 unidad.')
        return _redirect_back_or(request, 'ver_producto')

    cantidad_maxima = min(producto.stock, MAX_CART_QUANTITY)
    if cantidad > cantidad_maxima:
        messages.error(
            request,
            f'La cantidad máxima para {strip_accents(producto.nombre)} es {cantidad_maxima}. '
            f'Usa un valor entre 1 y {cantidad_maxima}.'
        )
        return _redirect_back_or(request, 'ver_producto')

    carrito = get_active_carrito(request.user)

    item, created = ItemCarrito.objects.get_or_create(
        carrito=carrito,
        producto=producto
    )

    nueva_cantidad = item.cantidad + cantidad if not created else cantidad
    if nueva_cantidad > cantidad_maxima:
        messages.error(
            request,
            f'No puedes tener más de {cantidad_maxima} unidades de {strip_accents(producto.nombre)} en el carrito.'
        )
        return _redirect_back_or(request, 'ver_producto')

    if not created:
        item.cantidad = nueva_cantidad
        item.save()
    else:
        item.cantidad = cantidad
        item.save(update_fields=['cantidad'])

    messages.success(request, f'{strip_accents(producto.nombre)} agregado al carrito ({cantidad} unidad(es)).')

    # Registrar interacción de carrito como señal de interés
    Interaccion.objects.create(
        usuario=request.user,
        producto=producto,
        tipo='CART'
    )

    return _redirect_back_or(request, 'carrito')


def actualizar_carrito(request, item_id):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.method != 'POST':
        return redirect('carrito')

    item = get_object_or_404(ItemCarrito.objects.select_related('producto', 'carrito'), id=item_id, carrito__usuario=request.user)
    try:
        cantidad = int(request.POST.get('cantidad', item.cantidad))
    except (TypeError, ValueError):
        cantidad = item.cantidad

    if cantidad < 1:
        cantidad = 1

    if cantidad > item.producto.stock:
        messages.error(request, f'No hay stock suficiente para {strip_accents(item.producto.nombre)}. Disponible: {item.producto.stock}')
        return redirect('carrito')

    item.cantidad = cantidad
    item.save(update_fields=['cantidad'])
    messages.success(request, f'Cantidad actualizada para {strip_accents(item.producto.nombre)}')
    return redirect('carrito')


def ver_producto(request, producto_id):
    producto = get_object_or_404(Producto.objects.select_related('categoria'), id=producto_id)
    cantidad_maxima = min(producto.stock, MAX_CART_QUANTITY)

    if request.user.is_authenticated:
        Interaccion.objects.create(
            usuario=request.user,
            producto=producto,
            tipo='VISTA'
        )

    return render(request, 'producto_detalle.html', {
        'producto': producto,
        'cantidad_maxima': cantidad_maxima,
    })


def carrito(request):
    """Ver carrito (READ)"""
    if not request.user.is_authenticated:
        return redirect('login')

    carrito = get_active_carrito(request.user)
    items = ItemCarrito.objects.filter(carrito=carrito)

    for item in items:
        item.subtotal = item.producto.precio * item.cantidad
        item.max_cantidad = max(item.producto.stock, item.cantidad)

    total = sum(i.producto.precio * i.cantidad for i in items)

    return render(request, 'carrito.html', {
        'items': items,
        'total': total
    })


def eliminar_carrito(request, item_id):
    """Eliminar item del carrito (DELETE)"""
    if not request.user.is_authenticated:
        return redirect('login')

    item = ItemCarrito.objects.get(id=item_id)
    item.delete()
    return redirect('carrito')


def buscar(request):
    """Buscar productos (READ filtered)"""
    query = request.GET.get('q', '')
    
    if query:
        resultados = Producto.objects.filter(
            nombre__icontains=query
        ) | Producto.objects.filter(
            descripcion__icontains=query
        ) | Producto.objects.filter(
            categoria__nombre__icontains=query
        )
    else:
        resultados = []

    return render(request, 'busqueda.html', {
        'resultados': resultados,
        'query': query
    })


def registro(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = RegistroForm()

    return render(request, 'registro.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        user = authenticate(
            username=request.POST['username'],
            password=request.POST['password']
        )
        if user:
            login(request, user)
            return redirect('dashboard')

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('landing')


def checkout(request):
    """Realizar compra y generar recibo"""
    if not request.user.is_authenticated:
        return redirect('login')

    if request.method != 'POST':
        return redirect('carrito')

    carrito = get_active_carrito(request.user)
    items = ItemCarrito.objects.filter(carrito=carrito)

    if not items.exists():
        messages.warning(request, 'Tu carrito está vacío. Agrega productos antes de comprar.')
        return redirect('carrito')

    with transaction.atomic():
        for item in items:
            producto = Producto.objects.select_for_update().get(id=item.producto_id)
            if producto.stock < item.cantidad:
                messages.error(
                    request,
                    f'No hay stock suficiente para {strip_accents(producto.nombre)}. Disponible: {producto.stock}'
                )
                return redirect('carrito')

        total = sum(i.producto.precio * i.cantidad for i in items)

        # Crear orden
        orden = Orden.objects.create(usuario=request.user, total=total)

        # Crear detalles de orden, registrar interacciones y descontar stock
        for item in items:
            DetalleOrden.objects.create(
                orden=orden,
                producto=item.producto,
                cantidad=item.cantidad
            )

            Interaccion.objects.create(
                usuario=request.user,
                producto=item.producto,
                tipo='COMPRA'
            )

            producto = Producto.objects.select_for_update().get(id=item.producto_id)
            producto.stock = max(0, producto.stock - item.cantidad)
            producto.save(update_fields=['stock'])

        # Eliminar items del carrito
        items.delete()

    # Redirigir a página de recibo
    return redirect('recibo', orden_id=orden.id)


def recibo(request, orden_id):
    """Ver recibo de compra (READ)"""
    orden = Orden.objects.get(id=orden_id, usuario=request.user)
    return render(request, 'recibo.html', {'orden': orden})


def historial_compras(request):
    """Ver historial de compras del usuario (READ)"""
    if not request.user.is_authenticated:
        return redirect('login')

    ordenes = Orden.objects.filter(usuario=request.user).order_by('-fecha')
    return render(request, 'historial.html', {'ordenes': ordenes})


def reportes(request):
    if not request.user.is_authenticated:
        return redirect('login')

    categories = category_summary(usuario_id=request.user.id)[:8]
    top_productos = list(top_products_by_interaction(usuario_id=request.user.id, limit=8))
    for item in top_productos:
        item['producto__nombre_clean'] = strip_accents(item['producto__nombre'])
    chart_base64 = generate_plot_base64(usuario_id=request.user.id, limit=8)

    favorite_category = categories[0] if categories else None
    most_viewed = max(categories, key=lambda c: c.vistas, default=None) if categories else None
    most_carted = max(categories, key=lambda c: c.carritos, default=None) if categories else None
    most_bought = max(categories, key=lambda c: c.compras, default=None) if categories else None

    return render(request, 'reportes.html', {
        'categories': categories,
        'top_productos': top_productos,
        'chart_base64': chart_base64,
        'favorite_category': favorite_category,
        'most_viewed': most_viewed,
        'most_carted': most_carted,
        'most_bought': most_bought,
        'total_interactions': total_interactions(usuario_id=request.user.id),
    })
