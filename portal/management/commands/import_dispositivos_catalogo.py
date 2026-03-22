"""
Comandos para importar/atualizar o catálogo de dispositivos.

Este módulo fornece um comando de gerenciamento Django que lê um arquivo
(Text/TSV) contendo pares CODIGO/DESCRICAO, normaliza os códigos e
cria/atualiza entradas em `DispositivoCatalogo`.
"""

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from portal.models import DispositivoCatalogo


def _normalize_codigo(value: str) -> str:
    """Normaliza um código removendo caracteres não alfanuméricos e zeros à esquerda.

    Exemplos:
        "0321" -> "321"
        "RG1048" -> "RG1048"
    """
    texto = re.sub(r"[^0-9A-Za-z]", "", (value or "").strip()).upper()
    if not texto:
        return ""
    if texto.isdigit():
        texto = texto.lstrip("0") or "0"
    return texto


class Command(BaseCommand):
    help = "Importa catalogo de dispositivos a partir de um arquivo TXT/TSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "arquivo",
            help="Caminho para o arquivo com CODIGO e DESCRICAO (separados por tab ou espacos).",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Atualiza descricoes ja existentes no catalogo.",
        )

    def handle(self, *args, **options):
        arquivo = options["arquivo"]
        allow_update = options["update"]
        created = 0
        updated = 0
        updated_items = []
        skipped = 0

        with open(arquivo, "r", encoding="utf-8") as handle:
            linhas = handle.read().splitlines()

        existing = {
            item.codigo: item
            for item in DispositivoCatalogo.objects.all().only("id", "codigo", "descricao")
        }
        seen = set()
        novos = []

        for linha in linhas:
            raw = linha.strip()
            if not raw:
                continue
            if raw.upper().startswith("CODIGO"):
                continue
            if "\t" in raw:
                parts = raw.split("\t", 1)
            else:
                parts = raw.split(None, 1)
            if len(parts) < 2:
                skipped += 1
                continue
            codigo_raw, descricao = parts[0], parts[1].strip()
            if not descricao or not re.search(r"[A-Za-z]", descricao):
                skipped += 1
                continue
            codigo = _normalize_codigo(codigo_raw)
            if not codigo:
                skipped += 1
                continue
            if codigo in seen:
                skipped += 1
                continue
            seen.add(codigo)
            if codigo in existing:
                if allow_update and existing[codigo].descricao != descricao:
                    existing[codigo].descricao = descricao
                    updated_items.append(existing[codigo])
                    updated += 1
                else:
                    skipped += 1
                continue
            novos.append(DispositivoCatalogo(codigo=codigo, descricao=descricao))

        with transaction.atomic():
            if novos:
                DispositivoCatalogo.objects.bulk_create(novos, batch_size=1000)
                created = len(novos)
            if allow_update and updated_items:
                DispositivoCatalogo.objects.bulk_update(
                    updated_items,
                    ["descricao"],
                    batch_size=1000,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Importacao concluida. Criados: {created}, Atualizados: {updated}, Ignorados: {skipped}."
            )
        )
