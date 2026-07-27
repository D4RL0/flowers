# Despliegue de L.Y Flowers en Railway

## 1. Servicios del proyecto

En el mismo proyecto de Railway deben existir tres servicios:

1. La aplicación conectada al repositorio de GitHub.
2. PostgreSQL, con el nombre `Postgres`.
3. Redis, con el nombre `Redis`.

Los nombres importan porque las variables usan referencias entre servicios.

## 2. Variables de la aplicación

Abra el servicio de la aplicación, ingrese a **Variables** y use **Raw Editor**.
Reemplace únicamente los valores indicados; nunca suba estos secretos a GitHub.

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=REEMPLAZAR_POR_UNA_CLAVE_ALEATORIA_LARGA
DATABASE_URL=${{Postgres.DATABASE_URL}}
VALKEY_URL=${{Redis.REDIS_URL}}

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=administracion.lyflowers@gmail.com
EMAIL_HOST_PASSWORD=REEMPLAZAR_POR_LA_CLAVE_DE_APLICACION_DE_GOOGLE
DEFAULT_FROM_EMAIL=Seguridad L.Y Flowers <administracion.lyflowers@gmail.com>
PASSWORD_RECOVERY_EMAIL=administracion.lyflowers@gmail.com
```

No agregue `PORT`: Railway la crea automáticamente. Tampoco copie una URL real
de PostgreSQL o Redis; las referencias anteriores usan la red privada del proyecto.

## 3. Dominio público

En el servicio de la aplicación vaya a **Settings > Networking > Generate Domain**.
Railway crea `RAILWAY_PUBLIC_DOMAIN` automáticamente y Django lo incorpora a
`ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`.

Si después utiliza un dominio propio, agregue:

```env
DJANGO_ALLOWED_HOSTS=sistema.sudominio.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://sistema.sudominio.com
```

## 4. Documentos persistentes

Los contratos, documentos del personal y comprobantes de liquidación no deben
guardarse en el disco temporal del despliegue.

En el servicio de la aplicación agregue un **Volume** y use exactamente este
punto de montaje:

```text
/app/media
```

Railway suministra `RAILWAY_VOLUME_MOUNT_PATH` automáticamente. No la cree a mano.
Habilite respaldos del volumen y de PostgreSQL antes de ingresar datos reales.

## 5. Comandos automáticos

El archivo `railway.json` configura:

- Build: `python manage.py collectstatic --noinput`
- Pre-deploy: `python manage.py migrate --noinput`
- Start: Gunicorn escuchando en `$PORT`
- Healthcheck: `/login/`

No duplique estos comandos en el panel, porque la configuración del repositorio
tiene prioridad sobre la configuración escrita manualmente en Railway.

## 6. Primer acceso

Después del primer despliegue, abra una consola del servicio y cree la única
cuenta administradora inicial:

```text
python manage.py createsuperuser
```

Luego abra el dominio generado, pruebe el inicio de sesión, la recuperación por
correo, la carga y visualización de un documento, y revise los logs del servicio.

## 7. Verificaciones antes de usar datos reales

- `DJANGO_DEBUG` aparece como `False`.
- El dominio abre siempre mediante HTTPS.
- Las migraciones terminan sin errores.
- CSS, JavaScript e imágenes cargan correctamente.
- PostgreSQL y Redis aparecen conectados.
- Los documentos siguen disponibles después de un redeploy.
- La recuperación de contraseña llega al correo institucional.
- Los respaldos de PostgreSQL y del volumen están habilitados.
