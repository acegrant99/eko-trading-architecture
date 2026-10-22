from dataclasses import dataclass

@dataclass
class RiskConfig:
    max_position_pct: float = 0.05
    kill_switch: bool = False
    max_daily_loss_pct: float = 0.02

class RiskManager:
    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()

    def check(self, signal, market):
        if self.config.kill_switch:
            return False, "kill switch"
        return True, "ok"
