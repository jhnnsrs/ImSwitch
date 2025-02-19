from imswitch.imcommon.model import initLogger
from .PositionerManager import PositionerManager



class SQUIDStageManager(PositionerManager):
    SPEED=1000

    def __init__(self, positionerInfo, name, **lowLevelManagers):
        super().__init__(positionerInfo, name, initialPosition={
            axis: 0 for axis in positionerInfo.axes
        })
        self._rs232manager = lowLevelManagers['rs232sManager'][
            positionerInfo.managerProperties['rs232device']
        ]
        self.__logger = initLogger(self, instanceName=name)

    def move(self, value, axis, speed=1000):
        if axis == 'X':
            self._rs232manager._squid.move_x_usteps(int(value))
        elif axis == 'Y':
            self._rs232manager._squid.move_y_usteps(int(value))
        elif axis == 'Z':
            self._rs232manager._squid.move_z_usteps(int(value))
        else:
            print('Wrong axis, has to be "X" "Y" or "Z".')
            return
        self._position[axis] = self._position[axis] + value
        
    def homing(self):
        self._rs232manager._squid.home_xy()

    def setPosition(self, value, axis):
        self._position[axis] = value

    def getPosition(self):
        posX,posY,posZ,posTheta = self._rs232manager._squid.get_pos() 
        self._position["X"]=posX
        self._position["Y"]=posY
        self._position["Z"]=posZ
        return self._position
        
    def is_busy(self):
        return self._rs232manager._squid.is_busy()      

    def get_abs(self, axis=1):
        self._position = self._rs232manager._squid.get_pos()
        return self._position["Z"]

    def closeEvent(self):
        self._rs232manager._squid.close()



# Copyright (C) 2020, 2021 The imswitch developers
# This file is part of ImSwitch.
#
# ImSwitch is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ImSwitch is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
