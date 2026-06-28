from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_bonus_claim import DailyBonusClaim
from app.models.referral import Referral
from app.models.user import User
from app.models.withdrawal import WithdrawalRequest, WithdrawalStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _date_label(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_insights(db: AsyncSession, user: User) -> dict:
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=6)  # today + 6 prior days = 7 days

    # ── 1. Daily bonus claims ────────────────────────────────────────────────
    bonus_rows = list(
        (await db.execute(
            select(DailyBonusClaim)
            .where(DailyBonusClaim.user_id == user.id)
            .order_by(DailyBonusClaim.claimed_at.desc())
        )).scalars().all()
    )

    # ── 2. Referral rewards paid to this user (as referrer) ─────────────────
    referral_rows = list(
        (await db.execute(
            select(Referral)
            .where(Referral.referrer_id == user.id, Referral.reward_paid == True)  # noqa: E712
            .order_by(Referral.reward_paid_at.desc())
        )).scalars().all()
    )

    # ── 3. Withdrawal requests ───────────────────────────────────────────────
    withdrawal_rows = list(
        (await db.execute(
            select(WithdrawalRequest)
            .where(WithdrawalRequest.user_id == user.id)
            .order_by(WithdrawalRequest.created_at.desc())
        )).scalars().all()
    )

    # ── Build transactions list ──────────────────────────────────────────────
    transactions: list[dict] = []

    for b in bonus_rows:
        ts = _normalize(b.claimed_at)
        transactions.append({
            "id": f"bonus_{b.id}",
            "type": "daily_bonus",
            "label": "Daily Bonus",
            "amount": float(b.amount),
            "direction": "credit",
            "status": "completed",
            "timestamp": ts.isoformat() if ts else None,
        })

    for r in referral_rows:
        ts = _normalize(r.reward_paid_at)
        transactions.append({
            "id": f"referral_{r.id}",
            "type": "referral_reward",
            "label": "Referral Reward",
            "amount": float(r.reward_amount),
            "direction": "credit",
            "status": "completed",
            "timestamp": ts.isoformat() if ts else None,
        })

    _status_label = {
        "pending_payment": "Pending Payment",
        "pending_verification": "Under Review",
        "processing": "Processing",
        "completed": "Completed",
        "rejected": "Rejected",
    }
    for w in withdrawal_rows:
        ts = _normalize(w.created_at)
        transactions.append({
            "id": f"withdrawal_{w.id}",
            "type": "withdrawal",
            "label": "Withdrawal",
            "amount": float(w.amount),
            "direction": "debit",
            "status": _status_label.get(w.status.value, w.status.value),
            "timestamp": ts.isoformat() if ts else None,
        })

    # Sort newest first
    transactions.sort(key=lambda x: x["timestamp"] or "", reverse=True)

    # ── Weekly earnings (last 7 days, credits only) ──────────────────────────
    # Build a day-keyed bucket for the last 7 days
    day_labels = [_date_label(now - timedelta(days=i)) for i in range(6, -1, -1)]
    weekly: dict[str, float] = {d: 0.0 for d in day_labels}

    for b in bonus_rows:
        ts = _normalize(b.claimed_at)
        if ts and ts >= week_ago:
            weekly[_date_label(ts)] = weekly.get(_date_label(ts), 0.0) + float(b.amount)

    for r in referral_rows:
        ts = _normalize(r.reward_paid_at)
        if ts and ts >= week_ago:
            weekly[_date_label(ts)] = weekly.get(_date_label(ts), 0.0) + float(r.reward_amount)

    weekly_chart = [{"date": d, "amount": weekly[d]} for d in day_labels]

    # ── Earning overview (lifetime totals) ───────────────────────────────────
    total_bonus = sum(float(b.amount) for b in bonus_rows)
    total_referral = sum(float(r.reward_amount) for r in referral_rows)
    total_withdrawn_completed = sum(
        float(w.amount) for w in withdrawal_rows if w.status == WithdrawalStatus.completed
    )
    total_withdrawn_pending = sum(
        float(w.amount) for w in withdrawal_rows
        if w.status in (
            WithdrawalStatus.pending_payment,
            WithdrawalStatus.pending_verification,
            WithdrawalStatus.processing,
        )
    )

    overview = {
        "total_earned": round(total_bonus + total_referral, 2),
        "daily_bonus_total": round(total_bonus, 2),
        "referral_reward_total": round(total_referral, 2),
        "total_withdrawn": round(total_withdrawn_completed, 2),
        "pending_withdrawal": round(total_withdrawn_pending, 2),
        "current_balance": float(user.balance),
    }

    return {
        "transactions": transactions[:50],   # cap at 50 for the page
        "weekly_chart": weekly_chart,
        "overview": overview,
    }