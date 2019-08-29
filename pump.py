# -*- coding: utf-8 -*-
"""
Created on Wed Aug 21 12:44:09 2019

@author: Raman
"""

import serial

class Pump_Serial(object):
    
    '''
    Communicate and control Cole-Parmer Pumps via RS-232
    
    This object can communicate with and control up to 25 Cole-Parmer pumps
    that have been daisy chained together. These connections are initalized
    upon construction, so have pumps hooked up before creating this object. Pumps
    are numbered 1-25, with pumps closest to the computer being lowest.
    
    Provides functions for assigning the speed of a pump, assigning revolutions,
    polling information a pump, and dispensing a volume (if given a tubing size/revolutions
    to volume conversion dictionary)
    
    
    Parameters
    ----------
        serialID : string
            The ID of the serial port. On a windows machine, this would be like "COM4".
        On a Unix machine, it would be lie "dev/ttyxxx".
        
        conversion_dict : dictionary {int : float}
            A dictionary that contains integer tubing sizes as keys and the corresponding
            volume (in mL) pumped by one revolution at the size as a float.
            
            Optional, but required to use volume functions.
    
    Attributes
    ----------
        serialID : string
            See above.
            
        conversion_dict : dictionary {int : float}
            See above.
        
        num_pumps : int
            Number to keep track of how many pumps are connected.
            
        speed_set : dict {int : boolean}
            Dictionary that stores pump IDs as keys and a boolean of if the speed 
            has been set for each pump at least once. This is to ensure that the pump isn't
            turned on without defining a direction or speed.
    '''
    
    def __init__(self, serialID, conversion_dict=None):
        self.serialID = serialID
        self.pump_dict = {}
        self.conversion_dict = conversion_dict
        
        self.status_dict = {0:{'0':'Local', '1':'Remote'},
                            3:{'1':'Idle', '2':'Waiting Go', '3':'Running',
                               '4':'Stopped Locally', '5':'No Motor Feedback', '6':'Overload',
                               '7':'Excessive Motor Feedback'},
                            4:{'0':'None', '1':'Parity', '2':'Framing', '3':'Overun', 
                               '4':'Invalid Command', '5':'Invalid Data'}}
        
        try:
            self.serial_dev = serial.Serial(self.serialID, baudrate=4800,
                                            parity=serial.PARITY_ODD,
                                            bytesize=serial.SEVENBITS, 
                                            stopbits=serial.STOPBITS_ONE,
                                            timeout=0.06)
        except Exception as e:
            print("Got the following exception connecting", e)
        
        
        while('?' in self.rts_status()):
            pump_num = len(self.pump_dict) + 1
            reply = self.assign_pump(pump_num)
            
            if reply == b'\x06':
                self.pump_dict[pump_num] = Pump(pump_num)

            else:
                raise RuntimeError('Pump did not acknowledge assignment') 
                
        if len(self.pump_dict) == 0:
            self.close()
            raise RuntimeError('No pumps were connected. Ensure connection/restart pumps')
            
    def assign_pump(self, pump_num):
        '''
        Assigns a number to a pump.
        
        Tells the current pump what number it is upon intialization.
        
        Parameters
        ----------
            pump_num : int
                The number the pump will be assigned, 1-25.
        '''
        self.serial_dev.write(b'\x02' + bytes(f'P{pump_num:02}', 'ascii') + b'\x0D')
        return self.serial_dev.read(64)
        
    def rts_status(self):
        '''
        Checks if a pump is sending RTS
        
        Returns
        -------
            string : Message (if any) by enquire command.
        '''
        self.serial_dev.write(b'\x05')
        return self.serial_dev.read(64).decode()
    
    def check_status(self, pump_num):
        self.valid_pump(pump_num)
        
        try:
            self.serial_dev.write(b'\x02' + bytes(f'P{pump_num:02}I', 'ascii') + b'\x0D')
            reply = self.serial_dev.read(100).decode()[5:-1] # the 5 returned numbers
        except serial.SerialException:
            return tuple(['Disconnected' for i in range(3)])
        
        try:
            return tuple([self.status_dict[i][reply[i]] for i in [0,3,4]])
        except (IndexError, KeyError):
            return ('','','')
        
    def full_info(self, pump_num):
        self.valid_pump(pump_num)
        
        pump = self.pump_dict[pump_num]
        
        try:
            total_vol = pump.get_total_vol()
        except AttributeError:
            total_vol = "Unknown"
        
        return (pump.vol_per_rev, total_vol, pump.rpm, pump.direction) +\
                self.check_status(pump_num)
        
    def assign_speed(self, pump_num, direction, rpm):
        '''
        Assigns a direction and rpm to a specfic pump.
        
        Parameters
        ----------
            pump_num : int
                The ID of the pump to assign
            
            direction : string
                The direction for the pump to turn, either "CW" (clockwise) or 
                "CCW" (counter-clockwise). Ignores case.
                
            rpm : float
                RPM of the pump. Must be between 10 (slowest) and 600 (fastest), inclusive.
                
        
        '''
        self.valid_pump(pump_num)
        
        rpm = float(rpm)
        
        if rpm > 600 or rpm < 10:
            raise ValueError('Not a valid rpm (10 <= rpm <= 600)')   
        direction = direction.lower()
        if direction not in ['cw', 'ccw']:
            raise ValueError('Direction must be cw or ccw')
        
        rpm = round(rpm, 1)
        
        dir_dict = {'cw':'+', 'ccw':'-'}
        self.serial_dev.write(b'\x02' + bytes(f'P{pump_num:02}S{dir_dict[direction]}{rpm:05}',
                                              'ascii') + b'\x0D')
        reply = self.serial_dev.read(64)
        
        # Handle if the pump is currently running in the opposite direction and
        # needs to be halted.
        if b'0x15' in reply:
            self.halt_pump(pump_num)
            
            self.assign_speed(pump_num, direction, rpm)    
        self.pump_dict[pump_num].set_speed(direction, rpm)
        
        
    def assign_rev(self, pump_num, rev, run=True):
        '''
        Assign the number of revolutions to spin for a pump. Runs immediately by default.
        
        Parameters
        ----------
            pump_num : int
                The ID of the pump to assign
            
            rev : float
                Number of revolutions to run. Must be positive.
            
            run : boolean
                Boolean for if the pump should immediately execute these revolutions.
                True by default.
        
        Raises
        ------
            ValueError
                If rev < 0 (must be positive)
        '''
        self.valid_pump(pump_num)

        if rev < 0:
            raise ValueError('rev must be a positive number')
        
        rev = round(rev, 2)
        
        if rev != 0:
            self.serial_dev.write(b'\x02' + bytes(f'P{pump_num:02}V{rev:08}',
                                                  'ascii') + b'\x0D')
            
            self.pump_dict[pump_num].total_rev += rev
            if run:
                self.run_pump(pump_num)
    
    def run_pump(self, pump_num):
        '''
        Run the revolutions currently set for the specified pump
        
        Parameters
        ----------
            pump_num : int
                The ID of the pump to run.
            
        Raises
        ------
            ValueError
                If assign_speed() hasn't been called at least once for this pump.
        '''
                
        self.valid_pump(pump_num)
        
        if self.pump_dict[pump_num].rpm == 0:
            raise ValueError('Pump must have speed assigned before running')
            
        self.serial_dev.write(b'\x02' + bytes(f'P{pump_num:02}G',
                                              'ascii') + b'\x0D')
        
    def halt_pump(self, pump_num):
        '''
        Stop the specified pump.
        
        Parameters
        ----------
            pump_num : int
                The ID of the pump to halt.
        '''
        self.valid_pump(pump_num)
        
        self.serial_dev.write(b'\x02' + bytes(f'P{pump_num:02}H', 'ascii') + b'\x0D')
        
    def close(self):
        '''
        Assigns local control to all pumps, then closes the serial port.
        '''
        for i in self.pump_dict:
            self.serial_dev.write(b'\x02' + bytes(f'P{i:02}L',
                                                  'ascii') + b'\x0D')
        self.serial_dev.close()
        
    def get_total_revs(self, pump_num):
        '''
        Get the total revolutions run by the specified pump since this object's creation.
        
        Parameters
        ----------
            pump_num : int
                The ID of the pump to query.
                
        Returns
        -------
            float
                The number of revolutions run by the pump.
        '''
        self.valid_pump(pump_num)
        self.serial_dev.write(b'\x02' + bytes(f'P{pump_num:02}C',
                                                  'ascii') + b'\x0D')
        
        return self.serial_dev.read(16).decode()
        #return float(reply[3:-2])
            
    def dispense_vol(self, pump_num, vol):
        '''
        Dispense a volume in mL from a specified pump.
        
        As with any run, speed must be set at least once. conversion_dict must 
        have tubing_size as a key.
        
        Parameters
        ----------
            pump_num : int
                The ID of the pump to dispense from.
            
            vol : float
                The volume to dispense in mL
        '''
        revs = self.pump_dict[pump_num].vol_to_rev(vol)
        self.assign_rev(pump_num, revs)
       
    def valid_pump(self, pump_num):
        ''' Checks if this pump is valid. Raises ValueError if not.'''
        if pump_num not in self.pump_dict:
            raise ValueError('Not a valid pump ID')
            
    def valid_converison(self, tubing_size):
        '''Checks if tubing_size is defined in conversion_dict. Raises ValueError if not.'''
        if self.conversion_dict is None:
            raise ValueError('Volume Conversion dictionary must be defined')
        if tubing_size not in self.conversion_dict:
            raise ValueError('Conversion not defined for this tubing size')
            
    def set_vol_per_rev(self, pump_num, vol_per_rev):
        self.pump_dict[pump_num].set_vol_per_rev(vol_per_rev)
            
class Pump(object):
    
    def __init__(self, ID):
        self.ID = ID
        self.total_rev = 0
        self.rpm = 0
        self.vol_per_rev = None
        self.direction = None
        
    def set_vol_per_rev(self, vol_per_rev):
        vol_per_rev = float(vol_per_rev)
        if vol_per_rev < 0 :
            raise ValueError("Volume must be positive")
        self.vol_per_rev = vol_per_rev
        
    def set_speed(self, direction, rpm):
        self.direction = direction
        self.rpm = rpm
            
        
    def get_total_vol(self):
        if self.vol_per_rev == None:
            raise AttributeError('vol_per_rev not assigned for this pump')
        return self.total_rev * self.vol_per_rev
    
    def vol_to_rev(self, vol):
        if vol < 0:
            raise ValueError('Volume must be positive')
        if self.vol_per_rev == None:
            raise AttributeError("Volume (mL) per rev for this pump has not been assigned")
        return vol / self.vol_per_rev 
        
        
        
        
    
    