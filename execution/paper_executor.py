class PaperExecutor:
    def execute(self, signal, market):
        return {"status": "paper", "side": signal.side.value, "size": signal.size}
