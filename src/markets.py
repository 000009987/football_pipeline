"""
Liquidación de mercados de apuestas.

Cada función devuelve un SettlementResult con:
  - result: "win" | "loss" | "push" | "half_win" | "half_loss" | "void"
  - pnl: retorno neto con stake=1.0 (0 si push/void, -0.5 si half_loss, +0.5*ev si half_win)
  - stake_returned: cuánto del stake se devuelve (1.0 win/push, 0.5 half, 0 loss)

Mercados:
  - 1X2 (HOME, DRAW, AWAY): sin push, sin media
  - O/U 2.5 (OVER, UNDER): sin push
  - BTTS (YES, NO): sin push
  - AH asiático (línea .0, .25, .5, .75): con push, half-win, half-loss, void

Uso:
  from src.markets import settle_1x2, settle_ou25, settle_btts, settle_ah
  res = settle_1x2(home_goals=2, away_goals=1, pick="HOME")
  # → SettlementResult(result="win", pnl=0.90, stake_returned=1.0)
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SettlementResult:
    result: str          # "win", "loss", "push", "half_win", "half_loss", "void"
    pnl: float           # retorno neto con stake=1.0
    stake_returned: float  # 1.0 win/push, 0.5 half, 0.0 loss


def _win(odds: float, stake: float) -> SettlementResult:
    return SettlementResult(
        result="win",
        pnl=stake * (odds - 1),
        stake_returned=stake,
    )


def _loss(stake: float) -> SettlementResult:
    return SettlementResult(
        result="loss",
        pnl=-stake,
        stake_returned=0.0,
    )


def _push(stake: float) -> SettlementResult:
    return SettlementResult(
        result="push",
        pnl=0.0,
        stake_returned=stake,
    )


def _half_win(odds: float, stake: float) -> SettlementResult:
    # Mitad del stake gana, mitad se devuelve
    return SettlementResult(
        result="half_win",
        pnl=stake * (odds - 1) / 2,
        stake_returned=stake,  # recibe stake completo: mitad devuelta + mitad ganada
    )


def _half_loss(odds: float, stake: float) -> SettlementResult:
    # Mitad del stake pierde, mitad se devuelve
    return SettlementResult(
        result="half_loss",
        pnl=-stake / 2,
        stake_returned=stake / 2,
    )


# ─── 1X2 ──────────────────────────────────────────────────────────────

def settle_1x2(home_goals: int, away_goals: int, pick: str, odds: float, stake: float = 1.0) -> SettlementResult:
    """
    Liquida un pick de 1X2.
    pick ∈ {"HOME", "DRAW", "AWAY"}
    Sin push, sin media: siempre hay ganador o empate.
    """
    pick = pick.upper()
    if pick not in {"HOME", "DRAW", "AWAY"}:
        return SettlementResult(result="void", pnl=0.0, stake_returned=stake)

    if pick == "HOME":
        won = home_goals > away_goals
    elif pick == "DRAW":
        won = home_goals == away_goals
    else:  # AWAY
        won = home_goals < away_goals

    return _win(odds, stake) if won else _loss(stake)


# ─── O/U 2.5 ──────────────────────────────────────────────────────────

def settle_ou25(home_goals: int, away_goals: int, pick: str, odds: float, stake: float = 1.0) -> SettlementResult:
    """
    Liquida un pick de Over/Under 2.5.
    pick ∈ {"OVER", "UNDER"}
    Sin push.
    """
    pick = pick.upper()
    if pick not in {"OVER", "UNDER"}:
        return SettlementResult(result="void", pnl=0.0, stake_returned=stake)

    total = home_goals + away_goals
    if pick == "OVER":
        won = total > 2.5
    else:  # UNDER
        won = total < 2.5

    return _win(odds, stake) if won else _loss(stake)


# ─── BTTS ────────────────────────────────────────────────────────────

def settle_btts(home_goals: int, away_goals: int, pick: str, odds: float, stake: float = 1.0) -> SettlementResult:
    """
    Liquida un pick de Both Teams To Score.
    pick ∈ {"YES", "NO"}
    Sin push.
    """
    pick = pick.upper()
    if pick not in {"YES", "NO"}:
        return SettlementResult(result="void", pnl=0.0, stake_returned=stake)

    both_scored = home_goals > 0 and away_goals > 0
    won = both_scored if pick == "YES" else not both_scored

    return _win(odds, stake) if won else _loss(stake)


# ─── AH asiático ─────────────────────────────────────────────────────

def _settle_ah_half(diff: float, handicap: float) -> str:
    """Liquida UNA mitad de un AH con línea .0 o .5 (sin push posible con .5)."""
    adj = diff + handicap
    if adj > 0:
        return "win"
    if adj < 0:
        return "loss"
    # adj == 0: solo ocurre con handicap .0
    return "push"


def settle_ah(home_goals: int, away_goals: int, handicap: float, pick: str, odds: float, stake: float = 1.0) -> SettlementResult:
    """
    Liquida un pick de Asian Handicap.
    pick ∈ {"HOME", "AWAY"}
    handicap: línea aplicada al HOME (negativo = home da ventaja).

    Líneas soportadas:
      - X.0 (entera): win/push/loss
      - X.5 (media): win/loss (nunca push)
      - X.25: se parte en X.0 + X.5
      - X.75: se parte en X.5 + (X+1).0
    """
    pick = pick.upper()
    if pick not in {"HOME", "AWAY"}:
        return SettlementResult(result="void", pnl=0.0, stake_returned=stake)

    # Diferencia desde la perspectiva del HOME
    diff = home_goals - away_goals

    # Si el pick es AWAY, invertir signo y handicap
    if pick == "AWAY":
        diff = -diff
        handicap = -handicap

    # Detectar línea
    # x.0 → entera, x.5 → media, x.25/x.75 → cuarto
    line_str = f"{handicap:.2f}"
    if line_str.endswith(".00"):
        # Línea entera
        adj = diff + handicap
        if adj > 0:
            return _win(odds, stake)
        if adj < 0:
            return _loss(stake)
        return _push(stake)

    if line_str.endswith(".50"):
        # Línea media
        adj = diff + handicap
        return _win(odds, stake) if adj > 0 else _loss(stake)

    if line_str.endswith(".25") or line_str.endswith(".75"):
        # Línea cuarto: partir en 2 mitades
        if line_str.endswith(".25"):
            h1 = handicap - 0.25   # X.0
            h2 = handicap + 0.25   # X.5
        else:  # .75
            h1 = handicap - 0.25   # X.5
            h2 = handicap + 0.25   # (X+1).0

        r1 = _settle_ah_half(diff, h1)
        r2 = _settle_ah_half(diff, h2)

        # Combinar resultados
        if r1 == "win" and r2 == "win":
            return _win(odds, stake)
        if r1 == "loss" and r2 == "loss":
            return _loss(stake)
        if r1 == "push" and r2 == "push":
            return _push(stake)
        if (r1 == "win" and r2 == "push") or (r1 == "push" and r2 == "win"):
            return _half_win(odds, stake)
        if (r1 == "loss" and r2 == "push") or (r1 == "push" and r2 == "loss"):
            return _half_loss(odds, stake)

    # Línea no soportada
    return SettlementResult(result="void", pnl=0.0, stake_returned=stake)


# Alias por compatibilidad
settle_ah_asiatico = settle_ah