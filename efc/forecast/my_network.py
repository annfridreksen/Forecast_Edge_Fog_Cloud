"""Replace this demonstrator with your network; preserve the forecast contract."""
from .models import NeuralNet

class MyNetwork(NeuralNet):
    """Example adapter: fit(completed_history), predict(causal_state).

    Input keys: queue_before, busy_before, rho_feature, observed_rate_s,
    mobile (0/1), edge_known_ms, fog. Output: finite mean_ms >= 0 and
    p95_ms >= mean_ms. No current target, end_s or future calendar is an input.
    This example inherits the small demonstration MLP; it is not a new model.
    """
