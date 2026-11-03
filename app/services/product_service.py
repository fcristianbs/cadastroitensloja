import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from app.config import Config

CATEGORIAS_PERMITIDAS = ["engenharia", "casa", "gadgets", "figures"]
MATERIAIS_EXTERNO_PERMITIDOS = {"PETG-UV", "PETG", "ASA"}
MATERIAIS_COMUNS = ["PETG-UV", "PETG", "ASA", "PLA", "TPU", "ABS"]

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
    """Lê data/produtos.json do repositório alvo com encoding UTF-8."""
    path = Config.PRODUTOS_JSON_PATH
    if not path.exists():
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
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


def validate_product_data(data: Dict[str, Any], is_new: bool = True) -> Tuple[bool, List[str]]:
    """
    Valida rigorosamente os dados do produto segundo as regras de negócio:
    - RN01: Slug válido e único (se is_new=True).
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
    elif is_new:
        existing_slugs = get_existing_slugs()
        if slug in existing_slugs:
            errors.append(f"O slug '{slug}' já está cadastrado em outro produto. Escolha um slug único.")
            
    # Validação da Categoria (RN02)
    categoria = (data.get("categoria") or "").strip()
    if not categoria:
        errors.append("O campo 'Categoria' é obrigatório.")
    elif categoria not in CATEGORIAS_PERMITIDAS:
        errors.append(f"Categoria '{categoria}' inválida. Categorias permitidas: {', '.join(CATEGORIAS_PERMITIDAS)}.")
        
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

    produto = {
        "slug": slug,
        "nome": str(data.get("nome", "")).strip(),
        "categoria": str(data.get("categoria", "")).strip(),
        "subcategoria": str(data.get("subcategoria", "")).strip() or "geral",
        "resumo": str(data.get("resumo", "")).strip(),
        "descricao": str(data.get("descricao", "")).strip(),
        "preco": preco,
        "precoParcelado": data.get("precoParcelado") if data.get("precoParcelado") else None,
        "material": str(data.get("material", "")).strip(),
        "uso": str(data.get("uso", "")).strip().lower(),
        "specs_resumo": str(data.get("specs_resumo", "")).strip() or None,
        "destaque": destaque,
        "selo": data.get("selo") if data.get("selo") else None,
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

