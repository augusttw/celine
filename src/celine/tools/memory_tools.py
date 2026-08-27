from __future__ import annotations

from celine.core.memory import memory_manager
from celine.tools.registry import tool


@tool(
    name="remember",
    description="Salva uma memória somente depois que o usuário deu consentimento explícito nesta conversa.",
)
def remember(fact: str, category: str = "general", consent: bool = False) -> str:
    """Salva um fato durável na memória de longo prazo.

    Args:
        fact: O fato ou preferência a ser lembrado.
        category: Categoria da memória (ex: 'preference', 'project', 'personal', 'general').
        consent: Deve ser true somente quando o usuário autorizou guardar este fato.
    """
    if not fact.strip():
        return "Nenhum conteúdo fornecido para memorizar."
    if not consent:
        return "Sem consentimento explícito: pergunte ao usuário se ele quer que esta informação seja lembrada."

    try:
        success = memory_manager.add_memory(fact.strip(), category=category)
    except ValueError as exc:
        return f"Não foi possível salvar a memória: {exc}"
    if success:
        return f"Memória guardada com carinho: \"{fact.strip()}\""
    return "Não foi possível salvar a memória."


@tool(
    name="forget",
    description="Remove ou esquece uma memória que foi modificada, cancelada ou que o usuário pediu para esquecer.",
)
def forget(query: str) -> str:
    """Remove memórias correspondentes ao termo de busca.

    Args:
        query: Termo ou trecho da memória a ser esquecida.
    """
    if not query.strip():
        return "Consulta vazia para esquecimento."

    count = memory_manager.delete_memory(query.strip())
    if count > 0:
        return f"Esqueci {count} memória(s) contendo '{query}'."
    return f"Nenhuma memória encontrada contendo '{query}'."


@tool(
    name="view_memories",
    description="Exibe as memórias de longo prazo salvas atualmente.",
)
def view_memories(limit: int = 25) -> str:
    """Lista as memórias salvas.

    Args:
        limit: Número máximo de memórias a exibir.
    """
    memories = memory_manager.get_memories(limit=limit)
    if not memories:
        return "Nenhuma memória registrada ainda."

    return "Memórias salvas:\n" + "\n".join(f"- {m}" for m in memories)


@tool(
    name="update_user_profile",
    description="Atualiza o perfil do usuário somente após consentimento explícito.",
)
def update_user_profile(fact: str, consent: bool = False) -> str:
    """Adiciona um fato ao perfil do usuário (USER.md).

    Args:
        fact: Informação a ser adicionada ao perfil do usuário.
        consent: Deve ser true somente quando o usuário autorizou guardar esta informação.
    """
    if not fact.strip():
        return "Informação vazia."

    if not consent:
        return "Sem consentimento explícito: pergunte ao usuário se ele quer que eu guarde essa informação no perfil."
    try:
        memory_manager.append_to_user_profile(fact.strip())
    except ValueError as exc:
        return f"Não foi possível atualizar o perfil: {exc}"
    return f"Perfil do usuário atualizado com: \"{fact.strip()}\""
