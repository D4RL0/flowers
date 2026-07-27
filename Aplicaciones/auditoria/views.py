from django.shortcuts import get_object_or_404, render

from Aplicaciones.auditoria.models import Bitacora


def inicioBitacora(request):
    registros = Bitacora.objects.select_related('usuario').all().order_by('-fecha_hora')
    return render(request, 'auditoria/inicioBitacora.html', {'registros': registros})


def verRegistroBitacora(request, id):
    return render(request, 'auditoria/verRegistroBitacora.html', {
        'registro': get_object_or_404(Bitacora.objects.select_related('usuario'), pk=id)
    })
