"""Regras temporais das visitas; sem alteração de esquema do banco.

Extraordinário: sem horários no modelo Plantao, somente a data do
plantão é verificável. Não inferir extensão até o dia seguinte.
"""

from datetime import datetime, time, timedelta

from django.db.models import Q


def horario_compativel(plantao, data_visita, horario):
    if not data_visita or horario is None:
        return False

    if plantao.tipo_servico == "ORDINARIO":
        inicio = datetime.combine(
            plantao.data,
            time(7, 0),
        )

        fim = inicio + timedelta(days=1)

        momento = datetime.combine(
            data_visita,
            horario,
        )

        return inicio <= momento < fim

    # Horário extraordinário ainda não está cadastrado no Plantao.
    return data_visita == plantao.data


def filtrar_cartoes_por_momento(
    queryset,
    data_visita,
    horario,
):
    """Pré-filtra no SQL e valida o intervalo real em Python."""

    if not data_visita or horario is None:
        return queryset.none()

    ontem = data_visita - timedelta(days=1)

    candidatos = queryset.filter(
        Q(plantao__data=data_visita)
        | Q(
            plantao__data=ontem,
            plantao__tipo_servico="ORDINARIO",
        )
    ).select_related("plantao")

    ids = [
        cartao.pk
        for cartao in candidatos
        if horario_compativel(
            cartao.plantao,
            data_visita,
            horario,
        )
    ]

    return queryset.filter(pk__in=ids)