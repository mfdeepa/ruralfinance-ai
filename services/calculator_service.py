def calculate_emi(principal: float, annual_rate: float, months: int) -> dict:
    """Standard reducing-balance EMI calculation."""
    r = annual_rate / (12 * 100)
    if r == 0:
        emi = principal / months
    else:
        emi = principal * r * (1 + r) ** months / ((1 + r) ** months - 1)

    total = emi * months
    interest = total - principal

    return {
        "emi": round(emi, 2),
        "total_payment": round(total, 2),
        "total_interest": round(interest, 2),
        "principal": principal,
        "interest_pct": round((interest / total) * 100, 1) if total > 0 else 0,
    }


def amortization_schedule(principal: float, annual_rate: float, months: int) -> list:
    r = annual_rate / (12 * 100)
    emi = calculate_emi(principal, annual_rate, months)["emi"]
    schedule = []
    balance = principal

    for m in range(1, months + 1):
        int_comp = balance * r if r > 0 else 0
        prin_comp = emi - int_comp
        balance = max(0.0, balance - prin_comp)
        schedule.append({
            "Month": m,
            "EMI (₹)": round(emi, 2),
            "Principal (₹)": round(prin_comp, 2),
            "Interest (₹)": round(int_comp, 2),
            "Balance (₹)": round(balance, 2),
        })

    return schedule


def simple_interest(principal: float, rate: float, years: float) -> dict:
    interest = principal * rate * years / 100
    return {
        "principal": principal,
        "interest": round(interest, 2),
        "total": round(principal + interest, 2),
        "rate": rate,
        "years": years,
    }


def compound_interest(principal: float, rate: float, years: float, frequency: int = 12) -> dict:
    amount = principal * (1 + rate / (frequency * 100)) ** (frequency * years)
    interest = amount - principal
    return {
        "principal": principal,
        "interest": round(interest, 2),
        "total": round(amount, 2),
        "rate": rate,
        "years": years,
        "frequency": frequency,
    }


def savings_growth(monthly: float, rate: float, years: int) -> dict:
    r = rate / (12 * 100)
    n = years * 12
    if r == 0:
        fv = monthly * n
    else:
        fv = monthly * ((1 + r) ** n - 1) / r * (1 + r)

    invested = monthly * n
    return {
        "future_value": round(fv, 2),
        "total_invested": round(invested, 2),
        "total_interest": round(fv - invested, 2),
        "monthly_savings": monthly,
        "rate": rate,
        "years": years,
    }
