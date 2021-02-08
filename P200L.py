"""Module to control the probe station movement.

See NetProbe7 Manual for command information
"""
#added delay in send_command to as an idea to help reduce runtime errors
import socket
import time

class P200L():
    """Class to interface with the probe station. Uses TCP/IP."""
    
    def __init__(self,ip='192.168.0.6',port=9002):
        """Create a probe station interface.

        Args:
            ip: IP address found in the "Router" application.
            port: port found in the "Router" application.
            verbose: print interesting info.
        """

        self.ip = ip
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.ip, self.port))
    
    def reconnect(self):
        """Reconnects to the server. 
        
        Use if the server is restarted or the connection somehow else went bad.
        """
        self.socket.close()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.ip, self.port))
    
    def send_command(self, message):
        """Send a command to the probe station.
        
        Args:
            message: command to send to the probe station as found in the manual.

        Returns: 
            Each response may be interpreted as shown in the probe station manual.
        """
        try:
            self.socket.send(str.encode(message+'\r'))
            time.sleep(0.05)
            data = b''
            response = retval = None
            while response != b'#064':
                while b'\r' not in data:
                    time.sleep(0.05)
                    data += self.socket.recv(1024)
                last_response = response
                response,data = data.split(b'\r',1)
                if response == b'#066':
                    raise Exception(f'Bad Command: "{message}"')
                elif response == b'#079':
                    raise Exception(f'Command Aborted: "{message}"')
    #             elif response == b'#080':
    #                 yield
                elif last_response == b'#192':
                    retval = response.decode('utf-8')
        except:
            try:
                self.reconnect()
            except:
                print('Warning: cannot reconnect to the server')
            raise
        return retval
    
    def goto_die(self, x, y):
        """Move to a certain die location indexed by x and y.
        """
        self.send_command(f':WFR:MOV:CR {x} {y}')
        self.send_command(':PRB:REFXY 0 0')

    def get_die(self):
        """Return the index values of the current die.

        Returns:
            The index values `(x, y)` of the current die.
        """
        x,y = self.send_command(f':WFR:POS:CR?').split(' ')
        return int(x),int(y)

    def reset_wafer(self):
        """Reset all dies to untested in the wafer Map.

        """
        self.send_command(f':WFR:RESET')
    
    def goto_first_die(self):
        """Move to the first die in the probe sequence.
        
        Returns:
            The index `(x,y)` of this die.
        """

        x,y = self.send_command(f':WFR:FIRST?').split(' ')
        self.send_command(':PRB:REFXY 0 0')
        return int(x),int(y)

    def goto_same_die(self):
        """Move to the same die.
        
        Returns: 
            The index `(x,y)` of this die.
        """
        x,y = self.send_command(f':WFR:POS:CR?').split(' ')
        self.send_command(':PRB:REFXY 0 0')
        return int(x),int(y)
    
    def goto_next_die(self):
        """Move to the next die.
        
        Returns:
            The index `(x,y)` of this die
        """
        x,y = self.send_command(f':WFR:NEXT?').split(' ')
        self.send_command(':PRB:REFXY 0 0')
        return int(x),int(y)
    
    def goto_subsite(self, subsite):
        """Move to a subsite of the current die/
        
        Args:
            subsite: Index of the subsite to go to. The current subsite `(x,y)`
                coordinate is visible in P200L Navigator
        """
        self.send_command(f':SUB:GOTO {subsite}')

    def goto_next_subsite(self):
        """Move to the next subsite.
        
        Returns: 
            New subsite index. Returns -1 if there there no more subsites left.
        """
        result = self.send_command(':SUB:NEXT?').split(' ')
        return int(result[0])

    def lower(self):
        self.send_command(f':PRB:DN')

    def raise(self):
        self.send_command(f':PRB:UP')

    def auto_raise(self, do_raise=None):
        """Set/get auto raising.
        
        Args: 
            do_raise (bool): Whether or not to raise the probe tips.
        """
        retval = self.send_command(':PRB:DNM?')
        auto_z_flags = retval.split(' ')
        if do_raise is not None:
            if not do_raise:
                assert not self.auto_lower(), "auto lower should be off before auto_raise is disabled"
            auto_z_flags[0] = {True:'True',False:'False'}[do_raise]
            retval = self.send_command(f':PRB:DNM {" ".join(auto_z_flags)}')
            auto_z_flags = retval.split(' ')
        return {'True':True,'False':False}[auto_z_flags[0]]

    def auto_lower(self, do_lower=None):
        """Set/get auto lowering.
        
        Args: 
            do_lower (bool): Whether or not to lower the probe tips.
        """
        
        retval = self.send_command(':PRB:DNM?')
        auto_z_flags = retval.split(' ')
        if do_lower is not None:
            if do_lower:
                assert self.auto_raise(), "auto raise should be on before auto-lower is enabled"
            auto_z_flags[1] = {True:'True',False:'False'}[do_lower]
            retval = self.send_command(f':PRB:DNM {" ".join(auto_z_flags)}')
            auto_z_flags = retval.split(' ')
        return {'True':True,'False':False}[auto_z_flags[1]]

    def use_pattern_recognition(self, do_rec=None):
        """Get/set using pattern recognition. 
        
        Args:
            do_rec (bool): If `True`, every time the stage moves to a new die, 
                the probe station will use pattern recognition for local
                alignment.
        """
        if do_rec is not None:
            do_rec = {True:"true",False:"false"}[do_rec]
            retval = self.send_command(f':WFR:PATREC {do_rec}')
        return {"True":True, "False":False}[self.send_command(f':WFR:PATREC?')]

    def load_wafer_file(self, wafer_file):
        """Load a wafer map file to the probe station. 
        
        See manual for file data structure

        Args:
            wafer_file: File name to load.
        """
        self.send_command(f':WFR:FILE {subsite_file}')

    def get_wafer_file(self):
        """Gets the current wafer map filename"""

        return self.send_command(f':WFR:FILE?')

    def load_subsite_file(self, subsite_file):
        """Load a subsite file to the probe station. 
        
        See manual for file data structure.
        
        Args:
            wafer_file: File name to load.
        """
        self.send_command(f':SUB:FILE {subsite_file}')

    def get_subsite_file(self):
        """Gets the current subsite filename."""

        return self.send_command(f':SUB:FILE?')

    def wafer_array_shape(self):
        """Return the shape of the wafer array.
        
        Returns:
            A tuple `(col, row)`.
        """

        # Note that the real command ':WFR:MAP:CR?' is broken
        retval = list(map(lambda x:x.split(','),self.send_command(':WFR:MAP:CSV?').split('~')))
        return int(retval[4][1]), int(retval[3][1])

    def subsite_shape(self):
        """Returns the size of the subsite array."""
        raise NotImplementedError
        return int(retval[4][1]), int(retval[3][1])