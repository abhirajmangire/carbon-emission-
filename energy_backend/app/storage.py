from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import json
from pathlib import Path

from .schemas import BillCreate, BillRead
from .settings import settings


@dataclass
class _IdCounter:
    next_id: int = 1

    def allocate(self) -> int:
        current = self.next_id
        self.next_id += 1
        return current


class InMemoryStorage:
    def __init__(self) -> None:
        self._id_counter = _IdCounter()
        self._bills: List[BillRead] = []
        self._data_file = Path(settings.data_path)
        self._load()

    # Bills
    def add_bill(self, bill: BillCreate) -> BillRead:
        new_bill = BillRead(
            id=self._id_counter.allocate(),
            year=bill.year,
            month=bill.month,
            kilowatt_hours=bill.kilowatt_hours,
            cost=bill.cost,
            emission_factor_kg_per_kwh=bill.emission_factor_kg_per_kwh,
        )
        self._bills.append(new_bill)
        self._bills.sort(key=lambda b: (b.year, b.month))
        self._save()
        return new_bill

    def list_bills(self) -> List[BillRead]:
        return list(self._bills)

    def find_bill(self, year: int, month: int) -> Optional[BillRead]:
        for b in self._bills:
            if b.year == year and b.month == month:
                return b
        return None

    def latest_bill(self) -> Optional[BillRead]:
        if not self._bills:
            return None
        return self._bills[-1]

    # Persistence
    def _save(self) -> None:
        data = [bill.model_dump() for bill in self._bills]
        try:
            self._data_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            # In demo mode, ignore persistence errors
            pass

    def _load(self) -> None:
        try:
            if self._data_file.exists():
                raw = json.loads(self._data_file.read_text(encoding="utf-8"))
                self._bills = [BillRead(**item) for item in raw]
                if self._bills:
                    self._id_counter.next_id = max(b.id for b in self._bills) + 1
        except Exception:
            # Ignore malformed file
            self._bills = []


storage = InMemoryStorage()

