from . import Predict
from predictors.TwoLevel import TwoLevel


class GShare(TwoLevel):
    def __init__(
        self,
        history_size_bits: int,
        pht_counter_bits: int = 2,
        initial_bhr_state: int = 0,
        initial_pht_state: int = 0,
        **kwargs
    ):
        # GShare is a global history twolevel predictor with one BHR
        super().__init__(
            num_bhrs=1,
            history_size_bits=history_size_bits,
            num_pht_entries=2 ** history_size_bits,
            pht_counter_bits=pht_counter_bits,
            initial_bhr_state=initial_bhr_state,
            initial_pht_state=initial_pht_state,
            **kwargs
        )

    # Mask used to keep only the configured number of history bits
    def _history_mask(self) -> int:
        return (1 << self.history_size_bits) - 1

    # Maximum value of a saturating PHT counter
    def _counter_max(self) -> int:
        return (1 << self.pht_counter_bits) - 1

    # Counter values in upper half predict taken
    def _taken_threshold(self) -> int:
        return 1 << (self.pht_counter_bits - 1)

    # GShare indexes the PHT with PC XOR global history
    def _pht_index(self, current_pc: int) -> int:
        return (current_pc ^ self.bhr[0]) & self._history_mask()

    # Use the selected saturating counter to predict
    def predict(self, opcode: str, current_pc: int, target_pc: int) -> Predict:
        pht_index = self._pht_index(current_pc)
        pht_state = self.pht[pht_index]
        return Predict.TAKEN if pht_state >= self._taken_threshold() else Predict.NOT_TAKEN

    # Update the same counter that was used for prediction
    def update(self, opcode: str, current_pc: int, target_pc: int, result: Predict):
        pht_index = self._pht_index(current_pc)
        pht_state = self.pht[pht_index]
        if result == Predict.TAKEN:
            self.pht[pht_index] = min(pht_state + 1, self._counter_max())
            outcome_bit = 1
        else:
            self.pht[pht_index] = max(pht_state - 1, 0)
            outcome_bit = 0
        self.bhr[0] = ((self.bhr[0] << 1) | outcome_bit) & self._history_mask() 