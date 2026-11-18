"""Backfill explícito e transacional; não é importado/chamado pela aplicação.

O chamador fornece uma conexão e controla a transação. Nunca abre banco,
cria tabelas, faz commit, altera o legado ou reativa uma permissão existente.
"""
from sqlalchemy import exists, literal, select


def copy_visitor_permissions(connection):
    from src.database.models import PermissaoAcesso, visitante_locais
    target = PermissaoAcesso.__table__
    missing = ~exists(select(1).where(
        target.c.pessoa_id == visitante_locais.c.visitante_id,
        target.c.local_id == visitante_locais.c.local_id))
    source = select(visitante_locais.c.visitante_id, visitante_locais.c.local_id,
                    literal(None), literal(None), literal(False)).where(missing)
    result = connection.execute(target.insert().from_select(
        ['pessoa_id', 'local_id', 'inicio', 'expiracao', 'revogada'], source))
    return result.rowcount
