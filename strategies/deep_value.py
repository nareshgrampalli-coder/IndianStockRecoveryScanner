def matches(row) -> bool:
    high, price = row.get("52_week_high"), row.get("market_price")
    return (
        high is not None and price is not None and high > 0 and price < high * 0.5
        and row.get("roce", float("nan")) > 12
        and row.get("roe", float("nan")) > 10
        and row.get("debt_equity", float("nan")) < 0.7
        and row.get("sales_growth", float("nan")) > 5
        and row.get("profit_growth", float("nan")) > 5
        and row.get("operating_cash_flow", float("nan")) > 0
        and row.get("pe", float("nan")) < 25
    )
