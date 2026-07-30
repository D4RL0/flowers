from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError


MAX_DOCUMENT_SIZE = 5 * 1024 * 1024
ALLOWED_DOCUMENTS = {
    '.pdf': ({'application/pdf'}, lambda header: header.startswith(b'%PDF-')),
    '.png': ({'image/png'}, lambda header: header.startswith(b'\x89PNG\r\n\x1a\n')),
    '.jpg': ({'image/jpeg'}, lambda header: header.startswith(b'\xff\xd8\xff')),
    '.jpeg': ({'image/jpeg'}, lambda header: header.startswith(b'\xff\xd8\xff')),
}
ALLOWED_IMAGES = {
    '.png': ({'image/png'}, lambda header: header.startswith(b'\x89PNG\r\n\x1a\n')),
    '.jpg': ({'image/jpeg'}, lambda header: header.startswith(b'\xff\xd8\xff')),
    '.jpeg': ({'image/jpeg'}, lambda header: header.startswith(b'\xff\xd8\xff')),
}


def validate_document(uploaded_file):
    if uploaded_file.size <= 0:
        raise ValidationError('El archivo está vacío.')
    if uploaded_file.size > MAX_DOCUMENT_SIZE:
        raise ValidationError('El documento no puede superar los 5 MB.')

    extension = Path(uploaded_file.name).suffix.lower()
    config = ALLOWED_DOCUMENTS.get(extension)
    if not config:
        raise ValidationError('Solo se permiten documentos PDF, JPG, JPEG o PNG.')

    content_types, signature_validator = config
    content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
    if content_type not in content_types:
        raise ValidationError('El tipo declarado del archivo no corresponde a su extensión.')

    position = uploaded_file.tell()
    header = uploaded_file.read(16)
    uploaded_file.seek(position)
    if not signature_validator(header):
        raise ValidationError('El contenido real del archivo no corresponde a un documento permitido.')

    return uploaded_file


def validate_and_secure_document(uploaded_file):
    validate_document(uploaded_file)
    extension = Path(uploaded_file.name).suffix.lower()
    uploaded_file.name = f'{uuid4().hex}{extension}'
    return uploaded_file


def validate_image(uploaded_file):
    if uploaded_file.size <= 0:
        raise ValidationError('La imagen está vacía.')
    if uploaded_file.size > MAX_DOCUMENT_SIZE:
        raise ValidationError('La imagen no puede superar los 5 MB.')

    extension = Path(uploaded_file.name).suffix.lower()
    config = ALLOWED_IMAGES.get(extension)
    if not config:
        raise ValidationError('Solo se permiten imágenes JPG, JPEG o PNG.')

    content_types, signature_validator = config
    content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
    if content_type not in content_types:
        raise ValidationError('El tipo declarado no corresponde a una imagen JPG o PNG.')

    position = uploaded_file.tell()
    header = uploaded_file.read(16)
    uploaded_file.seek(position)
    if not signature_validator(header):
        raise ValidationError('El contenido real del archivo no corresponde a una imagen permitida.')

    return uploaded_file


def validate_and_secure_image(uploaded_file):
    validate_image(uploaded_file)
    extension = Path(uploaded_file.name).suffix.lower()
    uploaded_file.name = f'{uuid4().hex}{extension}'
    return uploaded_file
