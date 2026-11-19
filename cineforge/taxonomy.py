"""콘셉트 라이브러리(Taxonomy) 조회·검증."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from cineforge.data_loader import load


@dataclass(frozen=True)
class Item:
    axis: str
    group: str
    id: str
    ko: str
    data: dict[str, Any]

    @property
    def label(self) -> str:
        return self.ko


class Taxonomy:
    def __init__(self, raw: dict[str, Any] | None = None) -> None:
        self.raw = raw or load("taxonomy.yaml")
        self.axes: dict[str, dict[str, Any]] = {a["id"]: a for a in self.raw["axes"]}
        self._items: dict[tuple[str, str], Item] = {}
        self._group_items: dict[tuple[str, str], dict[str, Item]] = {}
        for axis in self.raw["axes"]:
            for group in axis["groups"]:
                bucket = self._group_items.setdefault((axis["id"], group["id"]), {})
                for entry in group["items"]:
                    item = Item(axis["id"], group["id"], entry["id"], entry["ko"], entry)
                    self._items.setdefault((axis["id"], entry["id"]), item)
                    bucket[entry["id"]] = item
        self.presets = {p["id"]: p for p in self.raw.get("presets", [])}

    @property
    def version(self) -> str:
        return str(self.raw.get("version"))

    def order(self) -> list[str]:
        return list(self.raw["selection_order"])

    def axis(self, axis_id: str) -> dict[str, Any]:
        if axis_id not in self.axes:
            raise KeyError(f"알 수 없는 축: {axis_id}")
        return self.axes[axis_id]

    def items(self, axis_id: str, group_id: str | None = None) -> list[Item]:
        axis = self.axis(axis_id)
        result: list[Item] = []
        for group in axis["groups"]:
            if group_id and group["id"] != group_id:
                continue
            result.extend(self._group_items[(axis_id, group["id"])].values())
        return result

    def get(self, axis_id: str, item_id: str, group_id: str | None = None) -> Item:
        if group_id:
            found = self._group_items.get((axis_id, group_id), {}).get(item_id)
        else:
            found = self._items.get((axis_id, item_id))
        if found is None:
            raise KeyError(f"{axis_id}{'.' + group_id if group_id else ''}에 '{item_id}' 항목이 없습니다")
        return found

    def has(self, axis_id: str, item_id: str, group_id: str | None = None) -> bool:
        try:
            self.get(axis_id, item_id, group_id)
            return True
        except KeyError:
            return False

    def resolve(self, axis_id: str, token: str, group_id: str | None = None) -> Item:
        """id 또는 한국어 라벨(정확/부분 일치)로 항목을 찾는다."""
        token = token.strip()
        pool = self.items(axis_id, group_id)
        for item in pool:
            if item.id == token or item.ko == token:
                return item
        compact = token.replace(" ", "")
        partial = [i for i in pool if compact and compact in i.ko.replace(" ", "")]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            raise KeyError(f"'{token}'이(가) 여러 항목과 일치합니다: {', '.join(i.ko for i in partial)}")
        raise KeyError(f"{axis_id}에서 '{token}'을(를) 찾지 못했습니다")

    def labels(self, axis_id: str, ids: Iterable[str], group_id: str | None = None) -> list[str]:
        return [self.get(axis_id, i, group_id).ko for i in ids]

    def total_items(self) -> int:
        return sum(len(self.items(a)) for a in self.axes)
