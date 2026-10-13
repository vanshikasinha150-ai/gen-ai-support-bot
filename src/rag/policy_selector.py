from datetime import date

def select_policy(candidates, as_of=None):
    """as_of=None -> current question; date -> historical question."""
    ref = as_of or date.today()
    active = [d for d in candidates
              if d.effective_date <= ref
              and (d.expiry_date is None or d.expiry_date > ref)]
    if not active:
        return None  # refuse / ask clarification
    return max(active, key=lambda d: (d.effective_date, d.version))