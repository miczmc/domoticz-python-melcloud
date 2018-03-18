# MELCloud Plugin
# Author:     Gysmo, 2017
# Version: 0.6
#   
# Release Notes:
# v0.7 : Use builtin https support to avoid urllib segmentation fault on binaries
# v0.6.1 : Change Update function to not crash with RPI
# v0.6 : Rewrite of the module to be easier to maintain
# v0.5.1: Problem with device creation
# v0.5 : Upgrade code to be compliant wih new functions
# v0.4 : Search devices in floors, areas and devices
# v0.3 : Add Next Update information, MAC Address  and Serial Number
#         Add Horizontal vane
#         Add Vertival vane
#         Add Room Temp
# v0.2 : Add sync between Domoticz devices and MELCloud devices
#        Usefull if you use your Mitsubishi remote
# v0.1 : Initial release
"""
<plugin key="MELCloud" version="0.7" name="MELCloud plugin" author="gysmo" wikilink="http://www.domoticz.com/wiki/Plugins/MELCloud.html" externallink="http://www.melcloud.com">
    <params>
        <param field="Username" label="Email" width="200px" required="true" />
        <param field="Password" label="Password" width="200px" required="true" />
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
    </params>
</plugin>
"""

import Domoticz
import time
import json

class BasePlugin:
    
    melcloud_conn = None
    melcloud_baseurl = "app.melcloud.com"
    melcloud_port = "443"
    melcloud_key = None
    melcloud_state = "Not Ready"
    
    melcloud_urls = {}
    melcloud_urls["login"] = "/Mitsubishi.Wifi.Client/Login/ClientLogin"
    melcloud_urls["list_unit"] = "/Mitsubishi.Wifi.Client/User/ListDevices"
    melcloud_urls["set_unit"] = "/Mitsubishi.Wifi.Client/Device/SetAta"
    melcloud_urls["unit_info"] = "/Mitsubishi.Wifi.Client/Device/Get"
    
    list_units = []
    
    list_switchs = []
    list_switchs.append({"id":1,"name":"Mode","typename":"Selector Switch","image":16,"levels":"Off|Warm|Cold|Vent|Dry"})
    list_switchs.append({"id":2,"name":"Fan","typename":"Selector Switch","image":7,"levels":"Level1|Level2|Level3|Level4|Level5|Auto|Silence"})
    list_switchs.append({"id":3,"name":"Temp","typename":"Selector Switch","image":15,"levels":"16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31"})
    list_switchs.append({"id":4,"name":"Vane Horizontal","typename":"Selector Switch","image":7,"levels":"1|2|3|4|5|Swing|Auto"})
    list_switchs.append({"id":5,"name":"Vane Vertical","typename":"Selector Switch","image":7,"levels":"1|2|3|4|5|Swing|Auto"})
    list_switchs.append({"id":6,"name":"Room Temp","typename":"Temperature"})
    list_switchs.append({"id":7,"name":"Unit Infos","typename":"Text"})
    
    domoticz_levels = {}
    domoticz_levels["mode"] = {"0":0,"10":1,"20":3,"30":7,"40":2}
    domoticz_levels["mode_pic"] = {"0":9,"10":15,"20":16,"30":7,"40":11}
    domoticz_levels["fan"] = {"0":1,"10":2,"20":3,"30":4,"40":255,"50":0,"60":1}
    domoticz_levels["temp"] = {"0":16,"10":17,"20":18,"30":19,"40":20,"50":21,"60":22,"70":23,"80":24,"90":25,"100":26,"110":27,"120":28,"130":29,"140":30,"150":31}
    domoticz_levels["vaneH"] = {"0":1,"10":2,"20":3,"30":4,"40":5,"50":12,"60":0}
    domoticz_levels["vaneV"] = {"0":1,"10":2,"20":3,"30":4,"40":5,"50":7,"60":0}
    
    enabled = False
    
    def __init__(self):
        return

    def onStart(self):
        Domoticz.Heartbeat(25)
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(62)
        # Start connection to MELCloud
        self.melcloud_conn = Domoticz.Connection(Name="MELCloud", Transport="TCP/IP", Protocol="HTTPS", Address=self.melcloud_baseurl, Port=self.melcloud_port)
        self.melcloud_conn.Connect()
        return True

    def onStop(self):
        Domoticz.Log("Goobye from MELCloud plugin.")

    def onConnect(self, Connection, Status, Description):
        if (Status == 0):
            Domoticz.Log("Connection to MELCloud OK")
            self.melcloud_state = "READY"
            self.melcloud_login()
        else:
            Domoticz.Log("Failed to connect ("+str(Status)+") to: "+Parameters["Address"]+":"+Parameters["Port"]+" with error: "+Description)

    def onMessage(self, Connection, Data):
        Status = int(Data["Status"])
        if (Status == 200):
            strData = Data["Data"].decode("utf-8", "ignore")
            response = json.loads(strData)
            Domoticz.Debug("JSON REPLY: "+str(response))
            if(self.melcloud_state == "LOGIN"):
                Domoticz.Log("Context ID: "+str(response["LoginData"]["ContextKey"]))
                self.melcloud_key = response["LoginData"]["ContextKey"]
                self.melcloud_units_init()             
            elif(self.melcloud_state == "UNITS_INIT"):
                idoffset = 0
                Domoticz.Log("Find "+str(len(response))+ " buildings")
                for building in response:
                    Domoticz.Log("Find "+str(len(building["Structure"]["Areas"]))+ " areas in building "+building["Name"])
                    Domoticz.Log("Find "+str(len(building["Structure"]["Floors"]))+ " floors in building "+building["Name"])
                    Domoticz.Log("Find "+str(len(building["Structure"]["Devices"]))+ " devices  in building "+building["Name"])
                    #Search in devices        
                    for device in building["Structure"]["Devices"]:
                        self.melcloud_add_unit(device,idoffset)
                        idoffset += len(self.list_switchs)
                    #Search in areas
                    for area in building["Structure"]["Areas"]:
                        for device in area["Devices"]:
                            self.melcloud_add_unit(device,idoffset)
                            idoffset += len(self.list_switchs)
                    #Search in floors
                    for floor in building["Structure"]["Floors"]:
                        for device in floor["Devices"]:
                            self.melcloud_add_unit(device,idoffset)
                            idoffset += len(self.list_switchs)
                        for area in floor["Areas"]:
                            for device in area["Devices"]:
                                self.melcloud_add_unit(device,idoffset)    
                                idoffset += len(self.list_switchs)
                self.melcloud_create_units()
            elif(self.melcloud_state == "UNIT_INFO"):
                for unit in self.list_units:
                    if(unit['id'] == response['DeviceID']):
                        Domoticz.Log("Update unit {0} information.".format(unit['name']))
                        unit['power'] = response['Power']
                        unit['op_mode'] = response['OperationMode']
                        unit['room_temp'] = response['RoomTemperature']
                        unit['set_temp'] = response['SetTemperature']
                        unit['set_fan'] = response['SetFanSpeed']
                        unit['vaneH'] = response['VaneHorizontal']
                        unit['vaneV'] = response['VaneVertical']
                        unit['next_comm'] = response['NextCommunication']
                        Domoticz.Log("Heartbeat unit info: "+str(unit))
                        self.domoticz_sync_switchs(unit)
            elif(self.melcloud_state == "SET"):
                Domoticz.Log("Next update for command: " + response["NextCommunication"])
            else:
                Domoticz.Log("State not implemented:" + self.melcloud_state)
           
    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
        #~ Get switch function: mode, fan, temp ...
        switch_id = Unit
        while switch_id > 7:
            switch_id -= 7
        switch_type = self.list_switchs[switch_id-1]["name"]
        #~ Get the unit in units array
        current_unit = False
        for unit in self.list_units:
            if (unit['idoffset'] + self.list_switchs[switch_id-1]["id"]) == Unit:
                current_unit = unit
                break
        if(switch_type == 'Mode'):
            if(Level == 0):
                flag = 1
                current_unit['power'] = 'false'
                Domoticz.Log("Switch Off the unit "+current_unit['name'] + "with ID offset " + str(current_unit['idoffset']))
                Devices[1+current_unit['idoffset']].Update(nValue = 0,sValue = str(Level), Image = 9)
                Devices[2+current_unit['idoffset']].Update(nValue = 0,sValue = str(Devices[Unit + 1].sValue))
                Devices[3+current_unit['idoffset']].Update(nValue = 0,sValue = str(Devices[Unit + 2].sValue))
                Devices[4+current_unit['idoffset']].Update(nValue = 0,sValue = str(Devices[Unit + 3].sValue))
                Devices[5+current_unit['idoffset']].Update(nValue = 0,sValue = str(Devices[Unit + 4].sValue)) 
            elif(Level == 10):
                Domoticz.Log("Set to WARM the unit "+current_unit['name'])
                Devices[1+current_unit['idoffset']].Update(nValue = 1,sValue = str(Level),Image = 15)
            elif(Level == 20):
                Domoticz.Log("Set to COLD the unit "+current_unit['name'])
                Devices[1+current_unit['idoffset']].Update(nValue = 1,sValue = str(Level),Image = 16)
            elif(Level == 30):
                Domoticz.Log("Set to Vent the unit "+current_unit['name'])
                Devices[1+current_unit['idoffset']].Update(nValue = 1,sValue = str(Level),Image = 7)
            elif(Level == 40):
                Domoticz.Log("Set to Dry the unit "+current_unit['name'])
                Devices[1+current_unit['idoffset']].Update(nValue = 1,sValue = str(Level),Image = 11)
            if(Level != 0):
                flag = 6
                current_unit['power'] = 'true'
                current_unit['op_mode'] = self.domoticz_levels['mode'][str(Level)]
                Devices[2+current_unit['idoffset']].Update(nValue = 1,sValue = str(Devices[Unit + 1].sValue))
                Devices[3+current_unit['idoffset']].Update(nValue = 1,sValue = str(Devices[Unit + 2].sValue))
                Devices[4+current_unit['idoffset']].Update(nValue = 1,sValue = str(Devices[Unit + 3].sValue))
                Devices[5+current_unit['idoffset']].Update(nValue = 1,sValue = str(Devices[Unit + 4].sValue))
        elif(switch_type == 'Fan'):
            flag = 8
            current_unit['set_fan'] = self.domoticz_levels['fan'][str(Level)]
            if(Level == 0):
                Domoticz.Log("Change FAN  to Level 1 for "+current_unit['name'])
            elif(Level == 10):
                Domoticz.Log("Change FAN  to Level 2 for "+current_unit['name'])
            elif(Level == 20):
                Domoticz.Log("Change FAN  to Level 3 for "+current_unit['name'])
            elif(Level == 30):
                Domoticz.Log("Change FAN  to Level 4 for "+current_unit['name'])
            elif(Level == 40):
                Domoticz.Log("Change FAN  to Silence for "+current_unit['name'])
            elif(Level == 50):
                Domoticz.Log("Change FAN  to Auto for "+current_unit['name'])
            Devices[Unit].Update(nValue = Devices[Unit].nValue,sValue =  str(Level))
        elif(switch_type == 'Temp'):
            flag = 4
            setTemp = 16
            if(Level != 0):
                setTemp = int(str(Level).strip("0")) + 16
            Domoticz.Log("Change Temp to " + str(setTemp) + " for "+unit    ['name'])
            current_unit['set_temp'] = self.domoticz_levels['temp'][str(Level)]
            Devices[Unit].Update(nValue = Devices[Unit].nValue,sValue =  str(Level))
        elif(switch_type == 'Vane Horizontal'):
            flag = 256
            current_unit['vaneH'] = self.domoticz_levels['vaneH'][str(Level)]
            if(Level == 0):                
                Domoticz.Debug("Change Vane Horizontal to Level 1 for "+current_unit['name'])
            elif(Level == 10):
                Domoticz.Debug("Change Vane Horizontal to Level 2 for "+current_unit['name'])
            elif(Level == 20):
                Domoticz.Debug("Change Vane Horizontal to Level 3 for "+current_unit['name'])
            elif(Level == 30):
                Domoticz.Debug("Change Vane Horizontal to Level 4 for "+current_unit['name'])
            elif(Level == 40):
                Domoticz.Debug("Change Vane Horizontal to Level 5 for "+current_unit['name'])
            elif(Level == 50):
                Domoticz.Debug("Change Vane Horizontal to Swing for "+current_unit['name'])
            elif(Level == 60):
                Domoticz.Debug("Change Vane Horizontal to Auto for "+current_unit['name'])
            Devices[Unit].Update(Devices[Unit].nValue, str(Level))
        elif(switch_type == 'Vane Vertical'):
            flag = 16
            current_unit['vaneV'] = self.domoticz_levels['vaneV'][str(Level)]
            if(Level == 0):
                Domoticz.Debug("Change Vane Vertical to Level 1 for "+current_unit['name'])
            elif(Level == 10):
                Domoticz.Debug("Change Vane Vertical to Level 2 for "+current_unit['name'])
            elif(Level == 20):
                Domoticz.Debug("Change Vane Vertical to Level 3 for "+current_unit['name'])
            elif(Level == 30):
                Domoticz.Debug("Change Vane Vertical to Level 4 for "+current_unit['name'])
            elif(Level == 40):
                Domoticz.Debug("Change Vane Vertical to Level 5 for "+current_unit['name'])
            elif(Level == 50):
                Domoticz.Debug("Change Vane Vertical to Swing for "+current_unit['name'])
            elif(Level == 60):
                Domoticz.Debug("Change Vane Vertical to Auto for "+current_unit['name'])
            Devices[Unit].Update(Devices[Unit].nValue, str(Level))
        else:
            Domoticz.Log("Device not found")
        self.melcloud_set(current_unit,flag)
        return True

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self):
        Domoticz.Log("onDisconnect called")

    def onHeartbeat(self):
        Domoticz.Log("Current MEL Cloud Key ID:"+self.melcloud_key)
        for unit in self.list_units:
            self.melcloud_get_unit_info(unit)

    def melcloud_create_units(self):
        Domoticz.Log("Units infos " + str(self.list_units))
        if (len(Devices) == 0):
            # Init Devices
            # Creation of switches
            Domoticz.Log("Find " + str(len(self.list_units)) + " devices in MELCloud")
            for device in self.list_units:
                Domoticz.Log("Creating device: " + device['name'] + " with melID " + str(device['id']))
                for switch in self.list_switchs:
                    # Create switchs
                    if switch["typename"] == "Selector Switch":
                        switch_options = {"LevelNames": switch["levels"],"LevelOffHidden": "false","SelectorStyle": "1"}
                        Domoticz.Device(Name=device['name']+" - "+switch["name"], Unit=switch["id"]+device['idoffset'], TypeName=switch["typename"], Image=switch["image"], Options=switch_options, Used=1).Create()
                    else:
                        Domoticz.Device(Name=device['name']+" - "+switch["name"], Unit=switch["id"]+device['idoffset'], TypeName=switch["typename"], Used=1).Create()

    def melcloud_send_data(self,url,values,state):
        if self.melcloud_key is not None:
            headers = { 'Content-Type': 'application/x-www-form-urlencoded;', \
                        'Host': self.melcloud_baseurl, \
                        'User-Agent':'Domoticz/1.0', \
                        'X-MitsContextKey': self.melcloud_key}
            if(state == "SET"):
                 self.melcloud_conn.Send({'Verb':'POST', 'URL':url,'Headers': headers, 'Data': values})
            else:
                 self.melcloud_conn.Send({'Verb':'GET', 'URL':url,'Headers': headers, 'Data': values})
        else :
            headers = { 'Content-Type': 'application/x-www-form-urlencoded;', \
                        'Host': self.melcloud_baseurl, \
                        'User-Agent':'Domoticz/1.0'}              
            self.melcloud_conn.Send({'Verb':'POST', 'URL':url,'Headers': headers, 'Data': values})
        self.melcloud_state = state
        return True

    
    def melcloud_login(self):
        data = "AppVersion=1.9.3.0&Email={0}&Password={1}".format(Parameters["Username"],Parameters["Password"])
        self.melcloud_send_data(self.melcloud_urls["login"],data,"LOGIN")
        return True
    
    def melcloud_add_unit(self,device,idoffset):
        melcloud_unit = {}
        melcloud_unit['name'] = device["DeviceName"]
        melcloud_unit['id'] = device["DeviceID"]
        melcloud_unit['macaddr'] = device["MacAddress"]
        melcloud_unit['sn'] = device["SerialNumber"]
        melcloud_unit['building_id'] = device["BuildingID"]
        melcloud_unit['power'] = ""
        melcloud_unit['op_mode'] = ""
        melcloud_unit['room_temp'] = ""
        melcloud_unit['set_temp'] = ""
        melcloud_unit['set_fan'] = ""
        melcloud_unit['vaneH'] = ""
        melcloud_unit['vaneV'] = ""
        melcloud_unit['next_comm'] = ""
        melcloud_unit['idoffset'] = idoffset
        self.list_units.append(melcloud_unit)

    def melcloud_update_unit(self,meldevice,device):
        melDevice['power'] = device['Power']
        melDevice['opmode'] = device['OperationMode']
        melDevice['roomtemp'] = device['RoomTemperature']

    def melcloud_units_init(self):
        self.melcloud_send_data(self.melcloud_urls["list_unit"],None,"UNITS_INIT")
        return True
    def melcloud_set(self,unit,flag):
        post_fields = "Power={0}&DeviceID={1}&OperationMode={2}&SetTemperature={3}&SetFanSpeed={4}&VaneHorizontal={5}&VaneVertical={6}&EffectiveFlags={7}&HasPendingCommand=true".format(unit['power'],unit['id'],unit['op_mode'],unit['set_temp'],unit['set_fan'],unit['vaneH'],unit['vaneV'],flag)
        Domoticz.Debug("SET COMMAND SEND {0}".format(post_fields))
        self.melcloud_send_data(self.melcloud_urls["set_unit"],post_fields,"SET")
     
    def melcloud_get_unit_info(self,unit):
        url = self.melcloud_urls["unit_info"]+"?id="+str(unit['id'])+"&buildingID="+str(unit['building_id'])
        self.melcloud_send_data(url,None,"UNIT_INFO")
        
    def domoticz_sync_switchs(self,unit):
        for level, mode in self.domoticz_levels["mode"].items():
            if(mode == unit['op_mode']):
                setModeLevel = level
        for level, pic in self.domoticz_levels["mode_pic"].items():
            if(level == setModeLevel):
                setPicID = pic                
        for level, fan in self.domoticz_levels["fan"].items():
            if(fan == unit['set_fan']):
                setDomFan = level
        for level, temp in self.domoticz_levels["temp"].items():
            if(temp == unit['set_temp']):
                setDomTemp = level
        for level, vaneH in self.domoticz_levels["vaneH"].items():
            if(vaneH == unit['vaneH']):
                setDomVaneH = level
        for level, vaneV in self.domoticz_levels["vaneV"].items():
            if(vaneV == unit['vaneV']):
                setDomVaneV = level
        if(unit['power']):
            switch_value = 1
        else:
            switch_value = 0
            setModeLevel = '0'
        Devices[self.list_switchs[0]["id"]+unit["idoffset"]].Update(nValue = switch_value,sValue = setModeLevel,Image = setPicID)
        Devices[self.list_switchs[1]["id"]+unit["idoffset"]].Update(nValue = switch_value,sValue = setDomFan)
        Devices[self.list_switchs[2]["id"]+unit["idoffset"]].Update(nValue = switch_value,sValue = setDomTemp)
        Devices[self.list_switchs[3]["id"]+unit["idoffset"]].Update(nValue = switch_value,sValue = setDomVaneH)
        Devices[self.list_switchs[4]["id"]+unit["idoffset"]].Update(nValue = switch_value,sValue = setDomVaneV)
        Devices[self.list_switchs[5]["id"]+unit["idoffset"]].Update(nValue = switch_value,sValue = str(unit['room_temp']))

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


