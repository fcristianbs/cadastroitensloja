import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import requests
from app.config import Config

MATERIAIS_EXTERNO_PERMITIDOS = {"PETG-UV", "PETG", "ASA"}
MATERIAIS_COMUNS = ["PETG-UV", "PETG", "ASA", "PLA", "TPU", "ABS"]

def load_categorias() -> List[Dict[str, Any]]:
    """
    Carrega dinamicamente a taxonomia de categorias e subcategorias
    a partir de data/categorias.json do repositório local.
    Faz fallback para a API remota da Vercel caso o arquivo local não esteja acessível.
    """
    path = Config.CATEGORIAS_JSON_PATH
    if path and path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"[AVISO] Falha ao ler categorias.json local: {e}")

    # Fallback para API remota
    try:
        url = f"{Config.VERCEL_DEPLOY_URL.rstrip('/')}/api/categorias"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                return data
    except Exception:
        pass

    return []


def get_allowed_category_slugs() -> Set[str]:
    """Retorna os slugs de todas as categorias cadastradas no catálogo."""
    return {c.get("slug") for c in load_categorias() if c.get("slug")}


def get_allowed_subcategories_map() -> Dict[str, List[str]]:
    """
    Retorna um dicionário mapeando cada slug de categoria para a lista de slugs de suas subcategorias.
    Ex: {'casa': ['cozinha', 'decoracao', 'luminaria', ...], 'setup-games': ['desktop', 'games']}
    """
    cat_map: Dict[str, List[str]] = {}
    for cat in load_categorias():
        c_slug = cat.get("slug")
        if not c_slug:
            continue
        subs = []
        for sub in cat.get("subcategorias", []):
            if isinstance(sub, dict):
                s_slug = sub.get("slug")
                if s_slug:
                    subs.append(s_slug)
            elif isinstance(sub, str) and sub:
                subs.append(sub)
        cat_map[c_slug] = subs
    return cat_map


def get_categoria_by_slug(cat_slug: str) -> Optional[Dict[str, Any]]:
    """Busca uma categoria específica pelo seu slug."""
    for cat in load_categorias():
        if cat.get("slug") == cat_slug:
            return cat
    return None

def generate_slug(text: str) -> str:
    """
    Gera um slug amigável em kebab-case a partir de um texto.
    Remove acentos, caracteres especiais e substitui espaços/pontos por hífens.
    Ex: 'Suporte Starlink Mini · Veicular' -> 'suporte-starlink-mini-veicular'
    """
    if not text:
        return ""
    
    # Substituições comuns de símbolos de medidas e pontuações
    text = text.replace("·", "-").replace("/", "-").replace("\\", "-")
    text = text.replace("\"", "").replace("'", "")
    
    # Normaliza unicode (remove acentos e diacríticos)
    nfkd = unicodedata.normalize("NFKD", text)
    clean_text = "".join([c for c in nfkd if not unicodedata.combining(c)])
    
    # Converte para minúsculas
    clean_text = clean_text.lower()
    
    # Substitui qualquer caractere não alfanumérico por hífen
    clean_text = re.sub(r"[^a-z0-9]+", "-", clean_text)
    
    # Remove hífens duplicados e das extremidades
    clean_text = re.sub(r"-+", "-", clean_text).strip("-")
    
    return clean_text


def load_produtos() -> List[Dict[str, Any]]:
    """
    Lê data/produtos.json do repositório alvo com encoding UTF-8.
    Garante retrocompatibilidade automática: se o produto possui apenas 'categoria' ou 'subcategoria',
    popula 'categorias' e 'subcategorias' como listas para consumo uniforme no app.
    """
    path = Config.PRODUTOS_JSON_PATH
    if not path.exists():
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                for p in data:
                    if isinstance(p, dict):
                        if "categorias" not in p or not isinstance(p["categorias"], list):
                            cat_val = p.get("categoria")
                            p["categorias"] = [cat_val] if cat_val else []
                        if "subcategorias" not in p or not isinstance(p["subcategorias"], list):
                            sub_val = p.get("subcategoria")
                            p["subcategorias"] = [sub_val] if sub_val else []
                return data
            return []
    except Exception as e:
        print(f"[ERRO] Falha ao carregar produtos.json: {e}")
        return []


def save_produtos(produtos: List[Dict[str, Any]]) -> bool:
    """
    Salva a lista completa de produtos em data/produtos.json
    com indentação de 2 espaços e ensure_ascii=False.
    """
    path = Config.PRODUTOS_JSON_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Salva com arquivo temporário para evitar corrupção em caso de erro no meio da escrita
    temp_path = path.with_suffix(".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(produtos, f, indent=2, ensure_ascii=False)
            f.write("\n")
            
        temp_path.replace(path)
        return True
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Erro ao salvar data/produtos.json: {str(e)}")


def get_produto_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Busca um produto específico pelo slug."""
    produtos = load_produtos()
    for p in produtos:
        if p.get("slug") == slug:
            return p
    return None


def get_existing_slugs() -> Set[str]:
    """Retorna um conjunto contendo todos os slugs atualmente cadastrados."""
    return {p.get("slug") for p in load_produtos() if p.get("slug")}


def validate_product_data(data: Dict[str, Any], is_new: bool = True, original_slug: Optional[str] = None) -> Tuple[bool, List[str]]:
    """
    Valida rigorosamente os dados do produto segundo as regras de negócio:
    - RN01: Slug válido e único.
    - RN02: Categoria deve ser uma das 4 permitidas.
    - RN05: Se uso == 'externo', material DEVE ser PETG-UV, PETG ou ASA (PLA proibido).
    - Formato de preço, specs, imagens e campos obrigatórios.
    """
    errors: List[str] = []
    
    # Validação do Nome
    nome = (data.get("nome") or "").strip()
    if not nome:
        errors.append("O campo 'Nome do Produto' é obrigatório.")
        
    # Validação do Slug (RN01)
    slug = (data.get("slug") or "").strip()
    if not slug:
        errors.append("O campo 'Slug' é obrigatório.")
    elif not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", slug):
        errors.append("O Slug deve conter apenas letras minúsculas, números e hífens (ex: 'suporte-starlink-mini').")
    else:
        existing_slugs = get_existing_slugs()
        if is_new and slug in existing_slugs:
            errors.append(f"O slug '{slug}' já está cadastrado em outro produto. Escolha um slug único.")
        elif not is_new and original_slug and slug != original_slug and slug in existing_slugs:
            errors.append(f"O novo slug '{slug}' já está em uso por outro produto no catálogo.")
            
    # Validação de Categorias (RN02 - Múltiplas e Dinâmicas)
    raw_cats = data.get("categorias", [])
    if isinstance(raw_cats, str):
        try:
            categorias = json.loads(raw_cats)
        except Exception:
            categorias = [c.strip() for c in raw_cats.split(",") if c.strip()]
    elif isinstance(raw_cats, list):
        categorias = [str(c).strip() for c in raw_cats if str(c).strip()]
    else:
        categorias = []

    # Fallback para campo legado "categoria" se a lista estiver vazia
    categoria_single = (data.get("categoria") or "").strip()
    if not categorias and categoria_single:
        categorias = [categoria_single]

    if not categorias:
        errors.append("Pelo menos uma Categoria deve ser selecionada.")
    else:
        allowed_cats = get_allowed_category_slugs()
        if allowed_cats:
            for cat in categorias:
                if cat not in allowed_cats:
                    errors.append(f"Categoria '{cat}' inválida. Categorias disponíveis no catálogo: {', '.join(sorted(allowed_cats))}.")

    # Validação de Subcategorias
    raw_subs = data.get("subcategorias", [])
    if isinstance(raw_subs, str):
        try:
            subcategorias = json.loads(raw_subs)
        except Exception:
            subcategorias = [s.strip() for s in raw_subs.split(",") if s.strip()]
    elif isinstance(raw_subs, list):
        subcategorias = [str(s).strip() for s in raw_subs if str(s).strip()]
    else:
        subcategorias = []

    subcategoria_single = (data.get("subcategoria") or "").strip()
    if not subcategorias and subcategoria_single:
        subcategorias = [subcategoria_single]

    if not subcategorias:
        # Se nenhuma foi informada, default para 'geral'
        subcategorias = ["geral"]

    # Consistência: as subcategorias selecionadas devem pertencer às categorias ativas
    if categorias and subcategorias:
        allowed_subs_map = get_allowed_subcategories_map()
        valid_subs_for_active_cats = set()
        for cat in categorias:
            for s in allowed_subs_map.get(cat, []):
                valid_subs_for_active_cats.add(str(s).lower().strip())
        valid_subs_for_active_cats.add("geral")

        for sub in subcategorias:
            sub_norm = str(sub).lower().strip()
            if valid_subs_for_active_cats and sub_norm not in valid_subs_for_active_cats:
                errors.append(f"Subcategoria '{sub}' não pertence a nenhuma das categorias selecionadas ({', '.join(categorias)}).")
        
    # Validação de Resumo e Descrição
    resumo = (data.get("resumo") or "").strip()
    if not resumo:
        errors.append("O campo 'Resumo' é obrigatório.")
        
    descricao = (data.get("descricao") or "").strip()
    if not descricao:
        errors.append("O campo 'Descrição' é obrigatório.")
        
    # Validação de Uso e Material (RN05)
    uso = (data.get("uso") or "").strip().lower()
    if uso not in ["externo", "interno"]:
        errors.append("O campo 'Uso' deve ser 'externo' ou 'interno'.")
        
    material = (data.get("material") or "").strip()
    if not material:
        errors.append("O campo 'Material' é obrigatório.")
    else:
        material_upper = material.upper()
        if uso == "externo":
            if "PLA" in material_upper:
                errors.append("Regra RN05 violada: Material 'PLA' NÃO é permitido para uso externo sob sol e chuva.")
            # Normalização para verificar se está na lista permitida
            matched = any(m.upper() == material_upper for m in MATERIAIS_EXTERNO_PERMITIDOS)
            if not matched:
                errors.append(
                    f"Regra RN05: Para uso externo, o material DEVE ser PETG-UV, PETG ou ASA (informado: '{material}')."
                )
        elif uso == "interno":
            # Aceita PLA, PETG, TPU, ABS, etc.
            pass
            
    # Validação de Preço
    preco = data.get("preco")
    if preco is not None and preco != "":
        try:
            p_val = float(preco)
            if p_val < 0:
                errors.append("O preço não pode ser negativo.")
        except (ValueError, TypeError):
            errors.append("Preço inválido. Informe um valor numérico decimal (ex: 129.90) ou deixe em branco para 'Sob consulta'.")
            
    # Validação de Imagens
    imagens = data.get("imagens", [])
    if not isinstance(imagens, list) or len(imagens) == 0:
        errors.append("O produto deve possuir pelo menos uma imagem associada.")
    else:
        for idx, img in enumerate(imagens):
            if not isinstance(img, dict) or not img.get("src"):
                errors.append(f"A imagem #{idx+1} não possui o caminho ('src') definido.")
                
    is_valid = len(errors) == 0
    return is_valid, errors


def build_product_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constrói o dicionário de produto rigorosamente estruturado
    conforme o schema do Voxel Lab para data/produtos.json.
    """
    slug = generate_slug(data.get("slug") or data.get("nome") or "")
    
    # Trata preço
    raw_preco = data.get("preco")
    if raw_preco is not None and raw_preco != "" and raw_preco != "null":
        try:
            preco = round(float(raw_preco), 2)
        except (ValueError, TypeError):
            preco = None
    else:
        preco = None
        
    # Trata ordem
    raw_ordem = data.get("ordem")
    try:
        ordem = int(raw_ordem) if raw_ordem is not None and raw_ordem != "" else 1
    except (ValueError, TypeError):
        ordem = 1
        
    # Trata destaque
    destaque = bool(data.get("destaque", False))
    if isinstance(data.get("destaque"), str):
        destaque = data.get("destaque").lower() in ("true", "1", "on", "yes")

    # Specs
    raw_specs = data.get("specs", [])
    specs = []
    if isinstance(raw_specs, list):
        for s in raw_specs:
            if isinstance(s, dict):
                chave = str(s.get("chave", "")).strip()
                valor = str(s.get("valor", "")).strip()
                if chave and valor:
                    specs.append({"chave": chave, "valor": valor})
                    
    # Variações
    raw_variacoes = data.get("variacoes", [])
    variacoes = []
    if isinstance(raw_variacoes, list):
        for v in raw_variacoes:
            if isinstance(v, dict):
                nome_var = str(v.get("nome", "")).strip()
                opcoes = v.get("opcoes", [])
                if isinstance(opcoes, str):
                    opcoes = [opt.strip() for opt in opcoes.split(",") if opt.strip()]
                elif isinstance(opcoes, list):
                    opcoes = [str(opt).strip() for opt in opcoes if str(opt).strip()]
                
                padrao = str(v.get("padrao", "")).strip() or (opcoes[0] if opcoes else "")
                permite_outra = bool(v.get("permiteOutraMedida", False))
                if isinstance(v.get("permiteOutraMedida"), str):
                    permite_outra = v.get("permiteOutraMedida").lower() in ("true", "1", "yes")
                    
                if nome_var and opcoes:
                    variacoes.append({
                        "nome": nome_var,
                        "opcoes": opcoes,
                        "padrao": padrao,
                        "permiteOutraMedida": permite_outra
                    })

    # Cores
    raw_cores = data.get("cores", [])
    cores = []
    if isinstance(raw_cores, list):
        for c in raw_cores:
            if isinstance(c, dict):
                nome_cor = str(c.get("nome", "")).strip()
                hex_cor = str(c.get("hex", "")).strip()
                is_padrao = bool(c.get("padrao", False))
                if isinstance(c.get("padrao"), str):
                    is_padrao = c.get("padrao").lower() in ("true", "1", "yes")
                if nome_cor and hex_cor:
                    cores.append({
                        "nome": nome_cor,
                        "hex": hex_cor,
                        **({"padrao": True} if is_padrao else {})
                    })
    if not cores:
        # Padrão Voxel Lab se nenhuma for informada
        cores = [
            {"nome": "Preto fosco", "hex": "#111111", "padrao": True},
            {"nome": "Cinza", "hex": "#6B7280"},
            {"nome": "Branco", "hex": "#E8EDF2"}
        ]
    elif not any(c.get("padrao") for c in cores):
        cores[0]["padrao"] = True

    # Imagens
    raw_imagens = data.get("imagens", [])
    imagens = []
    if isinstance(raw_imagens, list):
        for img in raw_imagens:
            if isinstance(img, dict) and img.get("src"):
                imagens.append({
                    "src": str(img.get("src")).strip(),
                    "alt": str(img.get("alt") or data.get("nome", "")).strip(),
                    "tipo": str(img.get("tipo") or "instalada").strip()
                })

    # Instalação
    raw_instalacao = data.get("instalacao", [])
    instalacao = []
    if isinstance(raw_instalacao, list):
        for step in raw_instalacao:
            step_str = str(step).strip()
            if step_str:
                instalacao.append(step_str)
    elif isinstance(raw_instalacao, str):
        instalacao = [s.strip() for s in raw_instalacao.split("\n") if s.strip()]

    # Relacionados
    raw_relacionados = data.get("relacionados", [])
    relacionados = []
    if isinstance(raw_relacionados, list):
        relacionados = [str(r).strip() for r in raw_relacionados if str(r).strip()]
    elif isinstance(raw_relacionados, str):
        relacionados = [r.strip() for r in raw_relacionados.split(",") if r.strip()]

    # Processa Múltiplas Categorias e Categoria Primária
    raw_cats = data.get("categorias", [])
    if isinstance(raw_cats, str):
        try:
            categorias = json.loads(raw_cats)
        except Exception:
            categorias = [c.strip() for c in raw_cats.split(",") if c.strip()]
    elif isinstance(raw_cats, list):
        categorias = [str(c).strip() for c in raw_cats if str(c).strip()]
    else:
        categorias = []

    single_cat = str(data.get("categoria", "")).strip()
    if single_cat and single_cat not in categorias:
        categorias.insert(0, single_cat)
    elif not categorias and single_cat:
        categorias = [single_cat]

    if single_cat and single_cat in categorias:
        primary_cat = single_cat
    elif categorias:
        primary_cat = categorias[0]
    else:
        primary_cat = "outros"

    # Processa Múltiplas Subcategorias e Subcategoria Primária
    raw_subs = data.get("subcategorias", [])
    if isinstance(raw_subs, str):
        try:
            subcategorias = json.loads(raw_subs)
        except Exception:
            subcategorias = [s.strip() for s in raw_subs.split(",") if s.strip()]
    elif isinstance(raw_subs, list):
        subcategorias = [str(s).strip() for s in raw_subs if str(s).strip()]
    else:
        subcategorias = []

    single_sub = str(data.get("subcategoria", "")).strip().lower()
    norm_subs = []
    for s in subcategorias:
        s_lower = str(s).strip().lower()
        if s_lower and s_lower not in norm_subs:
            norm_subs.append(s_lower)
    subcategorias = norm_subs

    if single_sub and single_sub not in subcategorias:
        subcategorias.insert(0, single_sub)
    elif not subcategorias and single_sub:
        subcategorias = [single_sub]

    if single_sub and single_sub in subcategorias:
        primary_sub = single_sub
    elif subcategorias:
        primary_sub = subcategorias[0]
    else:
        primary_sub = "geral"

    produto = {
        "slug": slug,
        "nome": str(data.get("nome", "")).strip(),
        "categoria": primary_cat,
        "subcategoria": primary_sub,
        "categorias": categorias,
        "subcategorias": subcategorias,
        "resumo": str(data.get("resumo", "")).strip(),
        "descricao": str(data.get("descricao", "")).strip(),
        "preco": preco,
        "precoParcelado": data.get("precoParcelado") if data.get("precoParcelado") else None,
        "material": str(data.get("material", "")).strip(),
        "uso": str(data.get("uso", "")).strip().lower(),
        "specs_resumo": str(data.get("specs_resumo", "")).strip() or None,
        "destaque": destaque,
        "selo": data.get("selo") if data.get("selo") else None,
        "esgotado": bool(data.get("esgotado", False)),
        "selo_anterior": data.get("selo_anterior") if data.get("selo_anterior") else None,
        "ordem": ordem,
        "specs": specs,
        "variacoes": variacoes,
        "cores": cores,
        "imagens": imagens,
        "instalacao": instalacao,
        "mercadoLivreUrl": data.get("mercadoLivreUrl") if data.get("mercadoLivreUrl") else None,
        "relacionados": relacionados
    }
    
    return produto


def insert_product(product_record: Dict[str, Any], position: str = "top") -> List[Dict[str, Any]]:
    """Insere o produto no array de produtos.json e salva o arquivo."""
    produtos = load_produtos()
    
    # Remove se já existir com mesmo slug (atualização) ou insere
    produtos = [p for p in produtos if p.get("slug") != product_record.get("slug")]
    
    if position == "top":
        produtos.insert(0, product_record)
    else:
        produtos.append(product_record)
        
    save_produtos(produtos)
    return produtos


def update_product(original_slug: str, product_record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Atualiza um produto existente preservando sua posição original no array de data/produtos.json.
    Se o slug mudou, substitui a entrada anterior pelo novo registro.
    """
    produtos = load_produtos()
    updated = False
    
    for i, p in enumerate(produtos):
        if p.get("slug") == original_slug:
            produtos[i] = product_record
            updated = True
            break
            
    if not updated:
        # Fallback: insere no topo se não encontrou o slug anterior
        produtos.insert(0, product_record)
        
    save_produtos(produtos)
    return produtos


def delete_product(slug: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Remove permanentemente um produto do catálogo data/produtos.json pelo slug.
    Retorna (sucesso, produto_removido).
    """
    produtos = load_produtos()
    removed_product = None
    nova_lista = []
    
    for p in produtos:
        if p.get("slug") == slug:
            removed_product = p
        else:
            nova_lista.append(p)
            
    if removed_product:
        save_produtos(nova_lista)
        return True, removed_product
        
    return False, None


def toggle_esgotado_product(slug: str) -> Tuple[bool, bool, Optional[Dict[str, Any]]]:
    """
    Alterna o status de 'esgotado' de um produto:
    - Se estava esgotado: reativa o produto e restaura o selo anterior.
    - Se estava ativo: marca como esgotado e define o selo como 'ESGOTADO'.
    Retorna (sucesso, novo_status_esgotado, produto_atualizado).
    """
    produtos = load_produtos()
    found_product = None
    novo_status = False
    
    for p in produtos:
        if p.get("slug") == slug:
            esta_esgotado = bool(p.get("esgotado")) or p.get("selo") == "ESGOTADO"
            if esta_esgotado:
                # Reativa o produto
                p["esgotado"] = False
                # Restaura selo anterior se houver
                selo_ant = p.get("selo_anterior")
                p["selo"] = selo_ant if selo_ant and selo_ant != "ESGOTADO" else None
                novo_status = False
            else:
                # Marca como esgotado
                p["esgotado"] = True
                selo_atual = p.get("selo")
                if selo_atual and selo_atual != "ESGOTADO":
                    p["selo_anterior"] = selo_atual
                p["selo"] = "ESGOTADO"
                novo_status = True
                
            found_product = p
            break
            
    if found_product:
        save_produtos(produtos)
        return True, novo_status, found_product
        
    return False, False, None


def get_pending_batch_status() -> Dict[str, Any]:
    """
    Compara o catálogo local (data/produtos.json) com a versão de produção (origin/main ou HEAD)
    para quantificar e detalhar todas as alterações pendentes na fila local:
    - Novos produtos (adicionados)
    - Produtos editados (alterações de dados, esgotado, etc.)
    - Produtos removidos
    - Commits locais não enviados (ahead count)
    """
    from app.services.git_service import get_file_content_from_ref, run_git_command

    local_produtos = load_produtos()
    local_map = {p.get("slug"): p for p in local_produtos if p.get("slug")}

    # Tenta obter a versão remota origin/main; se falhar, tenta HEAD
    ref_to_try = f"{Config.GIT_REMOTE}/{Config.GIT_BRANCH}"
    base_json_str = get_file_content_from_ref(ref_to_try, "data/produtos.json")
    if not base_json_str:
        base_json_str = get_file_content_from_ref("HEAD", "data/produtos.json")

    base_produtos = []
    if base_json_str:
        try:
            parsed = json.loads(base_json_str)
            if isinstance(parsed, list):
                # Normaliza para retrocompatibilidade
                for p in parsed:
                    if isinstance(p, dict):
                        if "categorias" not in p or not isinstance(p["categorias"], list):
                            cat_val = p.get("categoria")
                            p["categorias"] = [cat_val] if cat_val else []
                        if "subcategorias" not in p or not isinstance(p["subcategorias"], list):
                            sub_val = p.get("subcategoria")
                            p["subcategorias"] = [sub_val] if sub_val else []
                base_produtos = parsed
        except Exception:
            base_produtos = []

    base_map = {p.get("slug"): p for p in base_produtos if p.get("slug")}

    novos: List[Dict[str, str]] = []
    editados: List[Dict[str, str]] = []
    removidos: List[Dict[str, str]] = []

    for slug, p in local_map.items():
        if slug not in base_map:
            novos.append({"slug": slug, "nome": p.get("nome", slug), "action": "novo"})
        elif p != base_map[slug]:
            editados.append({"slug": slug, "nome": p.get("nome", slug), "action": "editado"})

    for slug, p in base_map.items():
        if slug not in local_map:
            removidos.append({"slug": slug, "nome": p.get("nome", slug), "action": "removido"})

    # Verifica commits ahead no git
    code, ahead_out, _ = run_git_command(["rev-list", f"{Config.GIT_REMOTE}/{Config.GIT_BRANCH}..HEAD", "--count"])
    try:
        ahead_count = int(ahead_out) if code == 0 else 0
    except Exception:
        ahead_count = 0

    total_changes = len(novos) + len(editados) + len(removidos)
    has_pending = total_changes > 0 or ahead_count > 0

    # Monta texto resumo amigável
    parts = []
    if len(novos) > 0:
        parts.append(f"{len(novos)} novo{'s' if len(novos) > 1 else ''}")
    if len(editados) > 0:
        parts.append(f"{len(editados)} editado{'s' if len(editados) > 1 else ''}")
    if len(removidos) > 0:
        parts.append(f"{len(removidos)} removido{'s' if len(removidos) > 1 else ''}")

    if total_changes > 0:
        detalhe = f" ({', '.join(parts)})" if parts else ""
        summary_text = f"{total_changes} alteraç{'ões' if total_changes > 1 else 'ão'} local{'is' if total_changes > 1 else ''} pronta{'s' if total_changes > 1 else ''}{detalhe}"
    elif ahead_count > 0:
        summary_text = f"{ahead_count} commit{'s' if ahead_count > 1 else ''} pendente{'s' if ahead_count > 1 else ''} de push para a Vercel"
    else:
        summary_text = "Catálogo sincronizado com a Vercel"

    return {
        "has_pending": has_pending,
        "total_pending": total_changes if total_changes > 0 else ahead_count,
        "novos_count": len(novos),
        "editados_count": len(editados),
        "removidos_count": len(removidos),
        "ahead_count": ahead_count,
        "novos": novos,
        "editados": editados,
        "removidos": removidos,
        "all_pending_items": novos + editados + removidos,
        "summary_text": summary_text
    }


def discard_pending_changes() -> Tuple[bool, str]:
    """
    Descarta todas as alterações locais não publicadas e restaura o catálogo
    ao estado do último commit do repositório.
    """
    from app.services.git_service import git_discard_changes
    success, msg = git_discard_changes()
    return success, msg

