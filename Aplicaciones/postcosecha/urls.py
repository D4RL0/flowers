from django.urls import path
from . import views

urlpatterns = [
    path('recepciones/', views.inicioRecepcion, name='inicioRecepcion'),
    path('recepciones/nueva/', views.nuevaRecepcion, name='nuevaRecepcion'),
    path('recepciones/guardar/', views.guardarRecepcion, name='guardarRecepcion'),
    path('recepciones/<str:codigo>/ticket/', views.ticketRecepcion, name='ticketRecepcion'),
    path('recepciones/<str:codigo>/detalle/', views.detalleRecepcion, name='detalleRecepcion'),
    path('recepciones/editar/<str:codigo>/', views.editarRecepcion, name='editarRecepcion'),
    path('recepciones/procesar-edicion/', views.procesarEdicionRecepcion, name='procesarEdicionRecepcion'),
    path('recepciones/detalle/guardar/', views.guardarDetalleRecepcion, name='guardarDetalleRecepcion'),
    path('recepciones/detalle/procesar-edicion/', views.procesarEdicionDetalleRecepcion, name='procesarEdicionDetalleRecepcion'),
    path('recepciones/detalle/eliminar/<int:id>/', views.eliminarDetalleRecepcion, name='eliminarDetalleRecepcion'),
    path('clasificaciones/', views.inicioClasificacion, name='inicioClasificacion'),
    path('clasificaciones/reporte-diario/', views.reporteDiarioClasificacion, name='reporteDiarioClasificacion'),
    path('clasificaciones/nueva/', views.nuevaClasificacion, name='nuevaClasificacion'),
    path('clasificaciones/guardar/', views.guardarClasificacion, name='guardarClasificacion'),
    path('clasificaciones/<str:codigo>/reporte/', views.reporteClasificacion, name='reporteClasificacion'),
    path('clasificaciones/editar/<str:codigo>/', views.editarClasificacion, name='editarClasificacion'),
    path('clasificaciones/procesar-edicion/', views.procesarEdicionClasificacion, name='procesarEdicionClasificacion'),
    path('tarifarios/', views.inicioTarifario, name='inicioTarifario'),
    path('tarifarios/nuevo/', views.nuevoTarifario, name='nuevoTarifario'),
    path('tarifarios/guardar/', views.guardarTarifario, name='guardarTarifario'),
    path('tarifarios/editar/<str:codigo>/', views.editarTarifario, name='editarTarifario'),
    path('tarifarios/procesar-edicion/', views.procesarEdicionTarifario, name='procesarEdicionTarifario'),
    path('tarifarios/cerrar/<str:codigo>/', views.cerrarTarifario, name='cerrarTarifario'),
]
