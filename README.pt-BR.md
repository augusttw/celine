# Celine

<div align="center">

**Runtime de agente digital autônomo e local-first, projetado para execução segura, orquestração multi-provedor de LLMs e persistência de memória com isolamento total.**

**Português** | [English](README.md)

</div>

---

## Visão Geral

O **Celine** é um runtime de agente autônomo local-first desenvolvido em Python. Projetado com foco rigoroso em privacidade, capacidade de execução e ergonomia para desenvolvedores, o Celine opera por meio de uma Interface de Terminal (TUI) nativa ou CLI headless, mantendo todas as sessões, memórias operacionais, skills customizadas e credenciais de API estritamente isoladas em `~/.celine`.

Ao separar de forma estrita o código-fonte do estado de execução, contextos e segredos nunca são rastreados ou expostos no controle de versão (Git).

```
┌─────────────────────────────────────────────────────────────┐
│                       Runtime Celine                        │
├──────────────────────────────┬──────────────────────────────┤
│  Interface de Terminal (TUI) │   CLI Headless & Avaliação   │
│  (prompt-toolkit + Rich)     │  (saúde & contratos de comp.)│
├──────────────────────────────┴──────────────────────────────┤
│                     Núcleo do Agente                        │
│  Gerenciador Contexto · Sessões · Memória Longo Prazo · Soul│
├──────────────────────────────┬──────────────────────────────┤
│   Registro Nativo de Tools   │  Catálogo Multi-Provedores   │
│  Arquivos · Shell · Web · Git│  NVIDIA · OpenAI · Ollama…   │
└──────────────────────────────┴──────────────────────────────┘
```

---

## Principais Funcionalidades

- 🛡️ **Estado Local com Isolamento Total (Zero-Leak)**: Todo o estado de execução, sessões, logs de interação e credenciais residem exclusivamente em `~/.celine/` (ou `$CELINE_HOME`) com permissões estritas de sistema de arquivos (`0600` para autenticação).
- 🖥️ **TUI Nativa e Moderna**: Construída com `prompt-toolkit` e `rich`, oferecendo streaming de tokens em tempo real, painel de raciocínio (*thinking*), métricas de latência e controle intuitivo de comandos.
- 🔌 **Agnóstico a Provedores de LLM**: Alterne facilmente entre NVIDIA NIM, OpenAI, OpenRouter, DeepSeek, Qwen/DashScope, Groq, instâncias locais via Ollama ou qualquer endpoint compatível com a API OpenAI.
- ⚙️ **Engine de Execução de Ferramentas**: Capacidades nativas para manipulação de arquivos, execução de comandos de terminal, análise de diffs/status do Git, consultas web e indexação de memória.
- 🧠 **Arquitetura de Contexto e Memória**: Armazenamento estruturado de memória baseado em consentimento explícito, busca semântica entre sessões, compactação automática de contexto e bloqueio estrito contra vazamento de segredos.
- 🩺 **Diagnóstico e Avaliação Automatizados**: Comandos nativos (`celine doctor`, `celine evaluate`, `celine status`) para verificação contínua da integridade do sistema, assets e contratos comportamentais.

---

## Instalação

### Pré-requisitos

- **Sistema Operacional**: Linux, macOS ou Windows (WSL2 recomendado).
- **Python**: 3.11 ou superior.
- **Git**: Instalado e acessível no `$PATH`.
- **uv**: Gerenciador de pacotes e ambientes Python ([Guia de Instalação](https://docs.astral.sh/uv/getting-started/installation/)).
- **Provedor de LLM**: Chave de API de um provedor compatível ou uma instância local do [Ollama](https://ollama.com/) em execução.

### Passo a Passo

1. **Clonar o repositório**:
   ```bash
   git clone https://github.com/augusttw/celine.git
   cd celine
   ```

2. **Instalar em modo editável com o `uv`**:
   ```bash
   uv tool install --force --editable .
   ```
   > *Nota: O modo editável garante que alterações no código-fonte entrem em vigor no executável imediatamente, sem criar cópias desnecessárias do ambiente.*

3. **Inicializar o profile local**:
   ```bash
   celine install
   ```

---

## Configuração e Autenticação

O Celine carrega chaves de API via variáveis de ambiente ou por meio do armazenamento restrito local. Credenciais nunca devem ser salvas no `config.yaml` ou incluídas em commits.

### Provedores Suportados e Variáveis de Ambiente

| Provedor | Variável de Ambiente |
| :--- | :--- |
| **NVIDIA NIM** | `NVIDIA_API_KEY` ou `NVIDIA_NIM_API_KEY` |
| **OpenAI** | `OPENAI_API_KEY` |
| **OpenRouter** | `OPENROUTER_API_KEY` |
| **Qwen / DashScope** | `DASHSCOPE_API_KEY` ou `QWEN_API_KEY` |
| **DeepSeek** | `DEEPSEEK_API_KEY` |
| **Groq** | `GROQ_API_KEY` |
| **Ollama** | *(Não requer chave para endpoint local)* |

### Definindo Variáveis de Ambiente

Adicione a chave no arquivo de inicialização do seu shell (`~/.bashrc`, `~/.zshrc` ou equivalente):

```bash
export NVIDIA_API_KEY="sua-chave-aqui"
```

Alternativamente, salve as credenciais no arquivo `~/.celine/auth.json` (permissão `chmod 600`):

```json
{
  "nvidia-nim": {
    "api_key": "sua-chave-aqui"
  }
}
```

### Validação do Ambiente

Valide os assets, permissões de arquivos e conectividade com os provedores:

```bash
celine doctor
celine status
```

---

## Utilização

### Iniciando o Agente

```bash
# Iniciar a TUI interativa
celine

# Executar uma consulta única via CLI (modo headless)
celine chat -q "Analise a estrutura do repositório e descreva os módulos principais"
```

### Comandos da TUI Interativa

Durante a sessão interativa no terminal, utilize os comandos com barra (`/`) para gerenciar o runtime:

| Comando | Descrição |
| :--- | :--- |
| `/model` | Atualiza o catálogo e lista todos os modelos disponíveis |
| `/model refresh` | Força a consulta remota de modelos junto ao provedor ativo |
| `/model <id>` | Altera e persiste o modelo ativo (ex: `/model meta/llama-3.1-70b-instruct`) |
| `/provider list` | Lista os provedores configurados |
| `/provider <nome>` | Altera o provedor ativo (ex: `/provider nvidia-nim`) |
| `/session list` | Lista as sessões históricas de conversa |
| `/session new` | Inicializa uma nova sessão |
| `/session switch <id>` | Alterna o contexto para uma sessão específica |
| `/memory list` | Exibe as memórias de longo prazo armazenadas |
| `/memory search <termo>` | Realiza busca semântica/textual na base de memória |
| `/memory add <texto>` | Registra explicitamente uma informação na memória persistente |
| `/retry` | Repete a execução do último turno com as configurações vigentes |
| `/clear` | Limpa a tela e redesenha a interface |
| `/exit` | Encerra a sessão e finaliza o runtime |

---

## Referência de Comandos da CLI

```bash
celine                        # Abre a TUI interativa
celine chat -q "<prompt>"     # Executa consulta headless de turno único
celine install [--opções]     # Inicializa/atualiza o diretório ~/.celine
celine doctor                 # Diagnostica permissões, runtime e endpoints
celine evaluate [--live]      # Executa avaliação de contratos e comportamentos
celine presence status        # Inspeciona estado do daemon de presença desktop
celine presence notify ...    # Dispara notificação no sistema operacional
celine home                   # Imprime o caminho do profile isolado
celine status                 # Exibe JSON com status do provedor, modelo e sessão
```

---

## Estrutura do Projeto

```text
celine/
├── src/
│   ├── celine/
│   │   ├── app.py              # Ponto de entrada da CLI e parsing de argumentos
│   │   ├── config.py           # Esquema de configuração e gestão de profile
│   │   ├── runtime.py          # Loop interativo da TUI e execução headless
│   │   ├── evaluation.py       # Framework de avaliação comportamental
│   │   ├── profile.py          # Instalador do profile e diagnóstico doctor
│   │   ├── skill_isolation.py  # Isolamento e sandbox de skills
│   │   ├── core/               # Loop do agente, ranking de contexto, memória e sessões
│   │   ├── providers/          # Provedores de LLM, autenticação e catálogos
│   │   ├── tools/              # Implementações de ferramentas nativas (arquivos, shell, web, git)
│   │   ├── ui/                 # Renderização Rich/prompt-toolkit, banners e streaming
│   │   └── assets/             # Prompts de sistema, skins e widgets
│   └── celine_companion/       # Hooks de integração e presença desktop
├── tests/                      # Suite de testes automatizados e snapshots
└── ~/.celine/                  # Estado local isolado em disco (nunca versionado)
```

---

## Desenvolvimento e Testes

Execute a suíte de testes unitários e avaliações:

```bash
# Executar testes unitários
uv run --project . python -m unittest discover -s tests -v

# Executar avaliação estática
celine evaluate

# Executar avaliação com chamadas ao provedor ativo
celine evaluate --live
```

---

## Atualizações e Manutenção

Para atualizar o código em uma instalação existente:

```bash
git pull --ff-only
uv tool install --force --editable .
celine doctor
```

Como o checkout do repositório é separado do diretório `~/.celine/`, atualizações no código preservam integralmente suas sessões, memórias registradas e credenciais configuradas.

---

## Política de Segurança

- **Isolamento de Credenciais**: Nunca insira chaves de API em `config.yaml`, arquivos markdown ou commits. Armazene chaves em variáveis de ambiente ou no arquivo `~/.celine/auth.json`.
- **Permissões em Disco**: Certifique-se de que o arquivo `~/.celine/auth.json` possua permissões restritas de leitura (`chmod 600`).
- **Inspeção de Alterações**: Sempre revise a saída de `git status` e `git diff` antes de publicar alterações.
- **Backup**: Para migrar o estado do agente, faça backup do diretório `~/.celine` de forma privada e segura.

---

## Licença e Contribuição

Contribuições são bem-vindas. Certifique-se de que novas funcionalidades incluam testes unitários e sejam validadas via `celine doctor` e `celine evaluate` antes de submeter pull requests.
