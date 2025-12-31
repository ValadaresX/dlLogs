import ast
import logging
from itertools import zip_longest
from typing import Any

logger = logging.getLogger("convert_logs.parser_combatant_info")

type Player = dict[str, str | int]
type Stats = dict[str, int]
type TalentsPayload = dict[str, list[dict[str, int]] | list[int]]
type EquipmentItem = dict[str, int | list[int] | list[dict[str, int | None]]]
type Aura = dict[str, str | int]
type PvPStats = dict[str, int | None]


class CombatantInfoParser:
    """Parser dedicado para COMBATANT_INFO.

    Recebe (ts, csv_text) e retorna um dict pronto para o maestro,
    com chaves em inglês e termos do jogo preservados como no log.
    """

    def parse(self, ts: float, csv_text: str) -> dict[str, Any]:
        """Entrada: ts (epoch) e csv_text (string completa após timestamp)."""
        cols = [part.strip() for part in self._smart_split(csv_text)]
        if not cols or cols[0] != "COMBATANT_INFO":
            raise ValueError("Evento inesperado; esperado COMBATANT_INFO")
        if len(cols) >= 3:
            logger.debug("Processando COMBATANT_INFO para %s (faction=%s)", cols[1], cols[2])
        return self._parse_payload(cols[1:])

    @staticmethod
    def _literal(token: str, default: Any, label: str) -> Any:
        if not token:
            return default
        try:
            return ast.literal_eval(token)
        except (SyntaxError, ValueError, TypeError, RecursionError) as exc:
            logger.warning("%s malformados: %s (%s)", label, token, exc)
            raise ValueError(f"{label} malformados") from exc

    @staticmethod
    def _smart_split(s: str) -> list[str]:
        """Separa por vírgula ignorando colchetes/parenteses aninhados."""
        out: list[str] = []
        buf: list[str] = []
        square = paren = 0
        for ch in s:
            if ch == "[":
                square += 1
            elif ch == "]":
                square = max(0, square - 1)
            elif ch == "(":
                paren += 1
            elif ch == ")":
                paren = max(0, paren - 1)
            if ch == "," and square == 0 and paren == 0:
                out.append("".join(buf))
                buf.clear()
            else:
                buf.append(ch)
        out.append("".join(buf))
        return out

    def _parse_payload(self, cols: list[str]) -> dict[str, Any]:
        """Quebra a linha em blocos: jogador, atributos, talentos, expansao, equipamentos, auras, pvp."""
        stats, remaining_after_stats = self._parse_stats(cols)
        class_talents, remaining_after_talents = self._parse_talents(remaining_after_stats)
        expansion, remaining_after_expansion = self._parse_expansion(remaining_after_talents)
        equipment, remaining_after_equipment = self._parse_equipment(remaining_after_expansion)
        auras, pvp = self._parse_auras_and_pvp(remaining_after_equipment)
        player = self._parse_player(cols)
        return {
            "player": player,
            "stats": stats,
            "class_talents": class_talents["class_talents"],
            "pvp_talents": class_talents["pvp_talents"],
            "expansion_powers": expansion,
            "equipment": equipment,
            "interesting_auras": auras,
            "pvp_stats": pvp,
        }

    def _parse_player(self, cols: list[str]) -> Player:
        if len(cols) < 2:
            raise ValueError("Linha incompleta: faltam dados de jogador/faction")
        return {"guid": cols[0], "faction": int(cols[1])}

    def _parse_stats(self, cols: list[str]) -> tuple[Stats, list[str]]:
        """Consume stats e devolve (dict_stats, resto)."""
        stats_labels = [
            "strength",
            "agility",
            "stamina",
            "intellect",
            "dodge",
            "parry",
            "block",
            "crit_melee",
            "crit_ranged",
            "crit_spell",
            "speed",
            "lifesteal",
            "haste_melee",
            "haste_ranged",
            "haste_spell",
            "avoidance",
            "mastery",
            "versatility_damage_done",
            "versatility_healing_done",
            "versatility_damage_taken",
            "armor",
        ]
        minimo = 2 + len(stats_labels) + 1
        if len(cols) < minimo:
            raise ValueError("Linha incompleta: faltam estatisticas")
        base = {
            k: int(v)
            for k, v in zip(
                stats_labels, cols[2 : 2 + len(stats_labels)], strict=False
            )
        }
        spec_id = int(cols[2 + len(stats_labels)])
        remaining = cols[3 + len(stats_labels) :]
        return {**base, "spec_id": spec_id}, remaining

    def _parse_talents(self, cols: list[str]) -> tuple[TalentsPayload, list[str]]:
        """Detecta talentos Dragonflight (lista de tuplas) ou legado (Class Talents + PvP Talents).

        Retorna dict com:
          - class_talents: list[dict] (Dragonflight) ou list[int] (legacy)
          - pvp_talents: list[int]
        """
        if len(cols) < 2:
            raise ValueError("Linha incompleta: faltam talentos de classe/PvP")
        raw_talents, raw_pvp = cols[0], cols[1]
        pvp_raw = self._literal(raw_pvp, [], "Talentos PvP")
        pvp_seq = pvp_raw if isinstance(pvp_raw, (list, tuple)) else (pvp_raw,)
        pvp_talents: list[int] = [int(x) for x in pvp_seq]
        class_talents: list[dict[str, int]] | list[int]
        if raw_talents.startswith("["):
            normalized = self._normalize_class_talents_token(raw_talents)
            raw_talents_list = self._literal(normalized, [], "Talentos de classe")
            class_talents = [
                {"talent_id": t[0], "spell_id": t[1], "rank": t[2]}
                for t in raw_talents_list
            ]
        else:
            class_raw = self._literal(raw_talents, [], "Talentos legacy")
            class_talents = [int(x) for x in class_raw]
        result: TalentsPayload = {"class_talents": class_talents, "pvp_talents": pvp_talents}
        return result, cols[2:]

    def _parse_expansion(self, cols: list[str]) -> tuple[dict[str, Any] | None, list[str]]:
        """Artifact traits / Soulbind / Conduits / ausente.

        Se o token inicial parecer lista de itens (tuplas), não consome nada.
        Caso contrário, devolve estrutura bruta em 'data'.
        """
        if not cols:
            return None, cols
        token = cols[0]
        if not token.startswith("["):
            return None, cols
        obj = self._literal(token, [], "Expansao")
        if isinstance(obj, list) and obj and isinstance(obj[0], tuple):
            # Provavelmente lista de itens; não consome.
            return None, cols
        if self._is_shadowlands(obj):
            logger.info("Expansao detectada: Shadowlands")
            return self._parse_shadowlands(obj), cols[1:]
        if self._is_artifact_traits(obj):
            logger.info("Expansao detectada: Artifact traits")
            return self._parse_artifact_traits(obj), cols[1:]
        return {"data": obj}, cols[1:]

    def _parse_equipment(self, cols: list[str]) -> tuple[list[EquipmentItem], list[str]]:
        """Lista de itens (item_id, ilvl, encantamentos, bonus_list, gemas)."""
        if not cols:
            raise ValueError("Linha incompleta: faltam equipamentos")
        raw_items = self._literal(cols[0], [], "Equipamentos")
        if not isinstance(raw_items, (list, tuple)):
            raise ValueError("Equipamentos malformados")

        def _ints(val: Any) -> list[int]:
            if val in ("", None, ()):
                return []
            seq = val if isinstance(val, (list, tuple)) else [val]
            try:
                return [int(x) for x in seq]
            except (ValueError, TypeError):
                return []

        equipment: list[EquipmentItem] = []
        for entry in raw_items:
            if len(entry) < 2:
                logger.warning("Formato inesperado de item em equipamentos: %s", entry)
                raise ValueError("Formato inesperado de item em equipamentos")
            item_id, ilvl, *rest = entry
            enchants, bonus_list, gems_raw = ([*rest, [], [], []])[:3]
            gems_values = _ints(gems_raw)
            gems = [
                {"id": int(g), "item_level": int(glvl) if glvl is not None else None}
                for g, glvl in zip_longest(gems_values[::2], gems_values[1::2])
                if g is not None
            ]
            equipment.append(
                {
                    "item_id": int(item_id),
                    "item_level": int(ilvl),
                    "enchants": _ints(enchants),
                    "bonus_list": _ints(bonus_list),
                    "gems": gems,
                }
            )
        return equipment, cols[1:]

    def _parse_auras_and_pvp(self, cols: list[str]) -> tuple[list[Aura], PvPStats]:
        """Separa auras interessantes e estatísticas PvP finais."""
        if not cols:
            return [], {"Honor Level": None, "Season": None, "Rating": None, "Tier": None}
        if len(cols) < 5:
            raise ValueError("Linha incompleta: faltam estatisticas PvP")
        auras_raw = self._split_bracket_list(cols[0])
        # Formato: [caster, spell_id, caster, spell_id, ...] - grupos de 2
        auras: list[Aura] = [
            {
                "caster_guid": caster,
                "spell_id": self._to_int_or_raw(spell_token),
            }
            for caster, spell_token in zip(
                auras_raw[0::2], auras_raw[1::2], strict=False
            )
        ]
        pvp_vals = [int(v) for v in cols[1:5]]
        pvp: PvPStats = {
            "Honor Level": pvp_vals[0],
            "Season": pvp_vals[1],
            "Rating": pvp_vals[2],
            "Tier": pvp_vals[3],
        }
        return auras, pvp

    def _is_shadowlands(self, obj: Any) -> bool:
        if not isinstance(obj, list) or len(obj) < 5:
            return False
        conditions = [
            isinstance(obj[0], int),
            isinstance(obj[1], int),
            isinstance(obj[2], list),
            isinstance(obj[3], list),
            isinstance(obj[4], list),
        ]
        if not all(conditions):
            return False
        # Anima powers: lista de tuplas de tamanho 3.
        anima = obj[2]
        return all(isinstance(t, tuple) and len(t) == 3 for t in anima) or anima == []

    def _parse_shadowlands(self, obj: list[Any]) -> dict[str, Any]:
        anima_powers = [
            {"spell_id": int(t[0]), "maw_power_id": int(t[1]), "count": int(t[2])}
            for t in obj[2]
        ]
        soulbind_traits = [int(x) for x in obj[3]]
        conduits = [{"id": int(t[0]), "item_level": int(t[1])} for t in obj[4]]
        return {
            "soulbind_id": int(obj[0]),
            "covenant_id": int(obj[1]),
            "anima_powers": anima_powers,
            "soulbind_traits": soulbind_traits,
            "conduits": conduits,
        }

    def _is_artifact_traits(self, obj: Any) -> bool:
        if not isinstance(obj, list):
            return False
        return all(isinstance(x, int) for x in obj) and len(obj) % 2 == 0

    def _parse_artifact_traits(self, obj: list[int]) -> dict[str, Any]:
        return {
            "artifact_traits": [
                {"trait_id": obj[i], "rank": obj[i + 1]} for i in range(0, len(obj), 2)
            ]
        }

    @staticmethod
    def _normalize_class_talents_token(token: str) -> str:
        """Corrige tokens que comeÃ§am com '[,(' removendo a vÃ­rgula inicial fora da lista."""
        cleaned = token.strip()
        if cleaned.startswith("[,"):
            # Caso tÃ­pico: "[,(123,456,...)]" -> "[(123,456,...)]"
            cleaned = "[" + cleaned[2:].lstrip()
        return cleaned

    @staticmethod
    def _to_int_or_raw(val: Any) -> Any:
        try:
            return int(val)
        except (TypeError, ValueError):
            return val

    @staticmethod
    def _split_bracket_list(token: str) -> list[str]:
        inner = token.strip()
        if inner.startswith("[") and inner.endswith("]"):
            inner = inner[1:-1]
        if not inner:
            return []
        return [part.strip() for part in inner.split(",")]
