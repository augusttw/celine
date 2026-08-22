# Celine

Celine é uma agente digital independente, brasileira e local-first. O runtime
roda em Python, usa uma TUI nativa e mantém sessões, memória, skills e
credenciais isoladas em `~/.celine`.

O repositório contém código e assets. O estado pessoal e as chaves nunca ficam
no Git.

## Instalação em outro PC

### 1. Pré-requisitos

- Linux, macOS ou Windows com Python 3.11+.
- Git.
- `uv` instalado: https://docs.astral.sh/uv/getting-started/installation/
- Uma chave de API de um provider compatível com OpenAI, ou Ollama local.

### 2. Clonar e instalar

~~~bash
git clone https://github.com/augusttw/celine.git
cd celine
uv tool install --force --editable .
celine install
~~~

O modo `--editable` é intencional: atualizações do código entram no launcher
sem criar uma cópia separada do runtime.

### 3. Configurar o provider

A Celine lê as chaves por variável de ambiente. Nunca coloque uma chave em
`config.yaml`, README ou commit.

NVIDIA NIM:

~~~bash
export NVIDIA_API_KEY="sua-chave-nvidia"
celine
~~~

Dentro da TUI, selecione o provider e o modelo:

~~~text
/provider nvidia-nim
/model nvidia/nemotron-3.5-lightning-30b-a3b
~~~

Para deixar a chave persistente, coloque o `export` no arquivo de inicialização
do seu shell (`~/.bashrc`, `~/.zshrc` ou equivalente), fora do repositório.

Providers suportados por variável:

| Provider | Variável |
| --- | --- |
| NVIDIA NIM | `NVIDIA_API_KEY` ou `NVIDIA_NIM_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Qwen/DashScope | `DASHSCOPE_API_KEY` ou `QWEN_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Ollama | não precisa de chave |

Também é possível salvar a chave em `~/.celine/auth.json`; esse arquivo é
privado, usa modo `0600` e nunca deve ser versionado.

### 4. Verificar e iniciar

~~~bash
celine doctor
celine status
celine
~~~

`doctor` valida assets, permissões, provider ativo e endpoint de modelos.
Se aparecer `ConnectError`, verifique rede/DNS; não significa automaticamente
que a instalação ou a chave estão erradas.

## Comandos da TUI

| Comando | O que faz |
| --- | --- |
| `/model` | Atualiza o catálogo e lista modelos disponíveis |
| `/model refresh` | Força nova consulta ao provider |
| `/model <id>` | Troca e salva o modelo ativo |
| `/provider list` | Lista providers configurados |
| `/provider <nome>` | Troca o provider ativo |
| `/session list` | Lista sessões |
| `/session new` | Abre uma sessão nova |
| `/session switch <id>` | Alterna sessão |
| `/memory list` | Lista memórias salvas |
| `/memory search <termo>` | Busca na memória |
| `/memory add <texto>` | Salva uma memória explicitamente |
| `/retry` | Repete o último turno |
| `/clear` | Limpa e redesenha a TUI |
| `/exit` | Encerra a sessão |

A resposta mostra `pensando…` enquanto o provider ainda não enviou tokens,
diferencia ferramentas em execução e exibe o tempo total do turno.

## Atualizar em uma instalação existente

~~~bash
cd celine
git pull --ff-only
uv tool install --force --editable .
celine doctor
~~~

O checkout é versionado em Git; o profile `~/.celine` permanece separado.
Assim, atualizar o código não apaga sessões, memórias ou credenciais.

## Testar

~~~bash
uv run --project . python -m unittest discover -s tests -v
celine evaluate
celine evaluate --live
~~~

Os testes incluem catálogo de modelos, seleção sem rede, consentimento de
memória e snapshot visual do estado `pensando…`.

## Estrutura

~~~text
src/celine/                 runtime principal
src/celine/ui/              banner, prompt, streaming e tema
src/celine/providers/       autenticação, provider e catálogo de modelos
src/celine/core/            agente, sessões, memória e persona
src/celine/tools/           ferramentas nativas
src/celine/assets/          SOUL, skin e widget padrão
tests/                      testes e snapshots
~/.celine/                  estado local, nunca versionado
~~~

## Segurança

- Não faça commit de `~/.celine/auth.json`, `.env` ou `config.yaml`.
- Não copie credenciais para dentro do checkout.
- Revise `git diff` antes de publicar.
- O `config.yaml` contém preferências; as chaves ficam no `auth.json` ou no
  ambiente.
- Para migrar apenas o runtime, clone este repositório. Para migrar estado
  pessoal, faça backup privado de `~/.celine` com cuidado.

## Licença e contribuição

O projeto está no repositório público `augusttw/celine`. Mudanças devem vir
com teste quando afetarem runtime, segurança ou interface.
