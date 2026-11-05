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
from app.services.image_service import save_product_image, rename_product_images, delete_product_images
from app.services.product_service import (
    build_product_record,
    generate_slug,
    insert_product,
    update_product,
    delete_product,
    toggle_esgotado_product,
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
        
        original_slug = (raw_data.get("original_slug") or "").strip()
        is_edit = bool(original_slug)
        existing_prod = get_produto_by_slug(original_slug) if is_edit else get_produto_by_slug(slug)
        is_new = not is_edit
        
        saved_image_filename = None
        renamed_image_filename = None
        
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
            # Não enviou imagem nova
            if is_edit and existing_prod:
                if slug != original_slug:
                    # Slug foi alterado: renomeia a foto existente
                    new_src = rename_product_images(original_slug, slug)
                    if new_src:
                        renamed_image_filename = new_src.split("/")[-1]
                        raw_data["imagens"] = [{
                            "src": new_src,
                            "alt": (existing_prod.get("imagens") or [{}])[0].get("alt", nome),
                            "tipo": (existing_prod.get("imagens") or [{}])[0].get("tipo", "instalada")
                        }]
                        log("IMAGE_RENAME", "SUCCESS", f"Foto renomeada para '{renamed_image_filename}' acompanhando o novo slug.")
                    elif existing_prod.get("imagens"):
                        raw_data["imagens"] = existing_prod.get("imagens")
                elif existing_prod.get("imagens"):
                    raw_data["imagens"] = existing_prod.get("imagens")

        # Constrói o registro do produto
        product_record = build_product_record(raw_data)
        
        # Validação formal das regras de negócio
        is_valid, validation_errors = validate_product_data(
            product_record,
            is_new=is_new,
            original_slug=original_slug if is_edit else None
        )
        if not is_valid:
            error_msg = "; ".join(validation_errors)
            log("VALIDATION", "ERROR", f"Falha na validação das regras de negócio: {error_msg}")
            raise ValueError(error_msg)
            
        log("VALIDATION", "SUCCESS", "Validação concluída: Todas as regras de negócio foram atendidas (RN01, RN02, RN05).")

        # Etapa 3: Atualização do arquivo data/produtos.json
        log("JSON_UPDATE", "INFO", "Atualizando 'data/produtos.json'...")
        if is_edit and original_slug:
            update_product(original_slug, product_record)
            log("JSON_UPDATE", "SUCCESS", f"Produto '{nome}' atualizado com sucesso em data/produtos.json.")
        else:
            insert_product(product_record, position="top")
            log("JSON_UPDATE", "SUCCESS", f"Produto '{nome}' inserido com sucesso em data/produtos.json.")

        # Etapa 4: Git Add
        files_to_stage = ["data/produtos.json"]
        if saved_image_filename:
            files_to_stage.append(f"static/img/produtos/{saved_image_filename}")
            files_to_stage.append(f"public/static/img/produtos/{saved_image_filename}")
        elif renamed_image_filename:
            files_to_stage.append(f"static/img/produtos/{renamed_image_filename}")
            files_to_stage.append(f"public/static/img/produtos/{renamed_image_filename}")
            # Remove referências anteriores se necessário
            for ext in ["png", "jpg", "jpeg", "webp"]:
                files_to_stage.append(f"static/img/produtos/{original_slug}.{ext}")
                files_to_stage.append(f"public/static/img/produtos/{original_slug}.{ext}")
            
        log("GIT_ADD", "INFO", f"Preparando arquivos para commit: {', '.join(files_to_stage)}")
        git_add(files_to_stage)
        log("GIT_ADD", "SUCCESS", "Arquivos adicionados à staging area do Git.")

        # Etapa 5: Git Commit
        action_verb = "atualizar" if is_edit else "cadastrar"
        commit_msg = f"feat(catalogo): {action_verb} produto {nome} ({slug})"
        log("GIT_COMMIT", "INFO", f"Criando commit: '{commit_msg}'...")
        _, commit_hash, commit_out = git_commit(commit_msg)
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


def run_delete_pipeline(slug: str, auto_push: bool = True) -> Dict[str, Any]:
    """
    Executa o fluxo completo para remover um produto do catálogo:
    1. Git Pull origin main
    2. Remove fotos associadas do produto
    3. Remove o registro de data/produtos.json
    4. Git Add e Commit: feat(catalogo): remover produto <nome> (<slug>)
    5. Git Push origin main
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
        log("PRE_FLIGHT", "INFO", "Verificando o repositório local...")
        repo_info = get_repo_status()
        if not repo_info.get("is_git_repo"):
            raise RuntimeError(f"Repositório Git não configurado ou inválido: {repo_info.get('error')}")

        # Git Pull
        log("GIT_PULL", "INFO", f"Executando 'git pull {Config.GIT_REMOTE} {Config.GIT_BRANCH}'...")
        try:
            _, pull_output = git_pull()
            log("GIT_PULL", "SUCCESS", "Repositório sincronizado com sucesso.", pull_output)
        except GitServiceError as e:
            log("GIT_PULL", "WARNING", f"Aviso na sincronização prévia: {e}", e.stderr or e.stdout)

        # Exclui imagens físicas
        log("IMAGE_DELETE", "INFO", f"Removendo fotos associadas a '{slug}'...")
        deleted_images = delete_product_images(slug)
        if deleted_images:
            log("IMAGE_DELETE", "SUCCESS", f"{len(deleted_images)} arquivo(s) de imagem removido(s).", "\n".join(deleted_images))

        # Exclui do JSON
        log("JSON_DELETE", "INFO", f"Removendo produto '{slug}' de data/produtos.json...")
        del_success, removed_prod = delete_product(slug)
        if not del_success or not removed_prod:
            raise ValueError(f"Produto '{slug}' não foi encontrado no catálogo para exclusão.")
            
        prod_name = removed_prod.get("nome", slug)
        log("JSON_DELETE", "SUCCESS", f"Produto '{prod_name}' removido com sucesso de data/produtos.json.")

        # Git Add
        files_to_stage = ["data/produtos.json"] + deleted_images
        log("GIT_ADD", "INFO", f"Preparando alterações para commit: {', '.join(files_to_stage)}")
        git_add(files_to_stage)
        log("GIT_ADD", "SUCCESS", "Alterações adicionadas à staging area.")

        # Git Commit
        commit_msg = f"feat(catalogo): remover produto {prod_name} ({slug})"
        log("GIT_COMMIT", "INFO", f"Criando commit: '{commit_msg}'...")
        _, commit_hash, commit_out = git_commit(commit_msg)
        log("GIT_COMMIT", "SUCCESS", f"Commit criado com sucesso: [{commit_hash}] {commit_msg}", commit_out)

        # Git Push
        if auto_push and Config.ENABLE_AUTO_PUSH:
            log("GIT_PUSH", "INFO", f"Enviando alterações para '{Config.GIT_REMOTE}/{Config.GIT_BRANCH}'...")
            _, push_out = git_push()
            log("GIT_PUSH", "SUCCESS", "Push concluído com sucesso! Deploy disparado no Vercel.", push_out)
            result["pushed"] = True
        else:
            log("GIT_PUSH", "INFO", "Push automático desativado. Alterações salvas localmente.")
            result["pushed"] = False

        result["success"] = True
        result["product"] = removed_prod
        result["commit_hash"] = commit_hash
        result["commit_message"] = commit_msg
        return result

    except Exception as e:
        error_detail = str(e)
        log("ERROR", "ERROR", f"Falha na exclusão do produto: {error_detail}")
        result["success"] = False
        result["error"] = error_detail
        return result


def run_toggle_esgotado_pipeline(slug: str, auto_push: bool = True) -> Dict[str, Any]:
    """
    Executa o fluxo para alternar o status de esgotado de um produto no catálogo:
    1. Git Pull origin main
    2. Alterna 'esgotado' e ajusta selo no data/produtos.json
    3. Git Add e Commit: feat(catalogo): marcar produto <nome> como esgotado / reativar
    4. Git Push origin main
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
        "esgotado": False,
        "commit_hash": None,
        "commit_message": None,
        "pushed": False,
        "error": None
    }

    try:
        log("PRE_FLIGHT", "INFO", "Verificando o repositório local...")
        repo_info = get_repo_status()
        if not repo_info.get("is_git_repo"):
            raise RuntimeError(f"Repositório Git não configurado ou inválido: {repo_info.get('error')}")

        # Git Pull
        log("GIT_PULL", "INFO", f"Executando 'git pull {Config.GIT_REMOTE} {Config.GIT_BRANCH}'...")
        try:
            _, pull_output = git_pull()
            log("GIT_PULL", "SUCCESS", "Repositório sincronizado com sucesso.", pull_output)
        except GitServiceError as e:
            log("GIT_PULL", "WARNING", f"Aviso na sincronização prévia: {e}", e.stderr or e.stdout)

        # Alterna status no JSON
        toggle_success, novo_status, updated_prod = toggle_esgotado_product(slug)
        if not toggle_success or not updated_prod:
            raise ValueError(f"Produto '{slug}' não foi encontrado no catálogo.")

        prod_name = updated_prod.get("nome", slug)
        status_label = "marcado como ESGOTADO" if novo_status else "REATIVADO no catálogo"
        log("STATUS_UPDATE", "SUCCESS", f"Produto '{prod_name}' agora está {status_label}.")

        # Git Add
        files_to_stage = ["data/produtos.json"]
        git_add(files_to_stage)
        log("GIT_ADD", "SUCCESS", "data/produtos.json adicionado à staging area.")

        # Git Commit
        action_verb = "marcar produto como esgotado" if novo_status else "reativar produto"
        commit_msg = f"feat(catalogo): {action_verb} {prod_name} ({slug})"
        log("GIT_COMMIT", "INFO", f"Criando commit: '{commit_msg}'...")
        _, commit_hash, commit_out = git_commit(commit_msg)
        log("GIT_COMMIT", "SUCCESS", f"Commit criado com sucesso: [{commit_hash}] {commit_msg}", commit_out)

        # Git Push
        if auto_push and Config.ENABLE_AUTO_PUSH:
            log("GIT_PUSH", "INFO", f"Enviando alterações para '{Config.GIT_REMOTE}/{Config.GIT_BRANCH}'...")
            _, push_out = git_push()
            log("GIT_PUSH", "SUCCESS", "Push concluído com sucesso! Deploy disparado no Vercel.", push_out)
            result["pushed"] = True
        else:
            log("GIT_PUSH", "INFO", "Push automático desativado. Alterações salvas localmente.")
            result["pushed"] = False

        result["success"] = True
        result["product"] = updated_prod
        result["esgotado"] = novo_status
        result["commit_hash"] = commit_hash
        result["commit_message"] = commit_msg
        return result

    except Exception as e:
        error_detail = str(e)
        log("ERROR", "ERROR", f"Falha ao alterar status do produto: {error_detail}")
        result["success"] = False
        result["error"] = error_detail
        return result

