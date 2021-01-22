"""Micromanipulator P200L Probe Station

This is a module for taking automated measurements with the probe station.
"""

from time import sleep, time

import datetime as dt
import numpy as np

from P200L import P200L
from SR810_lockin import SR810_lockin


class Probe_Measurement():
    """Measurement class.
    """
    DELTA = 5

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
        self.z_down = None

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
        x_coord, y_coord = self.p200.get_xy_coords()  # coordinate of die location
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
                if self.adjust:
                    x_sub, y_sub = self.p200.get_subsite_offsets()
                    self.change_z_down(x_sub + x_coord, y_sub + y_coord)
            print(f'Die time {round((time() - tic) / 60, 2)} minutes')
        else:
            self.data[x_i][y_i] = []
            self.times[x_i][y_i] = []
            self.change_z_down(x_coord, y_coord)
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
            checkpoint: 'None' if there are no data savings.
                Else name of the file to save data
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

        Assumes that initial calibration data has been acquired on at least 3 points. Compute
        a plane equation for this in order to adjust the height of Z lowering to
        reduce scratch on the wafer's surface. The plane equation would be saved to the field self.adjust
        To not use this feature, simply do not call
        this function. To remove this functionality after being calibrated,
        set the field self.adjust to None. To recalibrate, call this function with new data.

        Args:
            data: A 2D numpy array with 3 columns and at least 3 rows. The columns are
                x distance (mm), y distance (mm), z_axis down distance (microns) given in 
                absolute distances with respect to the home position
                with units corresponding to the subsite map and the wafer marker coordinates.
                Each row is a calibration point on the wafer. Should look something like this:
                array([[x1, y1, z1],
                       [x2, y2, z2],
                       [x3, y3, z3]])

        Note: The procedure to find x and y coordinates and the z down distance
              can likely be found on section 3.1.5 and 3.2 of the
              NetProbe 7 Manual. Note that finding the z down distance requires
              repeating the instructions in 3.1.5 on three different points of the wafer
        """
        compute = np.linalg.lstsq(np.hstack(data[::, 0:2], np.ones(data.shape[0])), data[::, 2])
        self.adjust = lambda coords: np.vdot(compute, np.array([coords[0],coords[1], 1]))

    def change_z_down(self, x, y):
        """Checks if down distance needs to be modified. If so, modify it.

        Given the next probe location, this function computes the proper
        z_down distance suggested by the calibration function. If the actual
        distance and the proper distance differs, this function will update the
        z_down attribute to the proper distance.

        Args:
            x: the absolute x distance (mm)
            y: the absolute y distance (mm)
        """
        if self.adjust is None:
            return
        z_proper = self.adjust((x, y))
        if self.z_down is not None and (self.z_down - z_proper) < self.DELTA:
            return
        self.z_down = z_proper
        self.p200.set_z_down(z_proper)

class Probe_Offline(Probe_Measurement):
    """Offline version of Probe_Measurement for Testing purposes"""
    def __init__(self):
        self.adjust = None
        self.z_down = None
        self.measure_time = 1
        self.data = None
        self.times = None
