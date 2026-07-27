from django.urls import path
from . import views

urlpatterns = [
    path('liquidaciones/', views.inicioLiquidacion, name='inicioLiquidacion'),
    path('liquidaciones/nueva/', views.nuevaLiquidacion, name='nuevaLiquidacion'),
    path('liquidaciones/guardar/', views.guardarLiquidacion, name='guardarLiquidacion'),
    path('liquidaciones/ver/<str:codigo>/', views.verLiquidacion, name='verLiquidacion'),
    path('liquidaciones/editar/<str:codigo>/', views.editarLiquidacion, name='editarLiquidacion'),
    path('liquidaciones/procesar-edicion/', views.procesarEdicionLiquidacion, name='procesarEdicionLiquidacion'),
    path('liquidaciones/pagar/<str:codigo>/', views.marcarLiquidacionPagada, name='marcarLiquidacionPagada'),
]
