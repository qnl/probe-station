"""Micromanipulator P200L Probe Station

This is a module for taking automated measurements with the probe station.
"""
import h5py

import datetime as dt
import numpy as np

from pathlib import Path
from time import sleep, time

from probe_station.P200L import P200L
from probe_station.SR810_lockin import SR810_lockin

class Probe_Measurement():
    """Measurement class.
    """

    def __init__(
        self,
        wafer_file=None,
        subsite_file=None,
        data_file='',
        p200_ip='192.168.0.6',
        p200_port=9002,
        reset=False,
        online=True
    ):
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
        self._online = online

        if online:
            self._p200 = P200L(ip=p200_ip,port=p200_port)
            self._lockin = SR810_lockin()

        self.h5 = None

        self.measure_time = 1

        if wafer_file is not None:
            self._p200.load_wafer_file(wafer_file)
        if subsite_file is not None:
            self._p200.load_subsite_file(subsite_file)

        self.datashape = self.get_data_shape()
        self.reset_data_array(reset_wafer_map=reset)

    # def validate_filename(self, data_file, overwrite=False):
    #     """Initializes data_file.

    #     If file exists, will prompt user for input to determine whether a new
    #     file should be chosen.
    #     """

    #     exists_str = (
    #         'The data file %s already exists.\nSpecify a new filename or press '
    #         'enter to write to the same file.\nThis will overwrite previously '
    #         'probed values only if the same site is reprobed.\n'
    #     )
                     
    #     none_str = 'Specify a valid file to save the data to.\n'

    #     path = Path(data_file)
    #     while path.is_dir():
    #         path = Path(input(none_str).split('.')[0])

    #     path = path.parent / f'{path.name}.h5'

    #     try:
    #         path = path.resolve(strict=True)
        
    #         while not overwrite and path.exists():
    #             new = input(exists_str%(path))

    #             overwrite = not bool(new) # Overwrite if empty string
    #             new = new.split('.')[0].strip('/')

    #             if new:
    #                 name = Path(f'{new}.h5')
    #                 path = name if name.is_absolute() else path.parent / name
            
    #     except FileNotFoundError:
    #         pass

    #     print(f"Writing data to {'existing' if overwrite else 'new'} file {path}")

    #     return path

    def get_h5(self, filename):
        path = Path(filename)
        overwrite = False

        message = (
            f'The data file %s already exists. Press Enter to write to the '
            f'same file or enter a new filename.\n'
        )

        while not overwrite:
            try:
                path.resolve(strict=True)
                filename = input(message%(path))
                
                overwrite = filename == ''
                filename = filename.split('.')[0].strip('/')

                if filename:
                    path = Path(f'{filename}.h5')
            except FileNotFoundError:
                break

        if not path.exists():
            self.initialize_h5(filename)

        f = h5py.File(filename, 'a', libver='latest')
        f.swmr_mode = True
        return f

    def initialize_h5(self, filename):
        with h5py.File(filename, 'w', libver='latest') as f:
            f.attrs['wafer_map'] = self._p200.get_wafer_file()
            f.attrs['subsite_map'] = self._p200.get_subsite_file()
            f.create_dataset('voltages', data=self.data)
            f.create_dataset('times', data=self.times)

    def get_data_shape(self):
        wafer_x, wafer_y = self._p200.wafer_array_shape()
        num_subsites = self._p200.subsite_shape()

        return wafer_x, wafer_y, num_subsites

    def restore(self, data_file, reload_maps=False):
        with h5py.File(data_file, 'r', libver='latest') as f:
            wafer_file = f.attrs['wafer_map']
            subsite_file = f.attrs['subsite_map']
            
            self.data = np.array(f['voltages'])
            self.times = np.array(f['times'])

        if reload_maps:
            self._p200.load_wafer_file(wafer_file)
            self._p200.load_subsite_file(subsite_file)

    def reset_data_array(self, reset_wafer_map=True):
        """Reset data.
        
        Resets data and updates the size of the data array to reflect the number
        of dies on the wafer. Optionally resets the tested dies in the wafer
        map.

        Args:
            reset_wafer_map: reset the wafer map so that all sites are untested
        """

        self.data = np.full(self.datashape, -1)
        self.times = np.full(self.datashape, '', dtype=np.str)

        if reset_wafer_map:
            self._p200.reset_wafer()
        
    def probe_die(self, h5file, subsites=True):
        """Probe the current die and update the probe value data array.
        """

        x_i, y_i = self._p200.get_die()
        print(f'Starting die. x:{x_i}, y:{y_i}')
        tic = time()

        index = 1
        self._p200.goto_subsite(index)
        
        while index != -1:
            sleep(self.measure_time)
            self.data[x_i, y_i, index] = self._lockin.voltage_in()
            self.times[x_i, y_i, index] = dt.datetime.now().isoformat()

            h5file['voltages'][x_i, y_i, index] = self.data[x_i, y_i, index]
            h5file['times'][x_i, y_i, index] = self.times[x_i, y_i, index]

            index = self._p200.goto_next_subsite()

        print(f'Die time {round((time() - tic)/60, 2)} minutes')

        # if subsites is True:
        # 	index = 1
        # 	self._p200.goto_subsite(1)
        # 	self.data[x_i][y_i] = []
        #     self.times[x_i][y_i] = []
        # 	while index != -1:
        # 		sleep(self.measure_time)
        # 		self.data[x_i][y_i].append(self._lockin.voltage_in())
        #         self.times[x_i][y_i].append(dt.datetime.now())
        # 		index = self._p200.goto_next_subsite()
        # 	print(f'Die time {round((time()-tic)/60,2)} minutes')
        # else:
        # 	self.data[x_i][y_i] = []
        #     self.times[x_i][y_i] = []
        # 	sleep(self.measure_time)
        # 	self.data[x_i][y_i].append(self._lockin.voltage_in())
        #     self.times[x_i][y_i].append(dt.datetime.now())
        # 	print(f'Die time {round((time()-tic)/60,2)} minutes')

    def probe_wafer(
        self,
        data_file
        reset_die=True,
        use_pattern_recognition=True,
        subsites=True,
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

        self._p200.auto_raise(True)
        self._p200.auto_lower(True)
        self._p200.use_pattern_recognition(use_pattern_recognition)

        h5file = self.get_h5(data_file)

        try:
            if reset_die:
                self.reset_data_array(reset_wafer_map=True)
            else:
                x_index, y_index = self._p200.goto_same_die()

            while x_index < 1e6: # after the last die, x_index goes to a big number
                self.probe_die(h5file)

        except KeyboardInterrupt:
            end_time = dt.datetime.now()
            print(f'KeyboardInterrupt detected at {end_time}')
            self._p200.send_command(f':WFR:BIN {x_index} {y_index} T')
            raise
        except:
            end_time = dt.datetime.now()
            print(f'Error detected at {end_time}')
            raise
        finally:
            h5file.close()

        end_time = dt.datetime.now()
        print(
            f'Wafer completed at {end_time}. Total time: {end_time - start_time}'
        )
        # if checkpoint:
        #     np.savez(
        #         checkpoint,
        #         probe_values=np.array(self.data),
        #         times=np.array(self.times)
        #     )

        # try:
        #     if reset_die:
        #         self.reset_data_array()
        #         x_index, y_index = self._p200.goto_first_die()
        #     else:
        #     	# instead of going to next die, repeat the current die
        #         # x_index, y_index = self._p200.goto_next_die()
        #         x_index, y_index = self._p200.goto_same_die()
        #     while x_index < 1e6: # after the last die, x_index goes to a big number
        #         self.probe_die(subsites=subsites)

        #         if checkpoint:
        #             np.savez(
        #                 checkpoint,
        #                 probe_values=np.array(self.data),
        #                 times=np.array(self.times)
        #             )

        #         x_index, y_index = self._p200.goto_next_die()

        # except KeyboardInterrupt:
        #     end_time = dt.datetime.now()
        #     print(
        #         f'KeyboardInterrupt detected. '
        #         f'Total time: {end_time - start_time}'
        #     )
        #     self._p200.send_command(f':WFR:BIN {x_index} {y_index} T')
        #     raise
        # except:
        #     end_time = dt.datetime.now()
        #     print(f'Error. Total time: {end_time - start_time}')
        #     raise

        # end_time = dt.datetime.now()
        # print(f'Started at {start_time}')
        # print(f'Finished at {end_time}')
        # print(
        #     f'Wafer Done. Total time: {end_time - start_time}'
        # )

    def probe_site(data_file, wafer_x, wafer_y, subsite, auto_lower=False):
        self._p200.auto_raise(True)
        self._p200.auto_lower(auto_lower)

        self._p200.goto_die(wafer_x, wafer_y)
        self._p200.goto_subsite(subsite)

        if not auto_lower:
            if input('Lower the tips? [y/N]\n').lower()[0] == 'y':
                self._p200.lower()
            else:
                return
        
        self.data[x_i, y_i, index] = self._lockin.voltage_in()
        self.times[x_i, y_i, index] = dt.datetime.now().isoformat()
        
        with h5py.File(data_file, 'a') as h5file:
            h5file['voltages'][x_i, y_i, index] = self.data[x_i, y_i, index]
            h5file['times'][x_i, y_i, index] = self.times[x_i, y_i, index]

        return self.data[x_i, y_i, index]