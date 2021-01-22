import pytest
from Probe_Measurement import *


class TestCalibration:
    def test_calibrate(self):
        subject = Probe_Offline()
        subject.calibrate(np.array([[0, 0, 0], [0, 1, 1], [1, 0, 0]]))
        assert subject.adjust((0, 1)) == 1
        assert subject.adjust((2, 0)) == 0
        assert subject.adjust((0, 2)) == 2


class TestClass:
    def test_one(self):
        assert 0


if __name__ == '__main__':
    pytest.main()
