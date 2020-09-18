'''Class to take probe measurements for the QNL probe station in fab.
This is a top level class you want to instantiate for taking measurements
'''

from time import sleep, time

from probe_station.P200L import P200L
from probe_station.SR810_lockin import SR810_lockin

class Probe_Measurement():
    '''class to handle probe station measurements
    '''
    def __init__(self,
                 wafer_file=None,
                 subsite_file=None,
                 p200_ip='192.168.0.6',
                 p200_port=9002,
                 reset_wafer_map=True):
        '''Instantiate a measurement. Connects to the probe station and the lockin.
        Data from the meaasurement are stored in self.data

        Args: wafer_file: wafer to load. None to keep current wafer file.
              subsite_file: subsite_file to load. None to keep current subsite_file file.
              p200_ip: ip address found in the "Router" application
              p200_port: port found in the "Router" application
              reset_wafer_map: reset the wafer map so that all sites are untested
        '''
        
        self.p200 = P200L(ip=p200_ip,port=p200_port)
        self.lockin = SR810_lockin()
        self.measure_time = 1
        self.data = None

        if wafer_file is not None:
            self.p200.load_wafer_file(wafer_file)
        if subsite_file is not None:
            self.p200.load_subsite_file(subsite_file)
        self.reset_data_array(reset_wafer_map=reset_wafer_map)
    
    def reset_data_array(self, reset_wafer_map=True):
        '''Reset data and update the size of the data array to reflect
        the number of die on the wafer. Optinally resets the tested dies in the wafer map
        Args:
            reset_wafer_map: reset the wafer map so that all sites are untested
        '''
        (x_count, y_count) = self.p200.wafer_array_shape()
        self.data = [[[] for _ in range(y_count)] for _ in range(x_count)]
        self.p200.reset_die()
        
    def probe_die(self, subsites=True):
        '''Probe the current die and update the probe value data array'''
        x_i, y_i = self.p200.get_die()
        print(f'Starting die. x:{x_i}, y:{y_i}')
        tic = time()

        if subsites is True:
        	index = 1
        	self.p200.goto_subsite(1)
        	self.data[x_i][y_i] = []
        	while index != -1:
        		sleep(self.measure_time)
        		self.data[x_i][y_i].append(self.lockin.voltage_in())
        		index = self.p200.goto_next_subsite()
        	print(f'Die time {round((time()-tic)/60,2)} minutes')
        else:
        	self.data[x_i][y_i] = []
        	sleep(self.measure_time)
        	self.data[x_i][y_i].append(self.lockin.voltage_in())
        	print(f'Die time {round((time()-tic)/60,2)} minutes')

    def probe_wafer(self, reset_die=True, use_pattern_recognition=True, subsites=True):
        '''Probe a full wafer. Assumes that the user has adjusted the probe tips and set
        the down position such that the tips will contact probe points when they land.
        Also assumes that the wafer map and sub file are accurate.
        Args:
            reset_die: True to reset the data array and start from the beginning.
                False to continue from where the wafer was left off.
            use_pattern_recognition: use pattern recognition for local alignment when
                the probe station moves to a new die.
            substies: if only using 1 subsite per die location, set to false and put x=0,y=0 
            	for subsite 1 in P200L navigator. 
        '''
        start_time = time()
        self.p200.auto_raise(True)
        self.p200.auto_lower(True)
        self.p200.use_pattern_recognition(use_pattern_recognition)
        try:
            if reset_die:
                self.reset_data_array()
                x_index, y_index = self.p200.goto_first_die()
            else:
            	# instead of going to next die, repeat the current die
                # x_index, y_index = self.p200.goto_next_die()
                x_index, y_index = self.p200.goto_same_die()
            while x_index < 1e6: # after the last die, x_index goes to a big number
                self.probe_die(subsites=subsites)
                x_index, y_index = self.p200.goto_next_die()
        except KeyboardInterrupt:
            print(f'KeyboardInterrupt detected. Total time: {round((time()-start_time)/60,2)} minutes')
            self.p200.send_command(f':WFR:BIN {x_index} {y_index} T')
            raise
        except:
            print(f'Error. Total time: {round((time()-start_time)/60,2)} minutes')
            raise
        print(time())
        print(start_time)
        print(f'Wafer Done. Total time: {round((time()-start_time)/60,2)} minutes')