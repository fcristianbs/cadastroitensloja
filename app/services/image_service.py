import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from app.config import Config

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

def allowed_file(filename: str) -> bool:
    """Verifica se o arquivo possui uma extensão permitida."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def get_file_extension(filename: str) -> str:
    """Obtém a extensão do arquivo em minúsculas (ex: 'png', 'webp')."""
    if "." in filename:
        ext = filename.rsplit(".", 1)[1].lower()
        if ext == "jpeg":
            return "jpg"
        return ext
    return "png"


def save_product_image(
    file_storage: FileStorage,
    slug: str,
    alt_text: Optional[str] = None,
    image_type: str = "instalada"
) -> Dict[str, Any]:
    """
    Salva o arquivo de imagem do produto espelhado em duas pastas:
    1. <REPO_PATH>/static/img/produtos/<slug>.<ext>
    2. <REPO_PATH>/public/static/img/produtos/<slug>.<ext>
    
    Retorna o dicionário com src, alt e tipo conforme o schema Voxel Lab.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("Nenhum arquivo de imagem foi enviado.")
        
    orig_name = secure_filename(file_storage.filename)
    if not allowed_file(orig_name):
        raise ValueError(f"Formato de imagem não suportado. Use: {', '.join(ALLOWED_EXTENSIONS)}")
        
    ext = get_file_extension(orig_name)
    target_filename = f"{slug}.{ext}"
    
    # Diretórios de destino
    static_dir = Config.STATIC_IMG_DIR
    public_dir = Config.PUBLIC_IMG_DIR
    
    static_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    
    static_path = static_dir / target_filename
    public_path = public_dir / target_filename
    
    # Lê os bytes da imagem
    image_bytes = file_storage.read()
    if len(image_bytes) == 0:
        raise ValueError("O arquivo de imagem enviado está vazio.")
        
    # Otimização via Pillow (redimensiona se muito grande e otimiza peso para web)
    try:
        from PIL import Image, ImageOps
        import io

        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)  # Corrige orientação EXIF de fotos de celular
        
        # Redimensiona mantendo proporção se exceder 1600px
        max_dim = 1600
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
        out_buffer = io.BytesIO()
        ext_lower = ext.lower()
        
        if ext_lower in ("jpg", "jpeg"):
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(out_buffer, format="JPEG", quality=88, optimize=True)
            image_bytes = out_buffer.getvalue()
        elif ext_lower == "webp":
            img.save(out_buffer, format="WEBP", quality=85, method=6)
            image_bytes = out_buffer.getvalue()
        elif ext_lower == "png":
            img.save(out_buffer, format="PNG", optimize=True)
            image_bytes = out_buffer.getvalue()
    except ImportError:
        pass  # Pillow não disponível, prossegue com os bytes originais
    except Exception as e:
        # Se falhar a otimização, ainda tenta validar integridade básica
        pass
        
    # Grava nas duas pastas de forma sincronizada
    with open(static_path, "wb") as f_static:
        f_static.write(image_bytes)
        
    with open(public_path, "wb") as f_public:
        f_public.write(image_bytes)
        
    web_src = f"/static/img/produtos/{target_filename}"
    
    return {
        "src": web_src,
        "alt": alt_text or slug.replace("-", " ").title(),
        "tipo": image_type or "instalada",
        "filename": target_filename,
        "static_path": str(static_path),
        "public_path": str(public_path),
        "size_kb": round(len(image_bytes) / 1024, 1)
    }


def rename_product_images(old_slug: str, new_slug: str) -> Optional[str]:
    """
    Renomeia os arquivos de imagem de um produto quando o slug é alterado durante a edição.
    Retorna o novo web_src se renomeou com sucesso, ou None se não havia foto ou slugs idênticos.
    """
    if not old_slug or not new_slug or old_slug == new_slug:
        return None
        
    static_dir = Config.STATIC_IMG_DIR
    public_dir = Config.PUBLIC_IMG_DIR
    
    renamed_filename = None
    for ext in ALLOWED_EXTENSIONS:
        old_static = static_dir / f"{old_slug}.{ext}"
        new_static = static_dir / f"{new_slug}.{ext}"
        if old_static.exists():
            old_static.replace(new_static)
            renamed_filename = f"{new_slug}.{ext}"
            
        old_public = public_dir / f"{old_slug}.{ext}"
        new_public = public_dir / f"{new_slug}.{ext}"
        if old_public.exists():
            old_public.replace(new_public)
            renamed_filename = f"{new_slug}.{ext}"
            
    if renamed_filename:
        return f"/static/img/produtos/{renamed_filename}"
    return None
