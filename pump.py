# -*- coding: utf-8 -*-
"""
Created on Wed Aug 21 12:44:09 2019

@author: Isaiah Lemmon isaiah.lemmon@pnnl.gov

This module creates an interface to communicate with Cole-Parmer Pumps via 
a serial connection
"""

import serial
import time
import re
import asyncio

response_regex = re.compile(r"\d{5}")

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
            On a Unix machine, it would be like "dev/ttyxxx".
        
    Attributes
    ----------
        serialID : string
            See above.
            
        pump_dict : dict{int : pump.Pump}
            A dictionary storing Pump objects. The key is the ID of the Pump when it
            was assigned by the serial connection, and the value is the Pump object
        
        status_dict : dict{int : dict{string : string}}
            A dictionary used to decode the status string returned from the pump.
            
            The keys of the outer dict corresponds to the index of the character \
            info part of the status string.
            
            The keys of the inner dicts correspond to possible values that the index could
            be, and how those values should be interpreted into a human readable form
            
    '''
    
    def __init__(self, serialID):
        self.serialID = serialID
        self.pump_dict = {}
        
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
        
            while('?' in self.rts_status()):
                pump_num = len(self.pump_dict) + 1
                reply = self.assign_pump(pump_num)
                
                if reply == b'\x06': # Acknowldge assignment
                    self.pump_dict[pump_num] = Pump(pump_num)
    
                else:
                    raise RuntimeError('Pump did not acknowledge assignment')
                    
            if len(self.pump_dict) == 0:
                self.close()
                raise RuntimeError('No pumps were connected. Ensure connection/restart pumps')
        
        except serial.SerialException as e:
            raise PermissionError(e)
            
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
        '''
        Check the status of the Pump at pump_num in a human readable tuple
        
        Requests info from the pump. Uses stats_dict to return information about
        the pump's control
        
        Parameters
        ----------
            pump_num : the ID of the pump to check
            
        Returns 
        -------
            tuple(string, string, string)
            
            If there is no connection, returns (Disconnected, Disconnected, Disconnected)
            
            Otherwise returns (Control_string, status_string, error_string)
        '''
        self.valid_pump(pump_num)
        
        try:
            self.serial_dev.read(100) # Clear buffer
            self.serial_dev.write(b'\x02' + bytes(f'P{pump_num:02}I', 'ascii') + b'\x0D')
            # the 5 returned numbers
            reply = self.serial_dev.read(100).decode()
            status = re.search(response_regex, reply).group(0)
            
        # if no connection return Disconnected tuple
        except serial.SerialException:
            return tuple(['Disconnected' for i in range(3)])
        
        try:
            return tuple([self.status_dict[i][status[i]] for i in [0,3,4]])
        
        # Catch error where there wasn't enough time for the pump to respond
        except (IndexError, KeyError):
            return ('','','')
        
    def full_info(self, pump_num):
        '''
        Return the full information about a pump
        
        Similar to check_status(), but adds vol_per_rev, total_vol, rpm, and direction
        in addition to check_status's return.
        
        If vol_per_rev is None (unassigned), total_volume returns as the string "Unknown"
        
        Parameters
        ----------
            pump_num : int
                The number of the pump to get info about
        
        Returns
        -------
            tuple(float, float, float, string, string, string, string)
            
            Returns a tuple of information in the format
            (vol_per_rev, total_vol, rpm, direection) + check_status(pump_num)
        '''
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
            if self.valid_pump(i):
                self.serial_dev.write(b'\x02' + bytes(f'P{i:02}L',
                                                  'ascii') + b'\x0D')
        self.serial_dev.close()
        
    def get_total_revs(self, pump_num):
        '''
        NOT IMPLEMENTED 
        Get the total revolutions run by the specified pump since this object's creation.
        
        Would get 
        
        Parameters
        ----------
            pump_num : int
                The ID of the pump to query.
                
        Returns
        -------
            float
                The number of revolutions run by the pump.
        '''
        raise NotImplementedError('This feature is not yet implemented. Use Pump.get_total_vol()')
        self.valid_pump(pump_num)
        self.serial_dev.write(b'\x02' + bytes(f'P{pump_num:02}C',
                                                  'ascii') + b'\x0D')
        
        return self.serial_dev.read(16).decode()

            
    async def dispense_vol(self, pump_num, vol):
        '''
        Dispense a volume in mL from a specified pump.
        
        As with any run, speed must be set at least once. vol_per_rev must 
        be assigned for this pump.
        
        Parameters
        ----------
            pump_num : int
                The ID of the pump to dispense from.
            
            vol : float
                The volume to dispense in mL
        '''
        # Handle virtual pump case
        if type(self.pump_dict[pump_num]) == VPump:
            ratio = self.pump_dict[pump_num].ratio
            
            pump_1 = self.pump_dict[pump_num].pump_1
            pump_2 = self.pump_dict[pump_num].pump_2
            
            # Calculate revolutions based on the ratio to each pump
            rev_1 = pump_1.vol_to_rev(vol * ratio)
            rev_2 = pump_2.vol_to_rev(vol * (1 - ratio))
            
            # Run revolution of first pump and run
            self.assign_rev(pump_1.ID, rev_1, run=True)
            
            # Assign revolution of second pump, but don't run right away
            self.assign_rev(pump_2.ID, rev_2, run=False)
            
            # Wait until first pump has finished
            while self.check_status(pump_1.ID)[1] == 'Running':
                await asyncio.sleep(1)
            
            # Run second pump
            self.run_pump(pump_2.ID)
            
        else:
            revs = self.pump_dict[pump_num].vol_to_rev(vol)
            self.assign_rev(pump_num, revs)
       
    def valid_pump(self, pump_num):
        ''' Checks if this pump is valid and real. Raises ValueError if not.'''
        if pump_num not in self.pump_dict:
            raise ValueError('Not a valid pump ID')
            
        if type(self.pump_dict[pump_num]) == VPump:
            raise ValueError('Must not be a virtual pump')
            
    def set_vol_per_rev(self, pump_num, vol_per_rev):
        '''
        Sets the vol_per_rev attribute of the specified pump.
        '''
        self.pump_dict[pump_num].set_vol_per_rev(vol_per_rev)
        
    def add_vpump(self, pump_num_1, pump_num_2, ratio):
        self.valid_pump(pump_num_1)
        self.valid_pump(pump_num_2)
        
        num_pumps = len(self.pump_dict)
        
        key = f"VP{num_pumps + 1}"
        self.pump_dict[key] = VPump(self.pump_dict[pump_num_1], 
                                              self.pump_dict[pump_num_2], ratio)
        
    def set_vpump(self, vpump_id, pump_num_1, pump_num_2, ratio):
        if type(self.pump_dict[vpump_id]) is not VPump:
            raise ValueError("Passed ID must refer to a virtual pump")
        
        self.pump_dict[vpump_id].pump_1 = self.pump_dict[pump_num_1]
        self.pump_dict[vpump_id].pump_2 = self.pump_dict[pump_num_2]
        self.pump_dict[vpump_id].ratio = ratio
        
            
class Pump(object):
    '''
    Helper class to keep track of attributes of connected pumps
    
    Parameters
    ----------
        ID : int
            The ID of this pump in the serial connection
    
    Attributes
    ----------
        ID : int
            The ID of this pump
            
        total_rev : float
            The total number of revolutions this pumps has been told to do
            
        rpm : int
            The speed this pump will run at. Initially 0
            
        vol_per_rev : float
            The volume in mL dispensed by this pump every revolution. Initially None
            
        direction : string
            CW or CCW turning. Initially None
    '''
    
    def __init__(self, ID):
        self.ID = ID
        self.total_rev = 0
        self.rpm = 0
        self.vol_per_rev = None
        self.direction = None
        
    def set_vol_per_rev(self, vol_per_rev):
        '''
        Assign the volume (mL) per revolution
        
        Parameters
        ----------
            vol_per_rev : float
                The volume per revolution. Must be greater than 0
        '''
        vol_per_rev = float(vol_per_rev)
        if vol_per_rev <= 0 :
            raise ValueError("Volume must be greater than 0")
        self.vol_per_rev = vol_per_rev
        
    def set_speed(self, direction, rpm):
        '''
        Set the speed and direction attributes
        
        Parameters
        ----------
            direction : string
                CCW or CW
            
            rpm : int
                Revolutions per minute to run at
        '''
        self.direction = direction
        self.rpm = rpm
            
        
    def get_total_vol(self):
        '''
        Gets the total volume dispensed by this pump
        
        vol_per_rev must be assigned before calling this
        
        Returns
        -------
            float : The total volume dispsensed in mL
        '''
        if self.vol_per_rev == None:
            raise AttributeError('vol_per_rev not assigned for this pump')
        return self.total_rev * self.vol_per_rev
    
    def vol_to_rev(self, vol):
        '''
        Takes a volume in mL and converts to revolutions for this pump
        
        vol cannot be negative and vol_per_rev must be assigned
        
        Returns
        -------
            float : The number of revolutions to dispense this volume
        '''
        if vol < 0:
            raise ValueError('Volume must be positive')
        if self.vol_per_rev == None:
            raise AttributeError("Volume (mL) per rev for this pump has not been assigned")
        return vol / self.vol_per_rev 
    
        
        
class VPump(object):
    
    def __init__(self, pump_1, pump_2, ratio):
        self.pump_1 = pump_1
        self.pump_2 = pump_2
        self.ratio = ratio # ratio of pump 1 to 2
        
