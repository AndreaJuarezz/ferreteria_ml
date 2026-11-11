import base64
import io
import unicodedata
from dataclasses import dataclass

from django.db.models import Case, Count, IntegerField, Q, Sum, Value, When

from .models import Interaccion, Producto


@dataclass
class CategorySummary:
    nombre: str
    productos: int
    vistas: int
    carritos: int
    compras: int
    score: int


def strip_accents(text):
    if text is None:
        return ''
    text = str(text)
    for encoding in ('cp850', 'cp437', 'cp1252', 'latin1'):
        try:
            repaired = text.encode(encoding).decode('utf-8')
            if repaired != text:
                text = repaired
                break
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    normalized = unicodedata.normalize('NFKD', text)
    return normalized.encode('ascii', 'ignore').decode('ascii')


def _interaction_score_case():
    return Case(
        When(tipo='COMPRA', then=Value(3)),
        When(tipo='CART', then=Value(2)),
        When(tipo='VISTA', then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )


def top_products_by_interaction(usuario_id=None, limit=10):
    interactions = Interaccion.objects.all()
    if usuario_id is not None:
        interactions = interactions.filter(usuario_id=usuario_id)

    return (
        interactions.values('producto_id', 'producto__nombre')
        .annotate(
            vistas=Count('id', filter=Q(tipo='VISTA')),
            carritos=Count('id', filter=Q(tipo='CART')),
            compras=Count('id', filter=Q(tipo='COMPRA')),
            total=Count('id'),
            score=Sum(_interaction_score_case()),
        )
        .order_by('-score', '-compras', '-carritos', '-vistas', '-total')[:limit]
    )


def category_summary(usuario_id=None):
    interactions = Interaccion.objects.all()
    if usuario_id is not None:
        interactions = interactions.filter(usuario_id=usuario_id)

    categories = []
    product_counts = dict(
        Producto.objects.values('categoria__nombre')
        .annotate(total=Count('id'))
        .values_list('categoria__nombre', 'total')
    )

    interaction_rows = (
        interactions.values('producto__categoria__nombre')
        .annotate(
            vistas=Count('id', filter=Q(tipo='VISTA')),
            carritos=Count('id', filter=Q(tipo='CART')),
            compras=Count('id', filter=Q(tipo='COMPRA')),
            score=Sum(_interaction_score_case()),
        )
        .order_by('producto__categoria__nombre')
    )
    interaction_map = {
        row['producto__categoria__nombre']: row for row in interaction_rows
    }

    for nombre, total_productos in product_counts.items():
        row = interaction_map.get(nombre, {})
        categories.append(
            CategorySummary(
                nombre=strip_accents(nombre),
                productos=total_productos,
                vistas=row.get('vistas', 0),
                carritos=row.get('carritos', 0),
                compras=row.get('compras', 0),
                score=row.get('score', 0) or 0,
            )
        )

    return sorted(categories, key=lambda item: (item.score, item.compras, item.carritos, item.vistas, item.productos), reverse=True)


def total_interactions(usuario_id=None):
    interactions = Interaccion.objects.all()
    if usuario_id is not None:
        interactions = interactions.filter(usuario_id=usuario_id)
    return interactions.count()


def generate_text_report(usuario_id=None, limit=10):
    top_products = list(top_products_by_interaction(usuario_id=usuario_id, limit=limit))
    categories = category_summary(usuario_id=usuario_id)

    lines = []
    lines.append('REPORTE / RECOMENDACIONES')
    lines.append('=' * 32)
    lines.append('')
    lines.append('Top productos por interaccion:')
    for idx, item in enumerate(top_products, start=1):
        lines.append(
            f"{idx:02d}. {strip_accents(item['producto__nombre'])} | vistas={item['vistas']} | carrito={item['carritos']} | compras={item['compras']} | score={item['score']}"
        )

    lines.append('')
    lines.append('Resumen por categoria (clusters simples):')
    for idx, cat in enumerate(categories[:limit], start=1):
        lines.append(
            f"{idx:02d}. {strip_accents(cat.nombre)} | productos={cat.productos} | vistas={cat.vistas} | carrito={cat.carritos} | compras={cat.compras} | score={cat.score}"
        )

    return '\n'.join(lines)


def generate_plot(output_path, usuario_id=None, limit=10):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError('matplotlib no está instalado') from exc

    categories = category_summary(usuario_id=usuario_id)[:limit]
    labels = [cat.nombre for cat in categories]
    vistas = [cat.vistas for cat in categories]
    carritos = [cat.carritos for cat in categories]
    compras = [cat.compras for cat in categories]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Reporte / Clusters simples por categoria')

    axes[0].barh(labels, vistas, color='#60a5fa', label='Vistas')
    axes[0].barh(labels, carritos, color='#f59e0b', label='Carrito', alpha=0.7)
    axes[0].set_title('Vistas y carrito por categoria')
    axes[0].invert_yaxis()
    axes[0].set_xlabel('Cantidad')
    axes[0].legend(loc='lower right')

    axes[1].barh(labels, compras, color='#34d399')
    axes[1].set_title('Compras por categoria')
    axes[1].invert_yaxis()
    axes[1].set_xlabel('Cantidad')

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    from pathlib import Path
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def generate_plot_base64(usuario_id=None, limit=8):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError('matplotlib no está instalado') from exc

    categories = category_summary(usuario_id=usuario_id)[:limit]
    labels = [cat.nombre for cat in categories]
    vistas = [cat.vistas for cat in categories]
    carritos = [cat.carritos for cat in categories]
    compras = [cat.compras for cat in categories]

    if not categories:
        return ''

    fig, ax = plt.subplots(figsize=(12, 6))
    y = range(len(categories))
    height = 0.25

    ax.barh([i - height for i in y], vistas, height=height, label='Vistas', color='#60a5fa')
    ax.barh(y, carritos, height=height, label='Carrito', color='#f59e0b')
    ax.barh([i + height for i in y], compras, height=height, label='Compras', color='#34d399')
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.set_xlabel('Cantidad')
    ax.set_title('Que categorias miras, agregas al carrito y compras mas')
    ax.legend(loc='lower right')
    ax.grid(axis='x', linestyle='--', alpha=0.25)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')
