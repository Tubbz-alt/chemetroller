# -*- coding: utf-8 -*-
"""
Created on Wed Jul 31 09:11:21 2019

@author: Raman
"""

from opcua import Server, ua

server = Server()
#server.set_endpoint('opc.tcp://0.0.0.04840/UA/SampleServer')
objects = server.get_objects_node()
myobj = objects.add_object(86, "MyObject")
myvar1 = myobj.add_variable(87, "MyVar1", 6.7)
server.start()