"""Pure warehouse-allocation engine. No DB calls, no side effects: stock snapshots and
warehouse info in, an allocation plan and its explanation out. Objective, in order:
minimize the number of distinct warehouses touched, then minimize weighted shipping cost.
"""

import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class LineToFulfill:
    quotation_line_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    qty: int


@dataclass
class StockSnapshot:
    warehouse_id: uuid.UUID
    product_id: uuid.UUID
    available: int  # on_hand - reserved


@dataclass
class WarehouseInfo:
    id: uuid.UUID
    name: str
    shipping_cost_weight: Decimal


@dataclass
class AllocationPlan:
    quotation_line_id: uuid.UUID
    warehouse_id: uuid.UUID | None
    qty: int
    is_backorder: bool = False
    exhausted_warehouse_stock: bool = False  # this allocation used up everything the warehouse had


@dataclass
class FulfillmentPlan:
    allocations: list[AllocationPlan]
    explanations: list[str]
    total_shipments: int
    estimated_cost: Decimal


def plan_split(
    lines: list[LineToFulfill],
    stock: list[StockSnapshot],
    warehouses: list[WarehouseInfo],
    base_shipment_cost: Decimal,
) -> FulfillmentPlan:
    warehouses_by_id = {w.id: w for w in warehouses}
    # available[warehouse_id][product_id] -> remaining units at that warehouse, mutated as we allocate
    available: dict[uuid.UUID, dict[uuid.UUID, int]] = {w.id: {} for w in warehouses}
    for s in stock:
        if s.warehouse_id in available:
            available[s.warehouse_id][s.product_id] = s.available

    # Only lines with at least one stock snapshot for their product are physically fulfillable
    # from a warehouse; a line with no stock rows at all (a service/subscription) is skipped.
    fulfillable_product_ids = {s.product_id for s in stock}
    remaining: dict[uuid.UUID, int] = {
        ln.quotation_line_id: ln.qty for ln in lines if ln.product_id in fulfillable_product_ids
    }
    line_by_id = {ln.quotation_line_id: ln for ln in lines}

    allocations: list[AllocationPlan] = []
    used_warehouses: set[uuid.UUID] = set()
    candidate_warehouse_ids = set(available.keys())

    while candidate_warehouse_ids and any(qty > 0 for qty in remaining.values()):
        best_id = None
        best_full_coverage = -1
        for wid in candidate_warehouse_ids:
            stock_here = available[wid]
            full_coverage = sum(
                1
                for line_id, qty_needed in remaining.items()
                if qty_needed > 0 and stock_here.get(line_by_id[line_id].product_id, 0) >= qty_needed
            )
            weight = warehouses_by_id[wid].shipping_cost_weight
            if full_coverage > best_full_coverage or (
                full_coverage == best_full_coverage
                and best_id is not None
                and weight < warehouses_by_id[best_id].shipping_cost_weight
            ):
                best_full_coverage = full_coverage
                best_id = wid

        if best_id is None:
            break
        candidate_warehouse_ids.discard(best_id)

        stock_here = available[best_id]
        allocated_any = False
        for line_id, qty_needed in remaining.items():
            if qty_needed <= 0:
                continue
            product_id = line_by_id[line_id].product_id
            have = stock_here.get(product_id, 0)
            if have <= 0:
                continue
            take = min(have, qty_needed)
            allocations.append(
                AllocationPlan(
                    quotation_line_id=line_id,
                    warehouse_id=best_id,
                    qty=take,
                    exhausted_warehouse_stock=(take == have),
                )
            )
            stock_here[product_id] = have - take
            remaining[line_id] = qty_needed - take
            used_warehouses.add(best_id)
            allocated_any = True

        if not allocated_any:
            continue

    for line_id, qty_needed in remaining.items():
        if qty_needed > 0:
            allocations.append(
                AllocationPlan(quotation_line_id=line_id, warehouse_id=None, qty=qty_needed, is_backorder=True)
            )

    explanations: list[str] = []
    for ln in lines:
        line_allocs = [a for a in allocations if a.quotation_line_id == ln.quotation_line_id]
        if not line_allocs:
            continue
        parts = []
        backorder_qty = 0
        for a in line_allocs:
            if a.is_backorder:
                backorder_qty += a.qty
            else:
                wh = warehouses_by_id[a.warehouse_id]
                note = "all available" if a.exhausted_warehouse_stock else "partial"
                parts.append(f"{a.qty} of {ln.qty} from {wh.name} ({note})")
        sentence = ", ".join(parts)
        if backorder_qty:
            sentence = f"{sentence}, {backorder_qty} backordered" if sentence else f"{backorder_qty} of {ln.qty} backordered"
        explanations.append(f"{ln.product_name}: {sentence}.")

    total_shipments = len(used_warehouses)
    estimated_cost = sum(
        (_round(warehouses_by_id[wid].shipping_cost_weight * base_shipment_cost) for wid in used_warehouses),
        Decimal("0"),
    )

    return FulfillmentPlan(
        allocations=allocations,
        explanations=explanations,
        total_shipments=total_shipments,
        estimated_cost=estimated_cost,
    )
