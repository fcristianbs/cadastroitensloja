# VOXEL LAB · Painel Administrativo de Produtos

Painel administrativo local em Python (Flask + Web GUI moderna) projetado especificamente para gerenciar o catálogo Serverless de impressão 3D da **VOXEL LAB**, com validação automática de regras de negócio de engenharia e sincronização Git / deploy no Vercel.

---

## 🚀 Como Executar

### Opção 1: Inicialização em 1 Clique (Windows)
Basta dar dois cliques no arquivo:
```cmd
iniciar.bat
```
O servidor será iniciado na porta `5050` e seu navegador padrão será aberto automaticamente em `http://127.0.0.1:5050`.

### Opção 2: Via Terminal
```powershell
# Instalação das dependências (se necessário)
py -m pip install -r requirements.txt

# Inicialização da aplicação
py run.py
```

---

## 🛠️ Arquitetura e Fluxo de Automação

O catálogo da **VOXEL LAB** não utiliza bancos de dados relacionais pesados; toda a base de produtos é declarativa e versionada no Git:

1. **Sincronização Prévia:** Executa `git pull origin main` no diretório do repositório para garantir que a branch local esteja atualizada antes de qualquer alteração.
2. **Espelhamento de Imagens:** O upload da foto do produto é automaticamente renomeado para `<slug>.<ext>` e salvo de forma idêntica em:
   - `<REPO_PATH>/static/img/produtos/<slug>.<ext>`
   - `<REPO_PATH>/public/static/img/produtos/<slug>.<ext>` (necessário para o build estático do Vercel)
3. **Atualização do JSON:** Os dados da peça são validados e gravados em `<REPO_PATH>/data/produtos.json` formatados em UTF-8 com indentação de 2 espaços (`ensure_ascii=False`).
4. **Git Staging & Commit:** Executa `git add` dos arquivos específicos e cria o commit com o padrão do projeto:
   ```bash
   git commit -m "feat(catalogo): cadastrar produto <nome> (<slug>)"
   ```
5. **Git Push & Deploy Vercel:** Envia as alterações diretamente para o GitHub (`origin/main`). O Vercel detecta o push e recompila o catálogo estático instantaneamente em produção.

---

## 📋 Regras de Negócio e Validações Obrigatórias

- **RN01 (Slug Único em Kebab-case):** Gerado dinamicamente a partir do nome da peça em minúsculas sem acentos. A aplicação verifica a unicidade em tempo real contra os slugs existentes em `data/produtos.json`.
- **RN02 (Categorias Permitidas):** Restrito estritamente a `engenharia`, `casa`, `gadgets` e `figures`.
- **RN05 (Material vs. Ambiente de Uso):**
  - **Uso Externo:** Para suportar sol, chuva e estrada (como em veículos 4x4 e antenas Starlink), o material **DEVE** ser obrigatoriamente `PETG-UV`, `PETG` ou `ASA`. O uso de `PLA` é expressamente bloqueado pelo backend e pelo frontend.
  - **Uso Interno:** Permite `PLA`, `PETG`, `TPU`, `ABS`, etc.
- **Preço Flexível:** Suporta valor decimal numérico (ex: `129.90`) ou nulo (`null`), exibindo o status comercial *"Sob consulta"* no card de produto.
- **Variações & Sob Medida (RN04):** Permite configurar se uma variação aceita *"Outra medida"*, direcionando o cliente para o fluxo sob medida no WhatsApp.

---

## 🎨 Identidade Visual (Design System Voxel Lab)

O painel administrativo foi concebido respeitando os tokens oficiais da marca:
- **Superfície Principal:** `#0C1014` com malha quadriculada voxel sutil de 24px.
- **Superfície Elevada:** `#151B22` (cards, modais e formulários).
- **Laranja Bico Quente (`--nozzle`):** `#FF6B2C` para ações de destaque e preço.
- **Ciano CAD (`--cad`):** `#33D1E0` para especificações técnicas e badges de sob medida.
- **Tipografia:** Google Fonts *Unbounded* (display), *IBM Plex Sans* (interface) e *IBM Plex Mono* (código e ficha técnica).

---

## ⚙️ Variáveis de Ambiente (`.env`)

Configure o arquivo `.env` na raiz do projeto conforme sua estrutura local:

```ini
# Caminho da pasta do repositório local do catálogo
CATALOG_REPO_PATH=C:/git/VOXEL LAB

# Configurações do Git
GIT_BRANCH=main
GIT_REMOTE=origin
ENABLE_AUTO_PUSH=True

# Configurações do Servidor Local
FLASK_HOST=127.0.0.1
FLASK_PORT=5050
FLASK_DEBUG=True
SECRET_KEY=voxel-lab-admin-dev-secret-key-2026

# URL do Catálogo em Produção (Vercel)
VERCEL_DEPLOY_URL=https://voxel-lab-black.vercel.app
```

---

## 🧪 Testes Automatizados

Para executar os testes unitários de regras de negócio:
```powershell
py -m unittest discover tests
```

