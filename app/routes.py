import json
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    current_app
)
from app.config import Config
from app.services.git_service import get_repo_status, git_pull
from app.services.product_service import (
    load_produtos,
    get_produto_by_slug,
    get_existing_slugs,
    load_categorias,
    MATERIAIS_COMUNS
)
from app.services.publisher import run_publish_pipeline

main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)

@main_bp.route('/')
def index():
    """Página principal: Formulário de cadastro de produtos com live preview."""
    produtos = load_produtos()
    repo_status = get_repo_status()
    categorias = load_categorias()
    
    # Produto modelo (se o usuário clicou em 'Usar como Modelo' na lista de produtos)
    clone_slug = request.args.get('clone')
    clone_data = get_produto_by_slug(clone_slug) if clone_slug else None

    return render_template(
        'index.html',
        produtos=produtos,
        repo_status=repo_status,
        categorias=categorias,
        materiais=MATERIAIS_COMUNS,
        clone_data=clone_data,
        edit_data=None,
        is_edit=False,
        active_tab='cadastrar'
    )


@main_bp.route('/editar/<slug>')
def editar_produto(slug):
    """Página de edição de um produto existente do catálogo."""
    produtos = load_produtos()
    repo_status = get_repo_status()
    produto = get_produto_by_slug(slug)
    categorias = load_categorias()
    
    if not produto:
        flash(f"Produto com slug '{slug}' não foi encontrado no catálogo.", 'danger')
        return redirect(url_for('main.produtos_list'))

    return render_template(
        'index.html',
        produtos=produtos,
        repo_status=repo_status,
        categorias=categorias,
        materiais=MATERIAIS_COMUNS,
        clone_data=None,
        edit_data=produto,
        is_edit=True,
        original_slug=slug,
        active_tab='produtos'
    )


@main_bp.route('/produtos')
def produtos_list():
    """Página de listagem e consulta dos produtos já cadastrados em data/produtos.json."""
    produtos = load_produtos()
    categorias = load_categorias()
    total = len(produtos)
    destaques = sum(1 for p in produtos if p.get('destaque'))
    
    # Contagem por categoria
    categorias_count = {}
    for p in produtos:
        cat = p.get('categoria', 'outros')
        categorias_count[cat] = categorias_count.get(cat, 0) + 1

    return render_template(
        'produtos.html',
        produtos=produtos,
        categorias=categorias,
        total=total,
        destaques=destaques,
        categorias_count=categorias_count,
        active_tab='produtos'
    )


@main_bp.route('/git-status')
def git_status_page():
    """Página de diagnóstico e operações manuais do Git."""
    repo_status = get_repo_status()
    return render_template(
        'git_status.html',
        repo_status=repo_status,
        active_tab='git'
    )


@main_bp.route('/cadastrar', methods=['POST'])
def cadastrar_produto():
    """Recebe a submissão do formulário de produto e executa o pipeline."""
    # Extração de campos do formulário
    raw_data = {
        'nome': request.form.get('nome', '').strip(),
        'slug': request.form.get('slug', '').strip(),
        'categoria': request.form.get('categoria', '').strip(),
        'subcategoria': request.form.get('subcategoria', '').strip(),
        'resumo': request.form.get('resumo', '').strip(),
        'descricao': request.form.get('descricao', '').strip(),
        'preco': request.form.get('preco', '').strip(),
        'precoParcelado': request.form.get('precoParcelado', '').strip(),
        'material': request.form.get('material', '').strip(),
        'uso': request.form.get('uso', '').strip(),
        'specs_resumo': request.form.get('specs_resumo', '').strip(),
        'destaque': request.form.get('destaque') in ('true', '1', 'on', 'yes'),
        'selo': request.form.get('selo', '').strip() or None,
        'ordem': request.form.get('ordem', '1'),
        'mercadoLivreUrl': request.form.get('mercadoLivreUrl', '').strip() or None,
        'imagem_alt': request.form.get('imagem_alt', '').strip(),
        'imagem_tipo': request.form.get('imagem_tipo', 'instalada').strip(),
        'original_slug': request.form.get('original_slug', '').strip(),
        'is_edit': bool(request.form.get('original_slug', '').strip()),
    }

    # Processamento de Specs
    specs_json = request.form.get('specs_json')
    if specs_json:
        try:
            raw_data['specs'] = json.loads(specs_json)
        except Exception:
            raw_data['specs'] = []
    else:
        # Fallback para listas de inputs normais
        chaves = request.form.getlist('spec_chave[]')
        valores = request.form.getlist('spec_valor[]')
        raw_data['specs'] = [
            {'chave': c.strip(), 'valor': v.strip()}
            for c, v in zip(chaves, valores)
            if c.strip() and v.strip()
        ]

    # Processamento de Variações
    variacoes_json = request.form.get('variacoes_json')
    if variacoes_json:
        try:
            raw_data['variacoes'] = json.loads(variacoes_json)
        except Exception:
            raw_data['variacoes'] = []
    else:
        var_nomes = request.form.getlist('var_nome[]')
        var_opcoes = request.form.getlist('var_opcoes[]')
        var_padroes = request.form.getlist('var_padrao[]')
        var_outras = request.form.getlist('var_permiteOutra[]')
        
        variacoes = []
        for i in range(len(var_nomes)):
            nome_v = var_nomes[i].strip()
            if nome_v:
                ops = [o.strip() for o in var_opcoes[i].split(',') if o.strip()]
                padrao = var_padroes[i].strip() if i < len(var_padroes) else (ops[0] if ops else '')
                permite = (i < len(var_outras) and var_outras[i] in ('true', '1', 'on', 'yes'))
                variacoes.append({
                    'nome': nome_v,
                    'opcoes': ops,
                    'padrao': padrao,
                    'permiteOutraMedida': permite
                })
        raw_data['variacoes'] = variacoes

    # Processamento de Cores
    cores_json = request.form.get('cores_json')
    if cores_json:
        try:
            raw_data['cores'] = json.loads(cores_json)
        except Exception:
            raw_data['cores'] = []
    else:
        cor_nomes = request.form.getlist('cor_nome[]')
        cor_hexs = request.form.getlist('cor_hex[]')
        cor_padrao_idx = request.form.get('cor_padrao_index', '0')
        try:
            padrao_idx = int(cor_padrao_idx)
        except ValueError:
            padrao_idx = 0
            
        cores = []
        for i in range(len(cor_nomes)):
            cnome = cor_nomes[i].strip()
            chex = cor_hexs[i].strip()
            if cnome and chex:
                cores.append({
                    'nome': cnome,
                    'hex': chex,
                    'padrao': (i == padrao_idx)
                })
        raw_data['cores'] = cores

    # Processamento de Passos de Instalação
    instalacao_json = request.form.get('instalacao_json')
    if instalacao_json:
        try:
            raw_data['instalacao'] = json.loads(instalacao_json)
        except Exception:
            raw_data['instalacao'] = []
    else:
        passos = request.form.getlist('instalacao_passo[]')
        raw_data['instalacao'] = [p.strip() for p in passos if p.strip()]

    # Relacionados
    raw_data['relacionados'] = request.form.getlist('relacionados[]')
    
    # Auto Push
    auto_push = request.form.get('auto_push', 'true').lower() in ('true', '1', 'on', 'yes')

    # Foto
    foto_file = request.files.get('foto')

    # Executa o pipeline
    pipeline_result = run_publish_pipeline(
        raw_data=raw_data,
        image_file=foto_file,
        auto_push=auto_push
    )

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')

    if is_ajax:
        return jsonify(pipeline_result)

    if pipeline_result['success']:
        flash(f"Produto '{raw_data.get('nome')}' cadastrado com sucesso! Commit: {pipeline_result.get('commit_hash')}", 'success')
        return redirect(url_for('main.produtos_list'))
    else:
        flash(f"Erro ao cadastrar produto: {pipeline_result.get('error')}", 'danger')
        return redirect(url_for('main.index'))


# ==============================================================================
# API Endpoints
# ==============================================================================

@api_bp.route('/categorias', methods=['GET'])
def api_get_categorias():
    """Retorna todas as categorias e subcategorias carregadas dinamicamente."""
    return jsonify(load_categorias())


@api_bp.route('/produtos', methods=['GET'])
def api_get_produtos():
    """Retorna a lista completa de produtos cadastrados."""
    return jsonify(load_produtos())


@api_bp.route('/check-slug', methods=['GET'])
def api_check_slug():
    """Verifica se um slug já está em uso."""
    slug = request.args.get('slug', '').strip()
    if not slug:
        return jsonify({'available': False, 'message': 'Slug não fornecido.'})
        
    slugs = get_existing_slugs()
    is_available = slug not in slugs
    return jsonify({
        'slug': slug,
        'available': is_available,
        'message': 'Disponível' if is_available else 'Já cadastrado no catálogo'
    })


@api_bp.route('/git/status', methods=['GET'])
def api_git_status():
    """Retorna informações em tempo real do repositório Git."""
    return jsonify(get_repo_status())


@api_bp.route('/git/pull', methods=['POST'])
def api_git_pull():
    """Executa 'git pull' manualmente."""
    try:
        success, output = git_pull()
        return jsonify({'success': True, 'output': output})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/git/push', methods=['POST'])
def api_git_push():
    """Executa 'git push' manualmente com retries para reenviar commits pendentes."""
    from app.services.git_service import git_push
    try:
        success, output = git_push()
        return jsonify({'success': True, 'output': output})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

