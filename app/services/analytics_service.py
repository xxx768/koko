from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_bonus_claim import DailyBonusClaim
from app.models.referral import Referral
from app.models.user import User, UserRole
from app.models.withdrawal import WithdrawalRequest, WithdrawalStatus


def _normalize(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


async def get_analytics(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    week_ago  = now - timedelta(days=6)
    month_ago = now - timedelta(days=29)

    # ── User stats ────────────────────────────────────────────────────────
    total_users = (await db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.user)
    )).scalar_one()

    active_users = (await db.execute(
        select(func.count()).select_from(User).where(
            User.role == UserRole.user,
            User.is_active == True,       # noqa: E712
            User.is_suspended == False,   # noqa: E712
        )
    )).scalar_one()

    suspended_users = (await db.execute(
        select(func.count()).select_from(User).where(
            User.role == UserRole.user, User.is_suspended == True  # noqa: E712
        )
    )).scalar_one()

    verified_users = (await db.execute(
        select(func.count()).select_from(User).where(
            User.role == UserRole.user, User.is_verified == True  # noqa: E712
        )
    )).scalar_one()

    new_this_week = (await db.execute(
        select(func.count()).select_from(User).where(
            User.role == UserRole.user,
            User.created_at >= week_ago,
        )
    )).scalar_one()

    new_this_month = (await db.execute(
        select(func.count()).select_from(User).where(
            User.role == UserRole.user,
            User.created_at >= month_ago,
        )
    )).scalar_one()

    # ── Withdrawal / revenue stats ────────────────────────────────────────
    all_withdrawals = list((await db.execute(
        select(WithdrawalRequest).order_by(WithdrawalRequest.created_at.desc())
    )).scalars().all())

    total_withdrawal_amount = sum(float(w.amount) for w in all_withdrawals if w.status == WithdrawalStatus.completed)
    total_fees_collected    = sum(float(w.fee_amount) for w in all_withdrawals if w.status in (
        WithdrawalStatus.processing, WithdrawalStatus.completed
    ))
    pending_withdrawal_amount = sum(float(w.amount) for w in all_withdrawals if w.status in (
        WithdrawalStatus.pending_payment, WithdrawalStatus.pending_verification, WithdrawalStatus.processing
    ))

    withdrawal_counts = {
        "pending_payment":      sum(1 for w in all_withdrawals if w.status == WithdrawalStatus.pending_payment),
        "pending_verification": sum(1 for w in all_withdrawals if w.status == WithdrawalStatus.pending_verification),
        "processing":           sum(1 for w in all_withdrawals if w.status == WithdrawalStatus.processing),
        "completed":            sum(1 for w in all_withdrawals if w.status == WithdrawalStatus.completed),
        "rejected":             sum(1 for w in all_withdrawals if w.status == WithdrawalStatus.rejected),
    }

    # ── Bonus stats ───────────────────────────────────────────────────────
    all_bonuses = list((await db.execute(select(DailyBonusClaim))).scalars().all())
    total_bonus_paid = sum(float(b.amount) for b in all_bonuses)
    bonus_this_week  = sum(
        float(b.amount) for b in all_bonuses
        if _normalize(b.claimed_at) and _normalize(b.claimed_at) >= week_ago
    )

    # ── Referral stats ────────────────────────────────────────────────────
    all_referrals = list((await db.execute(select(Referral))).scalars().all())
    total_referral_rewards = sum(float(r.reward_amount) for r in all_referrals if r.reward_paid)
    pending_referrals      = sum(1 for r in all_referrals if not r.reward_paid)
    paid_referrals         = sum(1 for r in all_referrals if r.reward_paid)

    # ── Weekly chart (last 7 days) ────────────────────────────────────────
    day_labels = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    weekly_fees    = {d: 0.0 for d in day_labels}
    weekly_bonus   = {d: 0.0 for d in day_labels}
    weekly_signups = {d: 0   for d in day_labels}

    for w in all_withdrawals:
        if w.status in (WithdrawalStatus.processing, WithdrawalStatus.completed):
            ts = _normalize(w.updated_at)
            if ts and ts >= week_ago:
                key = ts.strftime("%Y-%m-%d")
                if key in weekly_fees:
                    weekly_fees[key] += float(w.fee_amount)

    for b in all_bonuses:
        ts = _normalize(b.claimed_at)
        if ts and ts >= week_ago:
            key = ts.strftime("%Y-%m-%d")
            if key in weekly_bonus:
                weekly_bonus[key] += float(b.amount)

    all_users_list = list((await db.execute(
        select(User).where(User.role == UserRole.user, User.created_at >= week_ago)
    )).scalars().all())
    for u in all_users_list:
        ts = _normalize(u.created_at)
        if ts:
            key = ts.strftime("%Y-%m-%d")
            if key in weekly_signups:
                weekly_signups[key] += 1

    weekly_chart = [
        {
            "date": d,
            "fees": round(weekly_fees[d], 2),
            "bonus_paid": round(weekly_bonus[d], 2),
            "signups": weekly_signups[d],
        }
        for d in day_labels
    ]

    # ── Transaction log (most recent 100) ────────────────────────────────
    transactions = []

    for w in all_withdrawals[:50]:
        ts = _normalize(w.created_at)
        transactions.append({
            "id": f"w_{w.id}",
            "type": "withdrawal",
            "user_id": w.user_id,
            "amount": float(w.amount),
            "fee": float(w.fee_amount),
            "status": w.status.value,
            "timestamp": ts.isoformat() if ts else None,
        })

    for b in sorted(all_bonuses, key=lambda x: x.claimed_at, reverse=True)[:25]:
        ts = _normalize(b.claimed_at)
        transactions.append({
            "id": f"b_{b.id}",
            "type": "daily_bonus",
            "user_id": b.user_id,
            "amount": float(b.amount),
            "fee": 0,
            "status": "completed",
            "timestamp": ts.isoformat() if ts else None,
        })

    for r in sorted(all_referrals, key=lambda x: x.created_at, reverse=True)[:25]:
        ts = _normalize(r.reward_paid_at or r.created_at)
        transactions.append({
            "id": f"r_{r.id}",
            "type": "referral_reward",
            "user_id": r.referrer_id,
            "amount": float(r.reward_amount),
            "fee": 0,
            "status": "paid" if r.reward_paid else "pending",
            "timestamp": ts.isoformat() if ts else None,
        })

    transactions.sort(key=lambda x: x["timestamp"] or "", reverse=True)

    return {
        "platform": {
            "total_users": total_users,
            "active_users": active_users,
            "suspended_users": suspended_users,
            "verified_users": verified_users,
            "new_this_week": new_this_week,
            "new_this_month": new_this_month,
        },
        "revenue": {
            "total_withdrawn": round(total_withdrawal_amount, 2),
            "total_fees_collected": round(total_fees_collected, 2),
            "pending_withdrawal_amount": round(pending_withdrawal_amount, 2),
            "total_bonus_paid": round(total_bonus_paid, 2),
            "bonus_paid_this_week": round(bonus_this_week, 2),
            "total_referral_rewards": round(total_referral_rewards, 2),
            "withdrawal_counts": withdrawal_counts,
            "total_referrals": len(all_referrals),
            "paid_referrals": paid_referrals,
            "pending_referrals": pending_referrals,
        },
        "weekly_chart": weekly_chart,
        "transactions": transactions[:100],
    }