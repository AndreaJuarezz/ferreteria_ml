from django.urls import path
from . import views
from .api import productos_api, recomendaciones_api

urlpatterns = [
    path('', views.landing, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('productos/', views.productos_list, name='productos_list'),
    path('productos/nuevo/', views.producto_create, name='producto_create'),
    path('productos/<int:producto_id>/editar/', views.producto_update, name='producto_update'),
    path('productos/<int:producto_id>/eliminar/', views.producto_delete, name='producto_delete'),
    path('carrito/', views.carrito, name='carrito'),
    path('producto/<int:producto_id>/', views.ver_producto, name='ver_producto'),
    path('agregar/<int:producto_id>/', views.agregar_carrito, name='agregar_carrito'),
    path('carrito/item/<int:item_id>/actualizar/', views.actualizar_carrito, name='actualizar_carrito'),
    path('eliminar-carrito/<int:item_id>/', views.eliminar_carrito, name='eliminar_carrito'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('registro/', views.registro, name='registro'),
    path('buscar/', views.buscar, name='buscar'),
    path('checkout/', views.checkout, name='checkout'),
    path('recibo/<int:orden_id>/', views.recibo, name='recibo'),
    path('historial-compras/', views.historial_compras, name='historial_compras'),
    path('reportes/', views.reportes, name='reportes'),
    path('api/productos/', productos_api, name='api_productos'),
    path('api/recomendaciones/', recomendaciones_api, name='api_recomendaciones'),
]