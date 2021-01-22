import pytest
from Probe_Measurement import *

import random
import numpy as np


class ProbeOffline(Probe_Measurement):
    """Offline version of Probe_Measurement for Testing purposes"""
    def __init__(self):
        self.adjust = None
        self.z_down = None
        self.measure_time = 1
        self.data = None
        self.times = None
        self.p200 = P200Offline()


class P200Offline:
    def __init__(self):
        self.z_down = 0

    def set_z_down(self, new_z):
        self.z_down = new_z


class TestCalibration:
    def test_calibrate_sanity(self):
        subject = ProbeOffline()
        subject.calibrate(np.array([[0, 0, 0], [0, 1, 1], [1, 0, 0]]))
        assert subject.adjust((0, 1)) == pytest.approx(1)
        assert subject.adjust((2, 0)) == pytest.approx(0)
        assert subject.adjust((0, 2)) == pytest.approx(2)
        assert subject.adjust((0, 10)) == pytest.approx(10)

    def test_calibration_fuzz(self):
        subject = ProbeOffline()
        for _ in range(10):
            test_array = [random.random() for i in range(9)]
            test_array = np.array(test_array).reshape((3, 3))
            subject.calibrate(test_array)
            answer = test_array[0] - test_array[1] + test_array[0]
            assert subject.adjust((answer[0], answer[1])) == pytest.approx(answer[2])

    def test_change_z_down(self):
        subject = ProbeOffline()
        subject.change_z_down(0, 0)
        assert subject.z_down == None
        subject.calibrate(np.array([[0, 0, 0], [0, 1, 1], [1, 0, 0]]))
        subject.change_z_down(0, 0)
        assert subject.z_down == pytest.approx(0)
        subject.change_z_down(0, 1)
        assert subject.z_down == pytest.approx(0)
        subject.change_z_down(10, 0)
        assert subject.z_down == pytest.approx(0)
        subject.change_z_down(0, 10)
        assert subject.z_down == pytest.approx(10)


class classy:
    def init(self):
        self.method = None
    
    def add_one(self):
        self.method = lambda x: x+1


class TestClass:
    def test_one(self):
        assert 1
        
    def test_classy(self):
        clas = classy()
        clas.add_one()
        assert 1 == clas.method(0)


if __name__ == '__main__':
    pytest.main()
