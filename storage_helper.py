import os
import uuid
import requests as _req

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
BUCKET = 'syndicpro-files'

_EXT = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/gif': '.gif',
    'application/pdf': '.pdf',
}


def upload_file(raw_bytes, mime_type, folder='uploads'):
    """Upload vers Supabase Storage. Retourne l'URL publique ou None si échec/non configuré."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None
    ext = _EXT.get(mime_type, '.bin')
    path = f"{folder}/{uuid.uuid4().hex}{ext}"
    try:
        resp = _req.post(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}",
            headers={
                'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
                'Content-Type': mime_type,
            },
            data=raw_bytes,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"
    except Exception:
        pass
    return None


def delete_file(file_url):
    """Supprime un fichier de Supabase Storage via son URL publique."""
    if not file_url or not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return
    prefix = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/"
    if not file_url.startswith(prefix):
        return
    path = file_url[len(prefix):]
    try:
        _req.delete(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}",
            headers={'Authorization': f'Bearer {SUPABASE_ANON_KEY}'},
            timeout=10,
        )
    except Exception:
        pass
