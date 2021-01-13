"""Micromanipulator P200L Probe Station

This is a module for taking automated measurements with the probe station.
"""

from time import sleep, time

import datetime as dt
import numpy as np

from probe_station.P200L import P200L
from probe_station.SR810_lockin import SR810_lockin


class Probe_Measurement():
    """Measurement class.
    """

    def __init__(self,
                 wafer_file=None,
                 subsite_file=None,
                 p200_ip='192.168.0.6',
                 p200_port=9002,
                 reset_wafer_map=True):
        """Instantiate a measurement. 
        
        Connects to the probe station and the lockin. Data from the meaasurement
        is stored in `self.data`.

        Args: 
            wafer_file: Wafer to load. `None` to keep current wafer file.
            subsite_file: Subsite file to load. `None` to keep current 
                `subsite_file` file.
            p200_ip: IP address found in the "Router" application
            p200_port: Port found in the "Router" application
            reset_wafer_map: Reset the wafer map so that all sites are
                untested.
        """

        self.p200 = P200L(ip=p200_ip, port=p200_port)
        self.lockin = SR810_lockin()
        self.measure_time = 1
        self.data = None
        self.times = None

        if wafer_file is not None:
            self.p200.load_wafer_file(wafer_file)
        if subsite_file is not None:
            self.p200.load_subsite_file(subsite_file)
        self.reset_data_array(reset_wafer_map=reset_wafer_map)

        self.adjust = None

    def reset_data_array(self, reset_wafer_map=True):
        """Reset data.
        
        Resets data and updates the size of the data array to reflect the number
        of dies on the wafer. Optionally resets the tested dies in the wafer
        map.

        Args:
            reset_wafer_map: reset the wafer map so that all sites are untested
        """
        (x_count, y_count) = self.p200.wafer_array_shape()
        self.data = [[[] for _ in range(y_count)] for _ in range(x_count)]
        self.times = [[[] for _ in range(y_count)] for _ in range(x_count)]
        self.p200.reset_die()

    def probe_die(self, subsites=True):
        """Probe the current die and update the probe value data array.
        """

        x_i, y_i = self.p200.get_die()
        print(f'Starting die. x:{x_i}, y:{y_i}')
        tic = time()

        if subsites is True:
            index = 1
            self.p200.goto_subsite(1)
            self.data[x_i][y_i] = []
            self.times[x_i][y_i] = []
            while index != -1:
                sleep(self.measure_time)
                self.data[x_i][y_i].append(self.lockin.voltage_in())
                self.times[x_i][y_i].append(dt.datetime.now())
                index = self.p200.goto_next_subsite()
            print(f'Die time {round((time() - tic) / 60, 2)} minutes')
        else:
            self.data[x_i][y_i] = []
            self.times[x_i][y_i] = []
            sleep(self.measure_time)
            self.data[x_i][y_i].append(self.lockin.voltage_in())
            self.times[x_i][y_i].append(dt.datetime.now())
            print(f'Die time {round((time() - tic) / 60, 2)} minutes')

    def probe_wafer(
            self,
            reset_die=True,
            use_pattern_recognition=True,
            subsites=True,
            checkpoint=None
    ):
        """Probe a full wafer. 
        
        Assumes that the user has adjusted the probe tips and set the down 
        position properly such that the tips will contact probe points when they
        land. Also assumes that the wafer map and sub file are accurate.

        Args:
            reset_die: `True` to reset the data array and start from the 
                beginning. `False` to continue from where the wafer was left off.
            use_pattern_recognition: Use pattern recognition for local alignment
                when the probe station moves to a new die.
            subsites: If only using 1 subsite per die location, set to false and
                put `x=0,y=0` for subsite 1 in P200L navigator. 
        """
        start_time = dt.datetime.now()

        self.p200.auto_raise(True)
        self.p200.auto_lower(True)
        self.p200.use_pattern_recognition(use_pattern_recognition)

        if checkpoint:
            np.savez(
                checkpoint,
                probe_values=np.array(self.data),
                times=np.array(self.times)
            )

        try:
            if reset_die:
                self.reset_data_array()
                x_index, y_index = self.p200.goto_first_die()
            else:
                # instead of going to next die, repeat the current die
                # x_index, y_index = self.p200.goto_next_die()
                x_index, y_index = self.p200.goto_same_die()
            while x_index < 1e6:  # after the last die, x_index goes to a big number
                self.probe_die(subsites=subsites)

                if checkpoint:
                    np.savez(
                        checkpoint,
                        probe_values=np.array(self.data),
                        times=np.array(self.times)
                    )

                x_index, y_index = self.p200.goto_next_die()

        except KeyboardInterrupt:
            end_time = dt.datetime.now()
            print(
                f'KeyboardInterrupt detected. '
                f'Total time: {end_time - start_time}'
            )
            self.p200.send_command(f':WFR:BIN {x_index} {y_index} T')
            raise
        except:
            end_time = dt.datetime.now()
            print(f'Error. Total time: {end_time - start_time}')
            raise

        end_time = dt.datetime.now()
        print(f'Started at {start_time}')
        print(f'Finished at {end_time}')
        print(
            f'Wafer Done. Total time: {end_time - start_time}'
        )

    def calibrate(self, data):
        """feed the class with calibration data

        Assumes that initial calibration has been done already on at least 3 points. Compute
        a plane equation for this in order to adjust the height of Z lowering in order to
        reduce scratch on the wafer's surface. The plane equation would be saved to the field self.adjust
        To not use this feature, simply do not call
        this function before probe_wafer. To remove this functionality after being calibrated,
        set the field self.adjust to None. To recalibrate, call this function with new data.

        Args:
            data: A 2D numpy array with 3 columns and at least 3 rows. The columns are
                x_coordinate, y_coordinate, z_coordinate given in absolute distances
                with units corresponding to the subsite map and the wafer marker coordinates.
                Each row is a calibration point on
                the wafer. Should look something like this:
                array([[x1, y1, z1],
                       [x2, y2, z2],
                       [x3, y3, z3]])
        """
        compute = np.linalg.lstsq(np.hstack(data[::, 0:2], np.ones(data.shape[0])), data[::, 2])
        self.adjust = lambda coords: np.dot(compute, np.array([coords[0],coords[1], 1]))
