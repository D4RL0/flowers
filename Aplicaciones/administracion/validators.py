from django.core.exceptions import ValidationError


def _provincia_valida(documento):
    return documento[:2].isdigit() and 1 <= int(documento[:2]) <= 24


def cedula_ecuatoriana_valida(cedula):
    cedula = str(cedula or '').strip()
    if len(cedula) != 10 or not cedula.isdigit() or not _provincia_valida(cedula):
        return False
    if int(cedula[2]) >= 6:
        return False
    total = 0
    for indice, caracter in enumerate(cedula[:9]):
        valor = int(caracter) * (2 if indice % 2 == 0 else 1)
        total += valor - 9 if valor > 9 else valor
    return (10 - total % 10) % 10 == int(cedula[9])


def ruc_ecuatoriano_valido(ruc):
    ruc = str(ruc or '').strip()
    if len(ruc) != 13 or not ruc.isdigit() or not _provincia_valida(ruc):
        return False
    tercer_digito = int(ruc[2])
    if tercer_digito < 6:
        return cedula_ecuatoriana_valida(ruc[:10]) and ruc[10:] != '000'
    if tercer_digito == 6:
        total = sum(int(digito) * peso for digito, peso in zip(ruc[:8], (3, 2, 7, 6, 5, 4, 3, 2)))
        verificador = (11 - total % 11) % 11
        return verificador < 10 and verificador == int(ruc[8]) and ruc[9:] != '0000'
    if tercer_digito == 9:
        total = sum(int(digito) * peso for digito, peso in zip(ruc[:9], (4, 3, 2, 7, 6, 5, 4, 3, 2)))
        verificador = (11 - total % 11) % 11
        return verificador < 10 and verificador == int(ruc[9]) and ruc[10:] != '000'
    return False


def validar_cedula_ecuatoriana(valor):
    if not cedula_ecuatoriana_valida(valor):
        raise ValidationError('Ingrese una cédula ecuatoriana válida.')


def validar_documento_ecuatoriano(valor):
    if not (cedula_ecuatoriana_valida(valor) or ruc_ecuatoriano_valido(valor)):
        raise ValidationError('Ingrese una cédula o RUC ecuatoriano válido.')


def telefono_ecuatoriano_valido(telefono):
    telefono = str(telefono or '').strip()
    if not telefono.isdigit():
        return False
    return (
        (len(telefono) == 10 and telefono.startswith('09'))
        or len(telefono) == 7
    )


def validar_telefono_ecuatoriano(valor):
    if not telefono_ecuatoriano_valido(valor):
        raise ValidationError('Ingrese un celular nacional 09 de 10 dígitos o un teléfono local de 7 dígitos.')
