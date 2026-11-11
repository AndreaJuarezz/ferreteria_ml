from django.db.models import Case, IntegerField, Sum, Value, When

from .models import Interaccion, Producto


INTERACTION_WEIGHTS = {
    'VISTA': 1,
    'CART': 2,
    'COMPRA': 3,
}

RECENT_USER_INTERACTIONS = 20
RECENT_GLOBAL_INTERACTIONS = 300


def _interaction_score_case():
    return Case(
        When(tipo='COMPRA', then=Value(INTERACTION_WEIGHTS['COMPRA'])),
        When(tipo='CART', then=Value(INTERACTION_WEIGHTS['CART'])),
        When(tipo='VISTA', then=Value(INTERACTION_WEIGHTS['VISTA'])),
        default=Value(0),
        output_field=IntegerField(),
    )


def _rank_products(products, score_map):
    return sorted(
        products,
        key=lambda producto: (
            score_map.get(producto.id, 0),
            producto.stock,
            -producto.id,
        ),
        reverse=True,
    )


def _build_category_quotas(category_scores, limit):
    if not category_scores or limit <= 0:
        return {}

    ordered = sorted(category_scores.items(), key=lambda item: item[1], reverse=True)

    if len(ordered) >= limit:
        return {category_id: 1 for category_id, _score in ordered[:limit]}

    quotas = {category_id: 1 for category_id, _score in ordered}
    remaining = limit - len(quotas)
    total_score = sum(score for _category_id, score in ordered) or len(ordered)

    fractional_parts = []
    for category_id, score in ordered:
        share = (score / total_score) * remaining if total_score else remaining / len(ordered)
        extra = int(share)
        quotas[category_id] += extra
        fractional_parts.append((share - extra, category_id))

    leftovers = limit - sum(quotas.values())
    for _fraction, category_id in sorted(fractional_parts, reverse=True):
        if leftovers <= 0:
            break
        quotas[category_id] += 1
        leftovers -= 1

    return quotas


def recomendaciones_hibridas(usuario_id, limite=10):
    interacciones_usuario = (
        Interaccion.objects.filter(usuario_id=usuario_id)
        .select_related('producto', 'producto__categoria')
        .order_by('-creado', '-id')[:RECENT_USER_INTERACTIONS]
    )

    if not list(interacciones_usuario):
        return list(
            Producto.objects.select_related('categoria')
            .filter(stock__gt=0)
            .order_by('?')[:limite]
        )

    interacciones_usuario = list(interacciones_usuario)

    user_category_scores = {}
    for interaccion in interacciones_usuario:
        categoria_id = interaccion.producto.categoria_id
        user_category_scores[categoria_id] = user_category_scores.get(categoria_id, 0) + INTERACTION_WEIGHTS.get(interaccion.tipo, 0)

    if not user_category_scores:
        return list(
            Producto.objects.select_related('categoria')
            .filter(stock__gt=0)
            .order_by('?')[:limite]
        )

    seen_product_ids = {interaccion.producto_id for interaccion in interacciones_usuario}

    recent_global_interactions = list(
        Interaccion.objects.select_related('producto')
        .order_by('-creado', '-id')[:RECENT_GLOBAL_INTERACTIONS]
    )
    global_product_scores = {}
    for interaccion in recent_global_interactions:
        global_product_scores[interaccion.producto_id] = global_product_scores.get(interaccion.producto_id, 0) + INTERACTION_WEIGHTS.get(interaccion.tipo, 0)

    category_quotas = _build_category_quotas(user_category_scores, limite)
    ordered_categories = sorted(user_category_scores.items(), key=lambda item: item[1], reverse=True)

    selected_products = []
    selected_ids = set()

    for category_id, _score in ordered_categories:
        quota = category_quotas.get(category_id, 0)
        if quota <= 0:
            continue

        products = list(
            Producto.objects.select_related('categoria')
            .filter(categoria_id=category_id, stock__gt=0)
            .exclude(id__in=seen_product_ids)
        )
        ranked_products = _rank_products(products, global_product_scores)

        for producto in ranked_products:
            if producto.id in selected_ids:
                continue
            selected_products.append(producto)
            selected_ids.add(producto.id)
            quota -= 1
            if quota <= 0 or len(selected_products) >= limite:
                break

    if len(selected_products) < limite:
        filler_products = list(
            Producto.objects.select_related('categoria')
            .filter(stock__gt=0)
            .exclude(id__in=seen_product_ids | selected_ids)
        )
        filler_products = _rank_products(filler_products, global_product_scores)

        for producto in filler_products:
            if len(selected_products) >= limite:
                break
            if producto.id in selected_ids:
                continue
            selected_products.append(producto)
            selected_ids.add(producto.id)

    return selected_products[:limite]