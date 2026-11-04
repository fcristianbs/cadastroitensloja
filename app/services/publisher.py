import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from werkzeug.datastructures import FileStorage

from app.config import Config
from app.services.git_service import (
    GitServiceError,
    git_add,
    git_commit,
    git_pull,
    git_push,
    get_repo_status
)
from app.services.image_service import save_product_image
from app.services.product_service import (
    build_product_record,
    generate_slug,
    insert_product,
    validate_product_data,
    get_produto_by_slug
)

def run_publish_pipeline(
    raw_data: Dict[str, Any],
    image_file: Optional[FileStorage] = None,
    auto_push: bool = True
) -> Dict[str, Any]:
    """
    Executa o fluxo completo e automatizado de cadastro de produto e deploy:
    1. Sincronização Prévia: git pull origin main
    2. Upload e espelhamento da Imagem: static/ e public/static/
    3. Atualização de data/produtos.json (UTF-8, indent=2, ensure_ascii=False)
    4. Git Add dos arquivos modificados
    5. Git Commit: "feat(catalogo): cadastrar produto <nome> (<slug>)"
    6. Git Push: git push origin main
    """
    logs: List[Dict[str, str]] = []
    
    def log(step: str, status: str, message: str, detail: str = ""):
        logs.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "step": step,
            "status": status,
            "message": message,
            "detail": detail
        })

    result: Dict[str, Any] = {
        "success": False,
        "logs": logs,
        "product": None,
        "commit_hash": None,
        "commit_message": None,
        "pushed": False,
        "error": None
    }

    try:
        # Etapa 0: Verificação de Sanidade do Repositório
        log("PRE_FLIGHT", "INFO", "Verificando o repositório local...")
        repo_info = get_repo_status()
        if not repo_info.get("is_git_repo"):
            raise RuntimeError(f"Repositório Git não configurado ou inválido: {repo_info.get('error')}")
            
        # Etapa 1: Sincronização Prévia (git pull)
        log("GIT_PULL", "INFO", f"Executando 'git pull {Config.GIT_REMOTE} {Config.GIT_BRANCH}'...")
        try:
            _, pull_output = git_pull()
            log("GIT_PULL", "SUCCESS", "Repositório sincronizado com sucesso.", pull_output)
        except GitServiceError as e:
            # Se for erro de conexão ou sem internet, avisa mas permite decidir se continua ou aborta
            log("GIT_PULL", "WARNING", f"Aviso na sincronização prévia: {e}", e.stderr or e.stdout)

        # Etapa 2: Validação Preliminar do Produto
        nome = (raw_data.get("nome") or "").strip()
        slug = generate_slug(raw_data.get("slug") or nome)
        raw_data["slug"] = slug
        
        # Checa se o slug já existe
        existing_prod = get_produto_by_slug(slug)
        is_new = existing_prod is None
        
        # Se veio imagem pelo formulário
        if image_file and image_file.filename:
            log("IMAGE_SAVE", "INFO", f"Processando e renomeando imagem para '{slug}'...")
            img_info = save_product_image(
                file_storage=image_file,
                slug=slug,
                alt_text=raw_data.get("imagem_alt") or nome,
                image_type=raw_data.get("imagem_tipo") or "instalada"
            )
            raw_data["imagens"] = [{
                "src": img_info["src"],
                "alt": img_info["alt"],
                "tipo": img_info["tipo"]
            }]
            saved_image_filename = img_info["filename"]
            log("IMAGE_SAVE", "SUCCESS", f"Foto salva com sucesso em 2 caminhos!", 
                f"1. static/img/produtos/{saved_image_filename}\n2. public/static/img/produtos/{saved_image_filename}")
        else:
            saved_image_filename = None
            # Se for atualização de produto existente e não enviou nova imagem, preserva imagens anteriores
            if existing_prod and existing_prod.get("imagens"):
                raw_data["imagens"] = existing_prod.get("imagens")

        # Constrói o registro do produto
        product_record = build_product_record(raw_data)
        
        # Validação formal das regras de negócio
        is_valid, validation_errors = validate_product_data(product_record, is_new=is_new)
        if not is_valid:
            error_msg = "; ".join(validation_errors)
            log("VALIDATION", "ERROR", f"Falha na validação das regras de negócio: {error_msg}")
            raise ValueError(error_msg)
            
        log("VALIDATION", "SUCCESS", "Validação concluída: Todas as regras de negócio foram atendidas (RN01, RN02, RN05).")

        # Etapa 3: Atualização do arquivo data/produtos.json
        log("JSON_UPDATE", "INFO", "Atualizando 'data/produtos.json'...")
        insert_product(product_record, position="top")
        log("JSON_UPDATE", "SUCCESS", f"Produto '{nome}' inserido com sucesso em data/produtos.json.")

        # Etapa 4: Git Add
        files_to_stage = ["data/produtos.json"]
        if saved_image_filename:
            files_to_stage.append(f"static/img/produtos/{saved_image_filename}")
            files_to_stage.append(f"public/static/img/produtos/{saved_image_filename}")
            
        log("GIT_ADD", "INFO", f"Preparando arquivos para commit: {', '.join(files_to_stage)}")
        git_add(files_to_stage)
        log("GIT_ADD", "SUCCESS", "Arquivos adicionados à staging area do Git.")

        # Etapa 5: Git Commit
        commit_msg = f"feat(catalogo): cadastrar produto {nome} ({slug})"
        log("GIT_COMMIT", "INFO", f"Criando commit: '{commit_msg}'...")
        _, commit_hash, commit_out = git_commit(commit_msg)
        if "Nenhuma alteração" in commit_out:
            log("GIT_COMMIT", "INFO", f"Conteúdo idêntico: {commit_out} (Commit: {commit_hash})")
        else:
            log("GIT_COMMIT", "SUCCESS", f"Commit criado com sucesso: [{commit_hash}] {commit_msg}", commit_out)

        # Etapa 6: Git Push (se auto_push for True)
        if auto_push and Config.ENABLE_AUTO_PUSH:
            log("GIT_PUSH", "INFO", f"Enviando alterações para '{Config.GIT_REMOTE}/{Config.GIT_BRANCH}'...")
            _, push_out = git_push()
            log("GIT_PUSH", "SUCCESS", "Push concluído com sucesso! Deploy automático acionado no Vercel.", push_out)
            result["pushed"] = True
        else:
            log("GIT_PUSH", "INFO", "Push automático desativado. As alterações foram salvas e commitadas localmente.")
            result["pushed"] = False

        result["success"] = True
        result["product"] = product_record
        result["commit_hash"] = commit_hash
        result["commit_message"] = commit_msg
        return result

    except Exception as e:
        error_detail = str(e)
        log("ERROR", "ERROR", f"Falha no processo: {error_detail}")
        result["success"] = False
        result["error"] = error_detail
        return result

