# Manual: Usando Copilot SDK com OpenHarness

## 📋 Pré-requisitos

1. **Copilot CLI instalado e autenticado**
   ```bash
   # Verificar se está instalado
   which copilot
   
   # Se não estiver, instale via GitHub CLI
   gh copilot --version
   ```

2. **Python 3.11+** (já tem no projeto)

## 🔧 Instalação

```bash
# Na pasta do projeto, instale o extra copilot
uv sync --extra copilot

# Ou com pip diretamente
pip install github-copilot-sdk>=0.2.0
```

## ⚙️ Configuração

### Opção 1: Usar padrões (Recomendado - Sem configuração)

Se você tem Copilot CLI instalado e autenticado, é isso que precisa:

```bash
# Usar Copilot SDK (ao invés de Anthropic)
uv run oh --provider copilot-sdk -p "sua prompt aqui"

# Especificar modelo (opcional, faz fallback automático se não existir)
uv run oh --provider copilot-sdk --model gpt-5 -p "sua prompt aqui"
```

### Opção 2: Configuração via Variáveis de Ambiente

Se você quer customizar a conexão ao Copilot CLI:

```bash
# Usar Copilot como provider padrão
export OPENHARNESS_PROVIDER=copilot-sdk

# (Opcional) Configurar token GitHub explicitamente
export GITHUB_TOKEN=ghp_seu_token_aqui

# (Opcional) Configurar caminho customizado do Copilot CLI
export COPILOT_CLI_PATH=/caminho/customizado/copilot

# (Opcional) Configurar URL customizada
export COPILOT_CLI_URL=https://seu-copilot-cli:port

# Agora use normalmente
uv run oh -p "sua prompt aqui"
```

### Opção 3: Configuração via `settings.json`

Edite `~/.openharness/settings.json`:

```json
{
  "provider": "copilot-sdk",
  "copilot_cli_path": "/caminho/para/copilot",
  "copilot_cli_url": "http://localhost:3000",
  "copilot_github_token": "ghp_seu_token"
}
```

## 📝 Exemplos de Uso

### Básico: Chat simples
```bash
uv run oh --provider copilot-sdk -p "Olá, como você chama você?"
```

### Com modelo específico
```bash
uv run oh --provider copilot-sdk --model gpt-5 -p "Explique machine learning em 3 linhas"
```

### Com modo interativo (REPL)
```bash
# Sem prompt específico abre o REPL interativo
uv run oh --provider copilot-sdk
# Digite seus prompts normalmente
```

### Com React TUI (Interface Visual)
```bash
# Abre a interface visual com Copilot
uv run oh --provider copilot-sdk --model gpt-5
```

### Ver uso/custo
```bash
# Durante uma sessão, use esses comandos:
/usage     # Ver tokens usados
/cost      # Ver custo estimado
```

## 🔍 Ver Quais Modelos Estão Disponíveis

```bash
# Dentro do OpenHarness (durante sessão):
/models     # Mostra modelos disponíveis para o provider atual
/model show # Mostra o modelo atualmente selecionado
/model set <model>  # Muda o modelo
```

Se usar Copilot SDK, `/models` mostra modelos disponíveis do Copilot CLI.
Se usar Anthropic, mostra modelos Claude disponíveis.

## ✅ Verificar Authentificação

```bash
# Verificar se Copilot CLI está autenticado
gh auth status

# Se não estiver, faça login
gh auth login
```

## 🐛 Troubleshooting

### Erro: "Copilot SDK não encontrado"
```bash
# Instale o SDK
uv sync --extra copilot
# Ou
pip install github-copilot-sdk
```

### Erro: "Modelo não disponível"
```bash
# OpenHarness faz fallback automático com warning
# Você verá algo como:
# "WARNING: model 'gpt-5' is not available; using 'claude-sonnet-4.6'"

# Para evitar, use um modelo que sabe que existe
# ou deixe o sistema escolher (sem --model)
uv run oh --provider copilot-sdk -p "sua prompt"
```

### Copilot CLI não encontrado
```bash
# Verifique se está instalado
which copilot

# Se não, instale via GitHub CLI
brew install gh  # macOS
# ou
sudo apt-get install gh  # Linux

# Depois autentique
gh auth login
```

### Permissão negada ao usar Copilot
```bash
# Verifique token GitHub
gh auth status

# Se necessário, faça login novamente
gh auth logout
gh auth login
```

## 📊 Comparação: Anthropic vs Copilot

| Aspecto      | Anthropic (padrão)             | Copilot SDK                |
| ------------ | ------------------------------ | -------------------------- |
| Flag         | `--provider anthropic`         | `--provider copilot-sdk`   |
| Requer       | API Key Anthropic              | Copilot CLI + GitHub OAuth |
| Autenticação | Automática (ANTHROPIC_API_KEY) | Via GitHub (gh auth)       |
| Modelos      | Claude 3.x, 4.x                | GPT-4, GPT-5 (via Copilot) |
| Fallback     | Não                            | Sim (automático)           |

## 💡 Dicas Úteis

1. **Deixe Anthropic como padrão** - Se não especificar `--provider`, usa Anthropic
2. **Teste fallback** - O sistema avisa se o modelo não existe, mas continua funcionando
3. **Variáveis de ambiente** - Use `OPENHARNESS_PROVIDER=copilot-sdk` para sempre usar Copilot
4. **Logs** - Use `-d` (debug) para ver mais detalhes: `uv run oh -d --provider copilot-sdk -p "test"`

## 🚀 Quick Start

Tudo está pronto! Apenas escolha um dos modos abaixo e comece:

```bash
# Mais rápido possível:
uv run oh --provider copilot-sdk -p "Olá"

# Interativo:
uv run oh --provider copilot-sdk

# Visual:
uv run oh --provider copilot-sdk --model gpt-5
```

---

**Última atualização:** 2 de abril de 2026
**Versão:** 1.0
