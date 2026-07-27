from django.urls import path
from . import views

urlpatterns = [
    path('auditoria/', views.inicioBitacora, name='inicioBitacora'),
    path('auditoria/ver/<int:id>/', views.verRegistroBitacora, name='verRegistroBitacora'),
]
