"""Binary paired outcomes; missing measurements stay missing, never become failure."""


def delta_loss(nominal, perturbed):
    if nominal is None or perturbed is None:
        return None
    if nominal not in (False, True, 0, 1) or perturbed not in (False, True, 0, 1):
        raise ValueError("Y must be binary or unavailable")
    return int(nominal)-int(perturbed)
