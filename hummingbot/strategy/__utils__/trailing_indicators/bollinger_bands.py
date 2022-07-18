from base_trailing_indicator import BaseTrailingIndicator
import pandas as pd
import numpy as np


class BBIndicator(BaseTrailingIndicator):
    def __init__(self, sampling_length: int = 30, processing_length: int = 1):
        if processing_length != 1:
            raise Exception("Exponential moving average processing_length should be 1")
        super().__init__(sampling_length, processing_length)

    def _indicator_calculation(self) -> float:
        np_sampling_buffer = self._sampling_buffer.get_as_numpy_array()
        sma = (np.sum(np_sampling_buffer) / np_sampling_buffer.size)
        std = np.std(np_sampling_buffer)

        upper_bb = sma + (2 * std)
        lower_bb = sma - (2 * std)

        return sma[-1], lower_bb[-1], upper_bb[-1]

    def _processing_calculation(self) -> float:
        return self._processing_buffer.get_last_value()
