# Celine

<div align="center">

[![Release](https://img.shields.io/github/v/release/augusttw/celine?color=brightgreen&label=release)](https://github.com/augusttw/celine/releases)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Avaliações](https://img.shields.io/badge/avalia%C3%A7%C3%B5es-15%2F15%20passando-success.svg)](file:///home/zyltr4x/coding/Celine/src/celine/evaluation.py)

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
- ⚙️ **Engine de Execução de Ferramentas**: Capacidades nativas para manipulação de arquivos, execução de comandos de terminal, análise de diffs/status do Git, consultas web, indexação de memória e ferramentas de companheiro.
- 🧠 **Estado Canônico e Memória**: Sessões e memórias consentidas compartilham `~/.celine/state.db`; a continuidade relacional permanece em um journal específico e auditável.
- ✅ **Approvals One-Shot**: Efeitos sensíveis retornam um token exato. Revise com `/approvals`, autorize com `/approve TOKEN` e use `/retry`; credenciais e arquivos privados nunca são expostos ao modelo.
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
| `/status` | Exibe o provedor, modelo e ID da sessão ativa vigentes |
| `/model` | Atualiza o catálogo e lista todos os modelos disponíveis |
| `/model refresh` | Força a consulta remota de modelos junto ao provedor ativo |
| `/model <id>` | Altera e persiste o modelo ativo (ex: `/model nvidia/nemotron-3.5-lightning-30b-a3b`) |
| `/provider list` | Lista os provedores configurados |
| `/provider <nome>` | Altera o provedor ativo (ex: `/provider nvidia-nim`) |
| `/session list` | Lista as sessões históricas de conversa |
| `/session new` | Inicializa uma nova sessão limpa |
| `/session switch <id>` | Alterna o contexto para uma sessão específica |
| `/memory list` | Exibe as memórias de longo prazo armazenadas |
| `/memory search <termo>` | Realiza busca semântica/textual na base de memória |
| `/memory add <texto>` | Registra explicitamente uma informação na memória persistente |
| `/approvals` | Lista efeitos sensíveis aguardando autorização |
| `/approve <token>` | Autoriza exatamente um efeito pendente; use `/retry` depois |
| `/retry` | Repete a execução do último turno com as configurações vigentes |
| `/clear` | Limpa a tela e redesenha a interface |
| `/help` | Exibe ajuda rápida e atalhos de comandos |
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
celine presence notify ...    # Dispara notificação explícita no sistema operacional
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
│   │   ├── legacy_sessions.py  # Migração idempotente de sessões legadas
│   │   ├── profile.py          # Instalador do profile e diagnóstico doctor
│   │   ├── skill_isolation.py  # Isolamento e sandbox de skills
│   │   ├── core/               # Loop do agente, broker de aprovações, memória e sessões
│   │   │   ├── agent.py        # Loop de turnos do agente e streaming de tokens
│   │   │   ├── approvals.py    # Aprovações one-shot e validação de políticas
│   │   │   ├── context.py      # Ranking de contexto e compactação de mensagens
│   │   │   ├── memory.py       # Armazenamento SQLite semântico/textual de memórias
│   │   │   ├── persona.py      # Construtor da persona e prompts de sistema
│   │   │   └── session.py      # Gerenciamento canônico de sessões no SQLite
│   │   ├── providers/          # Roteador multi-provedor, autenticação e cliente OpenAI
│   │   ├── tools/              # Registro de ferramentas nativas (arquivos, shell, web, memória, companion)
│   │   ├── ui/                 # Interface Rich/prompt-toolkit, banners, estilos e streaming
│   │   ├── voice/              # Módulo opcional de síntese de voz (TTS)
│   │   └── assets/             # Prompts de sistema (SOUL.md), temas e widgets
│   └── celine_companion/       # Presença desktop, diário de relacionamento e contratos pulse
├── tests/                      # Suite de testes automatizados e asserções de runtime
└── ~/.celine/                  # Estado local isolado em disco (state.db, config.yaml, auth.json)
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

