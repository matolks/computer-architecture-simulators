from . import AbstractBasePredictor, Predict


class Custom(AbstractBasePredictor):
    def __init__(
        self,
        history_size_bits: int = 24,
        num_perceptrons: int = 256,
        weight_bits: int = 8,
        initial_weight: int = 0,
        initial_history_bit: int = 0,
        training_threshold: int = None,
        **kwargs
    ):
        super().__init__()

        assert history_size_bits > 0, "history_size_bits must be positive"
        assert num_perceptrons > 0, "num_perceptrons must be positive"
        assert weight_bits > 1, "weight_bits must be greater than 1"

        self.history_size_bits = history_size_bits
        self.num_perceptrons = num_perceptrons
        self.weight_bits = weight_bits
        self.initial_weight = initial_weight
        self.initial_history_bit = 1 if initial_history_bit else 0
        self.weight_min = -(1 << (weight_bits - 1))
        self.weight_max = (1 << (weight_bits - 1)) - 1

        assert self.weight_min <= initial_weight <= self.weight_max, (
            f"initial_weight must be in range [{self.weight_min}, {self.weight_max}]"
        )
        # Standard perceptron training threshold heuristic
        self.training_threshold = (
            training_threshold
            if training_threshold is not None
            else int(1.93 * history_size_bits + 14)
        )

        self.reset()

    # Map the branch PC to one perceptron entry
    def _pc_index(self, current_pc: int) -> int:
        return current_pc % self.num_perceptrons

    # +1 for taken and -1 for not taken
    def _outcome_to_sign(self, result: Predict) -> int:
        return 1 if result == Predict.TAKEN else -1

    # Convert stored history bits into perceptron input values
    def _history_bit_to_sign(self, bit: int) -> int:
        return 1 if bit else -1

    # Prevent weights from overflowing
    def _clamp_weight(self, value: int) -> int:
        return max(self.weight_min, min(self.weight_max, value))

    # Dot product:
    # bias weight + sum(history_bit_sign * corresponding_weight)
    def _activation(self, current_pc: int) -> int:
        weights = self.perceptrons[self._pc_index(current_pc)]
        total = weights[0]
        for i in range(self.history_size_bits):
            total += weights[i + 1] * self._history_bit_to_sign(self.history[i])
        return total

    # Nonnegative activation predicts taken; negative activation predicts not taken
    def predict(self, opcode: str, current_pc: int, target_pc: int) -> Predict:
        return Predict.TAKEN if self._activation(current_pc) >= 0 else Predict.NOT_TAKEN

    def update(self, opcode: str, current_pc: int, target_pc: int, result: Predict):
        idx = self._pc_index(current_pc)
        weights = self.perceptrons[idx]
        y = self._activation(current_pc)
        prediction = Predict.TAKEN if y >= 0 else Predict.NOT_TAKEN
        target = self._outcome_to_sign(result)
        # Train on wrong predictions or low confidence correct predictions
        should_train = (prediction != result) or (abs(y) <= self.training_threshold)
        if should_train:
            # Bias update
            weights[0] = self._clamp_weight(weights[0] + target)
            # History correlated weight updates
            for i in range(self.history_size_bits):
                history_sign = self._history_bit_to_sign(self.history[i])
                weights[i + 1] = self._clamp_weight(weights[i + 1] + (target * history_sign))
        self.history = [1 if result == Predict.TAKEN else 0] + self.history[:-1]

    def reset(self):
        self.history = [self.initial_history_bit] * self.history_size_bits
        self.perceptrons = [
            [self.initial_weight] * (self.history_size_bits + 1)
            for _ in range(self.num_perceptrons)
        ]
