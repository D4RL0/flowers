import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404
from django.utils._os import safe_join


def archivo_media_protegido(request, path):
    try:
        ruta = Path(safe_join(settings.MEDIA_ROOT, path))
    except (SuspiciousFileOperation, ValueError, TypeError):
        raise Http404('Documento no encontrado')
    if not ruta.is_file():
        raise Http404('Documento no encontrado')

    tipo, _ = mimetypes.guess_type(ruta.name)
    respuesta = FileResponse(
        ruta.open('rb'),
        content_type=tipo or 'application/octet-stream',
        as_attachment=False,
        filename=ruta.name,
    )
    respuesta['Cache-Control'] = 'private, no-store'
    return respuesta
