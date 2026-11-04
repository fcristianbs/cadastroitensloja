/**
 * VOXEL LAB · Painel Administrativo de Produtos
 * Interatividade, Validação RN05, Live Preview e Automação Git
 */

document.addEventListener('DOMContentLoaded', () => {
  initSlugGenerator();
  initMaterialUsoRule();
  initPhotoDropzone();
  initSpecsBuilder();
  initVariacoesBuilder();
  initCoresBuilder();
  initInstalacaoBuilder();
  initLivePreview();
  initPublishPipeline();
  initGitPullAction();
});

// =============================================================================
// 1. Slug Generator & Unicidade
// =============================================================================
function slugify(text) {
  if (!text) return '';
  return text
    .toString()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/·/g, '-')
    .replace(/[\/\\"]/g, '-')
    .replace(/[']/g, '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function initSlugGenerator() {
  const nomeInput = document.getElementById('input-nome');
  const slugInput = document.getElementById('input-slug');
  const slugBadge = document.getElementById('slug-badge');
  const origSlugInput = document.getElementById('input-original-slug');
  if (!nomeInput || !slugInput) return;

  const isEditMode = !!origSlugInput && origSlugInput.value.trim().length > 0;
  let userEditedSlug = isEditMode || slugInput.value.trim().length > 0;
  let debounceTimeout = null;

  if (isEditMode && slugInput.value.trim()) {
    checkSlugAvailability(slugInput.value.trim());
  }

  nomeInput.addEventListener('input', () => {
    if (!userEditedSlug) {
      slugInput.value = slugify(nomeInput.value);
      checkSlugAvailability(slugInput.value);
    }
  });

  slugInput.addEventListener('input', () => {
    userEditedSlug = true;
    slugInput.value = slugify(slugInput.value);
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
      checkSlugAvailability(slugInput.value);
    }, 300);
  });

  function checkSlugAvailability(slug) {
    if (!slug) {
      if (slugBadge) slugBadge.style.display = 'none';
      return;
    }

    if (isEditMode && origSlugInput && slug === origSlugInput.value) {
      if (slugBadge) {
        slugBadge.style.display = 'inline-block';
        slugBadge.className = 'input-badge valid';
        slugBadge.textContent = 'SLUG ATUAL';
      }
      return;
    }

    fetch(`/api/check-slug?slug=${encodeURIComponent(slug)}`)
      .then(r => r.json())
      .then(data => {
        if (!slugBadge) return;
        slugBadge.style.display = 'inline-block';
        if (data.available) {
          slugBadge.className = 'input-badge valid';
          slugBadge.textContent = 'DISPONÍVEL';
        } else {
          slugBadge.className = 'input-badge invalid';
          slugBadge.textContent = 'JÁ CADASTRADO';
        }
      })
      .catch(() => {});
  }
}

// =============================================================================
// 2. Validação RN05 (Uso vs Material)
// =============================================================================
function initMaterialUsoRule() {
  const usoSelect = document.getElementById('select-uso');
  const materialInput = document.getElementById('input-material');
  const ruleAlert = document.getElementById('rn05-alert-box');
  const materialChipsContainer = document.getElementById('material-chips');

  if (!usoSelect || !materialInput || !ruleAlert) return;

  function validateRN05() {
    const uso = usoSelect.value;
    const material = (materialInput.value || '').trim().toUpperCase();

    if (uso === 'externo') {
      if (material.includes('PLA')) {
        ruleAlert.className = 'rule-alert-box violation';
        ruleAlert.innerHTML = `⚠️ <strong>Regra RN05 Violada:</strong> Peças para uso <strong>externo</strong> não podem usar material <strong>PLA</strong> (deforma ao sol e chuva). Use obrigatoriamente <strong>PETG-UV</strong>, <strong>PETG</strong> ou <strong>ASA</strong>.`;
        ruleAlert.style.display = 'flex';
        return false;
      } else if (material && !['PETG-UV', 'PETG', 'ASA'].includes(material)) {
        ruleAlert.className = 'rule-alert-box violation';
        ruleAlert.innerHTML = `⚠️ <strong>Atenção RN05:</strong> Para uso externo sob sol e intempéries, o catálogo exige <strong>PETG-UV</strong>, <strong>PETG</strong> ou <strong>ASA</strong>.`;
        ruleAlert.style.display = 'flex';
        return false;
      } else {
        ruleAlert.className = 'rule-alert-box';
        ruleAlert.innerHTML = `🛡️ <strong>RN05 OK:</strong> Material adequado para alta resistência UV e uso externo.`;
        ruleAlert.style.display = 'flex';
        return true;
      }
    } else {
      ruleAlert.className = 'rule-alert-box';
      ruleAlert.innerHTML = `ℹ️ Uso interno selecionado. Materiais permitidos: PLA, PETG, TPU, etc.`;
      ruleAlert.style.display = 'flex';
      return true;
    }
  }

  usoSelect.addEventListener('change', () => {
    updateMaterialChips();
    validateRN05();
  });

  materialInput.addEventListener('input', validateRN05);

  function updateMaterialChips() {
    if (!materialChipsContainer) return;
    const uso = usoSelect.value;
    const materials = uso === 'externo' 
      ? ['PETG-UV', 'PETG', 'ASA'] 
      : ['PLA', 'PETG', 'TPU', 'ABS'];

    materialChipsContainer.innerHTML = '';
    materials.forEach(mat => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip-btn';
      btn.textContent = mat;
      btn.addEventListener('click', () => {
        materialInput.value = mat;
        materialInput.dispatchEvent(new Event('input'));
      });
      materialChipsContainer.appendChild(btn);
    });
  }

  updateMaterialChips();
  validateRN05();
}

// =============================================================================
// 3. Upload & Dropzone de Imagens
// =============================================================================
let currentImageSrc = '';

function initPhotoDropzone() {
  const dropzone = document.getElementById('photo-dropzone');
  const fileInput = document.getElementById('input-foto');
  const previewBox = document.getElementById('photo-preview-container');
  const previewThumb = document.getElementById('photo-preview-thumb');
  const previewName = document.getElementById('photo-preview-name');
  const previewPaths = document.getElementById('photo-preview-paths');
  const slugInput = document.getElementById('input-slug');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      fileInput.files = e.dataTransfer.files;
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  });

  function handleFileSelected(file) {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    const currentSlug = slugInput ? (slugInput.value || 'produto') : 'produto';
    const targetName = `${currentSlug}.${ext === 'jpeg' ? 'jpg' : ext}`;

    const reader = new FileReader();
    reader.onload = (e) => {
      currentImageSrc = e.target.result;
      if (previewBox) previewBox.style.display = 'flex';
      if (previewThumb) previewThumb.src = currentImageSrc;
      if (previewName) previewName.textContent = `${file.name} ➔ ${targetName} (${(file.size / 1024).toFixed(1)} KB)`;
      if (previewPaths) {
        previewPaths.textContent = `Salvará em: static/img/produtos/${targetName} e public/static/...`;
      }
      // Notifica live preview
      document.dispatchEvent(new CustomEvent('product-image-updated', { detail: { src: currentImageSrc } }));
    };
    reader.readAsDataURL(file);
  }
}

// =============================================================================
// 4. Construtor Dinâmico de Especificações (Specs)
// =============================================================================
function initSpecsBuilder() {
  const container = document.getElementById('specs-container');
  const btnAdd = document.getElementById('btn-add-spec');
  const chips = document.querySelectorAll('.spec-preset-chip');

  if (!container || !btnAdd) return;

  function addSpecRow(chave = '', valor = '') {
    const row = document.createElement('div');
    row.className = 'dynamic-row spec-row';
    row.innerHTML = `
      <input type="text" class="form-control spec-chave" placeholder="CHAVE (ex: MATERIAL)" value="${chave}" style="width: 35%;">
      <input type="text" class="form-control spec-valor" placeholder="VALOR (ex: PETG-UV)" value="${valor}" style="flex: 1;">
      <button type="button" class="btn-remove-row" title="Remover"><i class="fas fa-trash-alt"></i></button>
    `;
    row.querySelector('.btn-remove-row').addEventListener('click', () => {
      row.remove();
      updateLiveSpecs();
    });
    row.querySelectorAll('input').forEach(inp => inp.addEventListener('input', updateLiveSpecs));
    container.appendChild(row);
    updateLiveSpecs();
  }

  btnAdd.addEventListener('click', () => addSpecRow());

  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const key = chip.getAttribute('data-key');
      const val = chip.getAttribute('data-val') || '';
      addSpecRow(key, val);
    });
  });

  // Se o container estiver vazio, adiciona presets padrão Voxel Lab
  if (container.children.length === 0) {
    addSpecRow('MATERIAL', 'PETG-UV');
    addSpecRow('CAMADA', '0,20 mm');
    addSpecRow('PREENCHIMENTO', '40% gyroid');
    addSpecRow('USO', 'Externo, sol e chuva');
    addSpecRow('PRAZO', '3 a 5 dias úteis');
  }

  function updateLiveSpecs() {
    document.dispatchEvent(new CustomEvent('product-specs-updated'));
  }
}

// =============================================================================
// 5. Construtor de Variações
// =============================================================================
function initVariacoesBuilder() {
  const container = document.getElementById('variacoes-container');
  const btnAdd = document.getElementById('btn-add-var');
  if (!container || !btnAdd) return;

  function addVarRow(nome = '', opcoes = '', padrao = '', permite = false) {
    const row = document.createElement('div');
    row.className = 'dynamic-row var-row';
    row.style.background = 'var(--surface-overlay)';
    row.style.padding = '0.75rem';
    row.style.borderRadius = 'var(--radius-md)';
    row.style.flexDirection = 'column';
    row.style.alignItems = 'stretch';
    row.style.gap = '0.5rem';

    row.innerHTML = `
      <div style="display: flex; gap: 0.5rem; align-items: center;">
        <input type="text" class="form-control var-nome" placeholder="Nome da Variação (ex: Fixação, Antena)" value="${nome}" style="flex: 1;">
        <button type="button" class="btn-remove-row" title="Remover"><i class="fas fa-trash-alt"></i></button>
      </div>
      <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 0.5rem;">
        <input type="text" class="form-control var-opcoes" placeholder="Opções separadas por vírgula (ex: Rack, Mastro, Teto)" value="${opcoes}">
        <input type="text" class="form-control var-padrao" placeholder="Opção Padrão" value="${padrao}">
      </div>
      <label style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; color: var(--ink-muted); cursor: pointer;">
        <input type="checkbox" class="var-permite" ${permite ? 'checked' : ''}>
        Permite Outra Medida (redireciona para Orçamento Sob Medida)
      </label>
    `;

    row.querySelector('.btn-remove-row').addEventListener('click', () => row.remove());
    container.appendChild(row);
  }

  btnAdd.addEventListener('click', () => addVarRow());
}

// =============================================================================
// 6. Construtor de Cores
// =============================================================================
function initCoresBuilder() {
  const container = document.getElementById('cores-container');
  const btnAdd = document.getElementById('btn-add-cor');
  if (!container || !btnAdd) return;

  function addColorRow(nome = 'Preto fosco', hex = '#111111', isPadrao = false) {
    const row = document.createElement('div');
    row.className = 'color-item-row';
    row.innerHTML = `
      <input type="color" class="color-swatch-picker" value="${hex}">
      <input type="text" class="form-control cor-nome" placeholder="Nome da Cor (ex: Preto fosco)" value="${nome}" style="flex: 1;">
      <input type="text" class="form-control cor-hex" placeholder="#111111" value="${hex}" style="width: 90px; font-family: var(--font-mono);">
      <label style="display: flex; align-items: center; gap: 0.35rem; font-size: 0.8rem; color: var(--ink-muted); cursor: pointer;">
        <input type="radio" name="cor_padrao_radio" class="cor-padrao" ${isPadrao ? 'checked' : ''}>
        Padrão
      </label>
      <button type="button" class="btn-remove-row" title="Remover"><i class="fas fa-trash-alt"></i></button>
    `;

    const picker = row.querySelector('.color-swatch-picker');
    const hexInput = row.querySelector('.cor-hex');
    picker.addEventListener('input', () => hexInput.value = picker.value);
    hexInput.addEventListener('input', () => {
      if (/^#[0-9A-Fa-f]{6}$/.test(hexInput.value)) picker.value = hexInput.value;
    });

    row.querySelector('.btn-remove-row').addEventListener('click', () => row.remove());
    container.appendChild(row);
  }

  btnAdd.addEventListener('click', () => addColorRow('Nova Cor', '#33D1E0', false));

  // Inicia com cores da Voxel Lab se vazio
  if (container.children.length === 0) {
    addColorRow('Preto fosco', '#111111', true);
    addColorRow('Cinza', '#6B7280', false);
    addColorRow('Branco', '#E8EDF2', false);
  }
}

// =============================================================================
// 7. Construtor de Passos de Instalação
// =============================================================================
function initInstalacaoBuilder() {
  const container = document.getElementById('instalacao-container');
  const btnAdd = document.getElementById('btn-add-step');
  if (!container || !btnAdd) return;

  function addStepRow(text = '') {
    const index = container.children.length + 1;
    const row = document.createElement('div');
    row.className = 'dynamic-row step-row';
    row.innerHTML = `
      <span style="font-family: var(--font-mono); font-weight: 700; color: var(--cad); width: 24px;">${String(index).padStart(2, '0')}.</span>
      <input type="text" class="form-control step-input" placeholder="Passo da instalação (ex: Fixe a base no mastro...)" value="${text}" style="flex: 1;">
      <button type="button" class="btn-remove-row" title="Remover"><i class="fas fa-trash-alt"></i></button>
    `;
    row.querySelector('.btn-remove-row').addEventListener('click', () => {
      row.remove();
      renumberSteps();
    });
    container.appendChild(row);
  }

  function renumberSteps() {
    Array.from(container.children).forEach((row, i) => {
      const span = row.querySelector('span');
      if (span) span.textContent = `${String(i + 1).padStart(2, '0')}.`;
    });
  }

  btnAdd.addEventListener('click', () => addStepRow());
}

// =============================================================================
// 8. Live Preview Card em Tempo Real
// =============================================================================
function initLivePreview() {
  const nomeInput = document.getElementById('input-nome');
  const catSelect = document.getElementById('select-categoria');
  const subcatInput = document.getElementById('input-subcategoria');
  const resumoInput = document.getElementById('input-resumo');
  const precoInput = document.getElementById('input-preco');
  const parceladoInput = document.getElementById('input-preco-parcelado');
  const seloInput = document.getElementById('input-selo');
  const usoSelect = document.getElementById('select-uso');
  const materialInput = document.getElementById('input-material');

  // Elementos do Preview
  const prevTitle = document.getElementById('preview-title');
  const prevCat = document.getElementById('preview-category');
  const prevSummary = document.getElementById('preview-summary');
  const prevPrice = document.getElementById('preview-price');
  const prevParcelas = document.getElementById('preview-installments');
  const prevSelo = document.getElementById('preview-selo');
  const prevUso = document.getElementById('preview-uso');
  const prevImg = document.getElementById('preview-img');
  const prevPlaceholder = document.getElementById('preview-placeholder');
  const prevSpecsBar = document.getElementById('preview-specs-bar');

  function updatePreview() {
    if (prevTitle && nomeInput) prevTitle.textContent = nomeInput.value.trim() || 'Nome do Produto';
    if (prevCat && catSelect) {
      const sub = subcatInput ? subcatInput.value.trim() : '';
      prevCat.textContent = `${catSelect.value || 'ENGENHARIA'} ${sub ? '· ' + sub : ''}`;
    }
    if (prevSummary && resumoInput) prevSummary.textContent = resumoInput.value.trim() || 'Resumo curto destacando a utilidade da peça.';

    // Preço
    if (prevPrice && precoInput) {
      const val = parseFloat(precoInput.value);
      if (!isNaN(val) && val > 0) {
        prevPrice.textContent = `R$ ${val.toFixed(2).replace('.', ',')}`;
      } else {
        prevPrice.textContent = 'Sob consulta';
      }
    }

    // Parcelamento
    if (prevParcelas && parceladoInput) {
      prevParcelas.textContent = parceladoInput.value.trim() || 'ou em até 12x no Mercado Livre';
    }

    // Selo
    if (prevSelo && seloInput) {
      const s = seloInput.value.trim();
      if (s) {
        prevSelo.textContent = s;
        prevSelo.style.display = 'block';
      } else {
        prevSelo.style.display = 'none';
      }
    }

    // Uso
    if (prevUso && usoSelect) {
      const u = usoSelect.value;
      prevUso.textContent = u === 'externo' ? 'EXTERNO · UV' : 'INTERNO';
    }

    // Specs Bar
    if (prevSpecsBar && materialInput) {
      const mat = materialInput.value.trim() || 'PETG-UV';
      prevSpecsBar.innerHTML = `<span class="spec-chip">${mat}</span>`;
      const specRows = document.querySelectorAll('.spec-row');
      specRows.forEach(r => {
        const k = r.querySelector('.spec-chave').value.trim();
        const v = r.querySelector('.spec-valor').value.trim();
        if (k && v && k !== 'MATERIAL') {
          prevSpecsBar.innerHTML += `<span class="spec-chip">${v}</span>`;
        }
      });
    }
  }

  [nomeInput, catSelect, subcatInput, resumoInput, precoInput, parceladoInput, seloInput, usoSelect, materialInput].forEach(inp => {
    if (inp) inp.addEventListener('input', updatePreview);
  });

  document.addEventListener('product-image-updated', (e) => {
    if (prevImg && prevPlaceholder) {
      prevImg.src = e.detail.src;
      prevImg.style.display = 'block';
      prevPlaceholder.style.display = 'none';
    }
  });

  document.addEventListener('product-specs-updated', updatePreview);

  updatePreview();
}

// =============================================================================
// 9. Pipeline de Publicação e Deploy com Modal de Terminal
// =============================================================================
function initPublishPipeline() {
  const form = document.getElementById('product-form');
  const modal = document.getElementById('deploy-modal');
  const terminal = document.getElementById('terminal-log-content');
  const progressBar = document.getElementById('deploy-progress-fill');
  const btnClose = document.getElementById('modal-btn-close');
  const btnViewSite = document.getElementById('modal-btn-view-site');
  const btnRetryPush = document.getElementById('modal-btn-retry-push');

  if (!form || !modal || !terminal) return;

  if (btnRetryPush) {
    btnRetryPush.addEventListener('click', async () => {
      btnRetryPush.disabled = true;
      btnRetryPush.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando Push...';
      addTerminalLog('GIT_PUSH', 'INFO', 'Tentando novamente enviar push para o GitHub (origin/main)...');
      try {
        const res = await fetch('/api/git/push', { method: 'POST' });
        const pData = await res.json();
        if (pData.success) {
          if (progressBar) progressBar.style.background = 'linear-gradient(90deg, var(--nozzle), var(--cad))';
          addTerminalLog('GIT_PUSH', 'SUCCESS', 'Push concluído com sucesso no GitHub! Deploy iniciado no Vercel.', pData.output);
          btnRetryPush.style.display = 'none';
          if (btnViewSite) btnViewSite.style.display = 'inline-flex';
        } else {
          addTerminalLog('GIT_PUSH', 'ERROR', `Falha no push: ${pData.error}`);
          btnRetryPush.disabled = false;
          btnRetryPush.innerHTML = '<i class="fas fa-arrows-rotate"></i> Tentar Novamente';
        }
      } catch (err) {
        addTerminalLog('NETWORK', 'ERROR', `Erro de conexão: ${err.message}`);
        btnRetryPush.disabled = false;
        btnRetryPush.innerHTML = '<i class="fas fa-arrows-rotate"></i> Tentar Novamente';
      }
    });
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Validação básica front-end
    const nome = document.getElementById('input-nome').value.trim();
    if (!nome) {
      alert('Por favor, informe o Nome do Produto.');
      return;
    }

    // Serializa Specs
    const specs = [];
    document.querySelectorAll('.spec-row').forEach(row => {
      const chave = row.querySelector('.spec-chave').value.trim();
      const valor = row.querySelector('.spec-valor').value.trim();
      if (chave && valor) specs.push({ chave, valor });
    });

    // Serializa Variações
    const variacoes = [];
    document.querySelectorAll('.var-row').forEach(row => {
      const nomeVar = row.querySelector('.var-nome').value.trim();
      const opcoesStr = row.querySelector('.var-opcoes').value.trim();
      const padrao = row.querySelector('.var-padrao').value.trim();
      const permite = row.querySelector('.var-permite').checked;
      if (nomeVar && opcoesStr) {
        variacoes.push({
          nome: nomeVar,
          opcoes: opcoesStr.split(',').map(s => s.trim()).filter(Boolean),
          padrao: padrao || opcoesStr.split(',')[0].trim(),
          permiteOutraMedida: permite
        });
      }
    });

    // Serializa Cores
    const cores = [];
    document.querySelectorAll('.color-item-row').forEach(row => {
      const cnome = row.querySelector('.cor-nome').value.trim();
      const chex = row.querySelector('.cor-hex').value.trim();
      const cpadrao = row.querySelector('.cor-padrao').checked;
      if (cnome && chex) {
        cores.push({ nome: cnome, hex: chex, padrao: cpadrao });
      }
    });

    // Serializa Instalação
    const instalacao = [];
    document.querySelectorAll('.step-row').forEach(row => {
      const val = row.querySelector('.step-input').value.trim();
      if (val) instalacao.push(val);
    });

    // Monta FormData
    const formData = new FormData(form);
    formData.set('specs_json', JSON.stringify(specs));
    formData.set('variacoes_json', JSON.stringify(variacoes));
    formData.set('cores_json', JSON.stringify(cores));
    formData.set('instalacao_json', JSON.stringify(instalacao));

    // Abre o Modal
    modal.classList.add('active');
    terminal.innerHTML = '';
    if (progressBar) progressBar.style.width = '15%';

    addTerminalLog('INIT', 'INFO', 'Iniciando pipeline de automação Git & Publicação...');

    try {
      if (progressBar) progressBar.style.width = '45%';
      
      const response = await fetch('/cadastrar', {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json'
        },
        body: formData
      });

      const data = await response.json();

      if (data.logs && Array.isArray(data.logs)) {
        data.logs.forEach(log => {
          addTerminalLog(log.step, log.status, log.message, log.detail);
        });
      }

      if (data.success) {
        if (progressBar) progressBar.style.width = '100%';
        addTerminalLog('DEPLOY', 'SUCCESS', `🚀 Produto '${data.product.nome}' publicado com sucesso!`);
        if (data.commit_hash) {
          addTerminalLog('GIT', 'SUCCESS', `Commit registrado: ${data.commit_hash} - ${data.commit_message}`);
        }
        if (data.pushed) {
          addTerminalLog('VERCEL', 'SUCCESS', 'Repositório atualizado no GitHub! O Vercel está compilando o novo catálogo.');
        }
        if (btnViewSite) btnViewSite.style.display = 'inline-flex';
        if (btnRetryPush) btnRetryPush.style.display = 'none';
      } else {
        if (progressBar) {
          progressBar.style.width = '100%';
          progressBar.style.background = 'var(--error)';
        }
        addTerminalLog('ERROR', 'ERROR', `Falha no cadastro: ${data.error || 'Erro desconhecido.'}`);
        
        // Se a falha foi especificamente no git push, exibe botão para tentar enviar novamente
        if (data.error && (data.error.includes('git push') || data.error.includes('push') || data.error.includes('remote rejected'))) {
          if (btnRetryPush) {
            btnRetryPush.style.display = 'inline-flex';
            btnRetryPush.disabled = false;
            btnRetryPush.innerHTML = '<i class="fas fa-arrows-rotate"></i> Tentar Push Novamente';
          }
        }
      }
    } catch (err) {
      if (progressBar) progressBar.style.background = 'var(--error)';
      addTerminalLog('NETWORK', 'ERROR', `Erro de comunicação com o servidor: ${err.message}`);
    } finally {
      if (btnClose) btnClose.style.display = 'inline-flex';
    }
  });

  function addTerminalLog(step, status, message, detail = '') {
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    const time = new Date().toLocaleTimeString('pt-BR');
    entry.innerHTML = `
      <span class="log-time">[${time}]</span>
      <span class="log-step">[${step}]</span>
      <span class="log-msg ${status}">${escapeHtml(message)}</span>
    `;
    if (detail) {
      const detailPre = document.createElement('pre');
      detailPre.style.margin = '4px 0 8px 30px';
      detailPre.style.color = '#8C99A6';
      detailPre.style.fontSize = '11px';
      detailPre.textContent = detail;
      entry.appendChild(detailPre);
    }
    terminal.appendChild(entry);
    terminal.scrollTop = terminal.scrollHeight;
  }

  if (btnClose) {
    btnClose.addEventListener('click', () => {
      modal.classList.remove('active');
    });
  }

  function escapeHtml(text) {
    return (text || '').replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[m]);
  }
}

// =============================================================================
// 10. Ação de Git Pull sob Demanda
// =============================================================================
function initGitPullAction() {
  const btnPull = document.getElementById('btn-git-pull');
  if (!btnPull) return;

  btnPull.addEventListener('click', async () => {
    btnPull.disabled = true;
    const origHtml = btnPull.innerHTML;
    btnPull.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sincronizando...';

    try {
      const res = await fetch('/api/git/pull', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        alert(`Sincronização concluída com sucesso:\n${data.output || 'Repositório atualizado.'}`);
        window.location.reload();
      } else {
        alert(`Erro na sincronização: ${data.error}`);
      }
    } catch (e) {
      alert(`Falha de rede: ${e.message}`);
    } finally {
      btnPull.disabled = false;
      btnPull.innerHTML = origHtml;
    }
  });
}

