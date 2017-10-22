# The MIT License (MIT)
#
# Copyright (c) 2017 ladyada for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`adafruit_sgp30`
====================================================

I2C driver for SGP30 Sensirion VoC sensor

* Author(s): ladyada
"""
from adafruit_bus_device.i2c_device import I2CDevice
import time

SGP30_DEFAULT_I2C_ADDR  = const(0x58)
SGP30_FEATURESET        = const(0x0020)

SGP30_CRC8_POLYNOMIAL   = const(0x31)
SGP30_CRC8_INIT         = const(0xFF)
SGP30_WORD_LEN          = const(2)

class Adafruit_SGP30: 
    def __init__(self, i2c, address=SGP30_DEFAULT_I2C_ADDR):
        """Initialize the sensor, get the serial # and verify that we found a proper SGP30"""
        self._device = I2CDevice(i2c, address)

        # get unique serial, its 48 bits so we store in an array
        self._serial = self.sgp_i2c_read_words_from_cmd([0x36, 0x82], 0.01, 3)
        # get featuerset
        featureset = self.sgp_i2c_read_words_from_cmd([0x20, 0x2f], 0.01, 1)
        if featureset[0] != SGP30_FEATURESET:
            raise RuntimeError('SGP30 Not detected')
        self.sgp_iaq_init()
        
    def sgp_iaq_init(self):
        """Initialize the IAQ algorithm"""
        # name, command, signals, delay
        self.sgp_run_profile(["iaq_init", [0x20, 0x03], 0, 0.01])

    def sgp_iaq_measure(self):
        """Measure the CO2eq and TVOC"""
        # name, command, signals, delay
        return self.sgp_run_profile(["iaq_measure", [0x20, 0x08], 2, 0.05])

    def sgp_get_iaq_baseline(self):
        """Retreive the IAQ algorithm baseline for CO2eq and TVOC"""
        # name, command, signals, delay
        return self.sgp_run_profile(["iaq_get_baseline", [0x20, 0x15], 2, 0.01])


    def sgp_set_iaq_baseline(self, co2eq, tvoc):
        if co2eq == 0 and tvoc == 0:
            raise RuntimeError('Invalid baseline')
        buffer = []
        for v in [tvoc, co2eq]:
            arr = [v >> 8, v & 0xFF]
            arr.append(self.sensirion_common_generate_crc(arr))
            buffer += arr
        self.sgp_run_profile(["iaq_set_baseline", [0x20, 0x1e] + buffer, 0, 0.01]) 


    # Low level command functions
    
    def sgp_run_profile(self, profile):
        """Run an SGP 'profile' which is a named command set"""
        name, command, signals, delay = profile
        #print("\trunning profile: %s, command %s, %d, delay %0.02f" % (name, ["0x%02x" % i for i in command], signals, delay))
        return self.sgp_i2c_read_words_from_cmd(command, delay, signals)


    def sgp_i2c_read_words_from_cmd(self, command, delay, reply_size):
        """Run an SGP command query, get a reply and CRC results if necessary"""
        with self._device:
            self._device.write(bytes(command))
            time.sleep(delay)
            if not reply_size:
                return None
            crc_result = bytearray(reply_size * (SGP30_WORD_LEN +1))
            self._device.read_into(crc_result)
            #print("\tRaw Read: ", crc_result)
            result = []
            for i in range(reply_size):
                word = [crc_result[3*i], crc_result[3*i+1]]
                crc = crc_result[3*i+2]
                if self.sensirion_common_generate_crc(word) != crc:
                    raise RuntimeError('CRC Error')
                result.append(word[0] << 8 | word[1])
            #print("\tOK Data: ", [hex(i) for i in result])
            return result

    def sensirion_common_generate_crc(self, data):
        """8-bit CRC algorithm for checking data"""
        crc = SGP30_CRC8_INIT
        # calculates 8-Bit checksum with given polynomial
        for byte in data:
            crc ^= byte
            for i in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ SGP30_CRC8_POLYNOMIAL
                else:
                    crc <<= 1
        return crc & 0xFF
