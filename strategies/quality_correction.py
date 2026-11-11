def matches(row) -> bool:
    return (
        row.get("market_cap", float("nan")) > 1000
        and row.get("roce", float("nan")) > 15
        and row.get("roe", float("nan")) > 15
        and row.get("debt_equity", float("nan")) < 0.5
        and row.get("sales_growth", float("nan")) > 10
        and row.get("profit_growth", float("nan")) > 10
        and row.get("operating_cash_flow", float("nan")) > 0
        and row.get("pe", float("nan")) < 35
    )
