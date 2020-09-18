'''module to control the Lockin amplifier for the QNL probe station in fab.
Also see https://www.thinksrs.com/downloads/pdfs/manuals/SR810m.pdf for GPIB commands
'''

import visa

class SR810_lockin():
    def __init__(self,gpib_addr='GPIB0::8::INSTR'):
        self.gpib_addr = gpib_addr
        self.dev = visa.ResourceManager().open_resource(gpib_addr)
        self.dev.write('OUTX 1') # Use GPIB
        self.dev.write('OVRM 1') # Don't lock out the front panel

    def reconnect(self):
        '''Reinstantiate the device'''
        self.dev = visa.ResourceManager().open_resource(self.gpib_addr)

    def voltage_out(self, voltage=None):
        '''Get/Set the excitation voltage of the lockin
        Args: voltage: voltage in volts. None to query
        Returns: voltage in volts
        '''
        if voltage is not None:
            self.dev.write('SLVL {}'.format(voltage))
        return float(self.dev.query('SLVL?'))

    def voltage_in(self):
        '''Get the probe voltage of the lockin
        Returns: voltage in volts. will return -1 on overload
        '''

        # verify not over voltage
        self.dev.write('*CLS')
        status_byte = int(self.dev.query('LIAS?'))
        over_voltage = (status_byte & 4) >> 2
        if over_voltage:
            return(-1)

        return float(self.dev.query('OUTP? 3'))

    def sensitivity(self,sense=None):
        '''get/set the sensitivity of the lock in
        Args: sense parameter (0 through 26). None to query.
        Returns: sense parameter (0 through 26)
            0   2 nV/fA 
            1   5 nV/fA 
            2   10 nV/fA 
            3   20 nV/fA 
            4   50 nV/fA 
            5   100 nV/fA 
            6   200 nV/fA 
            7   500 nV/fA 
            8   1 µV/pA 
            9   2 µV/pA 
            10  5 µV/pA 
            11  10 µV/pA 
            12  20 µV/pA 
            13  50 µV/pA
            14  100 µV/pA
            15  200 µV/pA
            16  500 µV/pA
            17  1 mV/nA
            18  2 mV/nA
            19  5 mV/nA
            20  10 mV/nA
            21  20 mV/nA
            22  50 mV/nA
            23  100 mV/nA
            24  200 mV/nA
            25  500 mV/nA
            26  1 V/µA 
        '''
        if sense is not None:
            assert sense >= 0 and sense <= 26, 'Sense "{}" is out of range'.format(sense)
            self.dev.write('SENS {}'.format(sense))
        return float(self.dev.query('SENS?'))

    def time_constant(self,tc=None):
        '''get/set the time constant
        Args: tc (0 through 19). None to query.
        Returns: time constant (0 through 19)
                0   10 µs
                1   30 µs
                2   100 µs
                3   300 µs
                4   1 ms
                5   3 ms
                6   10 ms
                7   30 ms
                8   100 ms
                9   300 ms
                10  1 s
                11  3 s
                12  10 s
                13  30 s
                14  100 s
                15  300 s
                16  1 ks
                17  3 ks
                18  10 ks
                19  30 ks 
        '''
        if tc is not None:
            assert tc >= 0 and tc <= 19, 'Sense "{}" is out of range'.format(tc)
            self.dev.write('OFLT {}'.format(tc))
        return float(self.dev.query('OFLT?'))


if __name__ == '__main__':
    inst = SR810_lockin('GPIB0::8::INSTR')
    print(inst.voltage_in())
    print(inst.voltage_out(1))