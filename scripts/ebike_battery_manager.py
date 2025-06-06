#!/usr/bin/python3

import asyncio
from kasa import Discover, SmartDevice
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
import logging
import argparse
from typing import Set, Union, ForwardRef, Dict, List, Optional
from os.path import isfile
from enum import Enum
import configparser
import traceback
from math import ceil
from dataclasses import dataclass
import atexit
import signal
import sys
import inspect
import bisect
from hilo_software_utilities.send_mail import send_file_email
from hilo_software_utilities.custom_logger import init_logging

# Constants
CLOSE_MISS_PCT = 0.05
CLOSE_MISS_MAX = 3
BATTERY_PREFIX = 'battery_'
RETRY_DELAY_SECS = 60 * 2
SETTLE_TIME_SECS = 30
PLUG_SETTLE_TIME_SECS = 10
COARSE_PROBE_INTERVAL_SECS = 10 * 60
FINE_PROBE_INTERVAL_SECS = 5 * 60
COARSE_PROBE_THRESHOLD_MARGIN = 20.0
MAX_CYCLES_IN_FINE_MODE = 20
MINIMUM_AMP_THRESHOLD_FOR_ACTIVE_CHARGE = 0.03
CONFIG_PLUGS_SECTION = 'Plugs'
CONFIG_STORAGE_SECTION = 'Storage'
CONFIG_FULL_CHARGE_SECTION = 'FullCharge'
DEFAULT_CONFIG_TAG = 'DEFAULT'
NOMINAL_START_THRESHOLD_TAG = 'nominal_charge_start_power_threshold'
NOMINAL_STOP_THRESHOLD_TAG = 'nominal_charge_stop_power_threshold'
FULL_CHARGE_THRESHOLD_TAG = 'full_charge_power_threshold'
ACTIVE_CHARGE_THRESHOLD_TAG = 'active_charge_power_threshold'
STORAGE_CHARGE_START_THRESHOLD_TAG = 'storage_charge_start_power_threshold'
STORAGE_CHARGE_STOP_THRESHOLD_TAG = 'storage_charge_stop_power_threshold'
STORAGE_CHARGE_CYCLE_LIMIT_TAG = 'storage_charge_cycle_limit'
COARSE_PROBE_THRESHOLD_MARGIN_TAG = 'coarse_probe_threshold_margin'
CHARGER_AMP_HOUR_RATE_TAG = 'charger_amp_hour_rate'
BATTERY_AMP_HOUR_CAPACITY_TAG = 'battery_amp_hour_capacity'
BATTERY_VOLTAGE_TAG = 'battery_voltage'
CHARGER_EFFICIENCY_TAG = "charger_efficiency"
INVESTIGATE_START_CURRENT_FILE = 'start_current_data.txt'
# Now experimenting with various thresholds.  For Rad 90W appears to end up at ~91%.
NOMINAL_CHARGE_START_THRESHOLD_DEFAULT = 90.0
NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT = 90.0
FULL_CHARGE_THRESHOLD_DEFAULT = 5.0
STORAGE_CHARGE_START_THRESHOLD_DEFAULT = 90.0
STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT = 90.0
STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT = 1
DEFAULT_LOG_FILE = 'ebike_battery_manager.log'
RETRY_LIMIT = 3
FULL_CHARGE_REPEAT_LIMIT = 3
PLUG_RETRY_SETUP_LIMIT = 3
MAX_RUNTIME_HOURS_DEFAULT = 12
DEFAULT_BATTERY_VOLTAGE = 48.0
CHARGER_EFFICIENCY = 0.75

# mandatory_config_manufacturer_tags = [FULL_CHARGE_THRESHOLD_TAG, COARSE_PROBE_THRESHOLD_MARGIN_TAG]
# one_of_config_manufacturer_threshold_tags = [NOMINAL_START_THRESHOLD_TAG, NOMINAL_STOP_THRESHOLD_TAG]
MANDATORY_CONFIG_MANUFACTURER_TAGS = [FULL_CHARGE_THRESHOLD_TAG, COARSE_PROBE_THRESHOLD_MARGIN_TAG]
ONE_OF_CONFIG_MANUFACTURER_TAGS = [NOMINAL_START_THRESHOLD_TAG, NOMINAL_STOP_THRESHOLD_TAG]

def fn_name():
    return inspect.currentframe().f_back.f_code.co_name

def sigint_handler(signal, frame):
    print("SIGINT received")
    sys.exit(0)


class BatteryManagerState:
    '''
    Singleton class to encapsulate global state

    Raises:
        BatteryPlugException: _description_
        BatteryPlugException: _description_
        BatteryPlugException: _description_
        BatteryPlugException: _description_
        AnalyzeException: _description_

    Returns:
        _type_: _description_
    '''
    _instance = None

    _full_charge_repeat_limit: int
    _fine_probe_interval_secs: int
    _probe_interval_secs: int
    _max_cycles_in_fine_mode: int
    _force_full_charge: bool
    _max_hours_to_run: int
    _storage_charge_cycle_limit: int
    _analyze_first_entry: bool
    _quiet_mode: bool
    _logging_mode: "LoggingMode"
    _default_config: "DeviceConfig"
    _device_config: Dict[str, "DeviceConfig"]
    _plug_manufacturer_map: Dict[str, str]
    _battery_plug_list: List[Union["BatteryPlug", "BatteryStripPlug"]]
    _plug_storage_list: List[str]
    _plug_full_charge_list: List[str]
    _active_plugs: Set["ActivePlug"]
    _scan_for_battery_prefix: bool
    _nominal_charge_start_power_threshold: float
    _nominal_charge_stop_power_threshold: float
    _full_charge_power_threshold: float
    _storage_charge_start_power_threshold: float
    _storage_charge_stop_power_threshold: float
    _log_file: str
    _debug_file_logger_active: bool

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._full_charge_repeat_limit = FULL_CHARGE_REPEAT_LIMIT
            cls._instance._fine_probe_interval_secs = FINE_PROBE_INTERVAL_SECS
            cls._instance._probe_interval_secs = COARSE_PROBE_INTERVAL_SECS
            cls._instance._max_cycles_in_fine_mode = MAX_CYCLES_IN_FINE_MODE
            cls._instance._force_full_charge = False
            cls._instance._max_hours_to_run = MAX_RUNTIME_HOURS_DEFAULT
            cls._instance._storage_charge_cycle_limit = STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT
            cls._instance._battery_plug_list = []
            cls._instance._device_config = {}
            cls._instance._plug_manufacturer_map = {}
            cls._instance._plug_storage_list = []
            cls._instance._plug_full_charge_list = []
            cls._instance._analyze_first_entry = True
            cls._instance._quiet_mode = False
            cls._instance._logging_mode = LoggingMode.SUPER_QUIET
            cls._instance._default_config = None
            cls._instance._active_plugs = set()
            cls._scan_for_battery_prefix = False
            cls._nominal_charge_start_power_threshold = NOMINAL_CHARGE_START_THRESHOLD_DEFAULT
            cls._nominal_charge_stop_power_threshold = NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT
            cls._full_charge_power_threshold = FULL_CHARGE_THRESHOLD_DEFAULT
            cls._storage_charge_start_power_threshold = STORAGE_CHARGE_START_THRESHOLD_DEFAULT
            cls._storage_charge_stop_power_threshold = STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT
            cls._log_file = DEFAULT_LOG_FILE
            cls._debug_file_logger_active = False
        return cls._instance

    @property
    def full_charge_repeat_limit(self) -> int:
        return self._full_charge_repeat_limit
    
    @full_charge_repeat_limit.setter
    def full_charge_repeat_limit(self, limit: int)  -> None:
        self._full_charge_repeat_limit = limit

    @property
    def fine_probe_interval_secs(self) -> int:
        return self._fine_probe_interval_secs
    
    @fine_probe_interval_secs.setter
    def fine_probe_interval_secs(self, seconds: int) -> None:
        self._fine_probe_interval_secs = seconds

    @property
    def probe_interval_secs(self) -> int:
        return self._probe_interval_secs
    
    @probe_interval_secs.setter
    def probe_interval_secs(self, seconds: int) -> None:
        self._probe_interval_secs = seconds

    @property
    def max_cycles_in_fine_mode(self) -> int:
        return self._max_cycles_in_fine_mode
    
    @max_cycles_in_fine_mode.setter
    def max_cycles_in_fine_mode(self, cycles: int) -> None:
        self._max_cycles_in_fine_mode = cycles

    @property
    def force_full_charge(self) -> bool:
        return self._force_full_charge
    
    @force_full_charge.setter
    def force_full_charge(self, force_full_charge: bool) -> None:
        self._force_full_charge = force_full_charge

    @property
    def max_hours_to_run(self) -> int:
        return self._max_hours_to_run
    
    @max_hours_to_run.setter
    def max_hours_to_run(self, hours: int) -> None:
        self._max_hours_to_run = hours

    @property
    def storage_charge_cycle_limit(self) -> int:
        return self._storage_charge_cycle_limit
    
    @storage_charge_cycle_limit.setter
    def storage_charge_cycle_limit(self, cycle_limit: int) -> None:
        self._storage_charge_cycle_limit = cycle_limit

    @property
    def analyze_first_entry(self) -> bool:
        return self._analyze_first_entry
    
    @analyze_first_entry.setter
    def analyze_first_entry(self, first: bool) -> None:
        self._analyze_first_entry = first

    @property
    def quiet_mode(self) -> bool:
        return self._quiet_mode
    
    @quiet_mode.setter
    def quiet_mode(self, _quiet_mode: bool) -> None:
        self._quiet_mode = _quiet_mode

    @property
    def logging_mode(self) -> "LoggingMode":
        return self._logging_mode
    
    @logging_mode.setter
    def logging_mode(self, _logging_mode: "LoggingMode") -> None:
        self._logging_mode = _logging_mode

    @property
    def default_config(self) -> "DeviceConfig":
        return self._default_config
    
    @default_config.setter
    def default_config(self, config: "DeviceConfig") -> None:
        self._default_config = config

    @property
    def device_config(self) -> Dict[str, "DeviceConfig"]:
        return self._device_config
    
    @device_config.setter
    def device_config(self, map: Dict[str, "DeviceConfig"]) -> None:
        self._device_config = map
    
    @property
    def plug_manufacturer_map(self) -> Dict[str, str]:
        return self._plug_manufacturer_map
    
    @plug_manufacturer_map.setter
    def plug_manufacturer_map(self, map: Dict[str, str]) -> None:
        self._plug_manufacturer_map = map
    
    @property
    def battery_plug_list(self) -> List[Union["BatteryPlug", "BatteryStripPlug"]]:
        return self._battery_plug_list

    @battery_plug_list.setter
    def battery_plug_list(self, list: List[Union["BatteryPlug", "BatteryStripPlug"]]) -> None:
        self._battery_plug_list = list
    
    @property
    def plug_storage_list(self) -> List[str]:
        return self._plug_storage_list

    @plug_storage_list.setter
    def plug_storage_list(self, list: List[str]) -> None:
        self._plug_storage_list = list

    @property
    def plug_full_charge_list(self) -> List[str]:
        return self._plug_full_charge_list

    @plug_full_charge_list.setter
    def plug_full_charge_list(self, list: List[str]) -> None:
        self._plug_full_charge_list = list    

    @property
    def active_plugs(self) -> Set["ActivePlug"]:
        return self._active_plugs

    @active_plugs.setter
    def active_plugs(self, plugs: Set["ActivePlug"]) -> None:
        self._active_plugs = plugs    

    @property
    def scan_for_battery_prefix(self) -> bool:
        return self._scan_for_battery_prefix
    
    @scan_for_battery_prefix.setter
    def scan_for_battery_prefix(self, _scan_for_battery_prefix) -> None:
        self._scan_for_battery_prefix = _scan_for_battery_prefix

    @property
    def nominal_charge_start_power_threshold(self) -> float:
        return self._nominal_charge_start_power_threshold
    
    @nominal_charge_start_power_threshold.setter
    def nominal_charge_start_power_threshold(self, _nominal_charge_start_power_threshold) -> None:
        self._nominal_charge_start_power_threshold = _nominal_charge_start_power_threshold

    @property
    def nominal_charge_stop_power_threshold(self) -> float:
        return self._nominal_charge_stop_power_threshold
    
    @nominal_charge_stop_power_threshold.setter
    def nominal_charge_stop_power_threshold(self, _nominal_charge_stop_power_threshold) -> None:
        self._nominal_charge_stop_power_threshold = _nominal_charge_stop_power_threshold

    @property
    def full_charge_power_threshold(self) -> float:
        return self._full_charge_power_threshold
    
    @full_charge_power_threshold.setter
    def full_charge_power_threshold(self, _full_charge_power_threshold) -> None:
        self._full_charge_power_threshold = _full_charge_power_threshold

    @property
    def storage_charge_start_power_threshold(self) -> float:
        return self._storage_charge_start_power_threshold
    
    @storage_charge_start_power_threshold.setter
    def storage_charge_start_power_threshold(self, _storage_charge_start_power_threshold) -> None:
        self._storage_charge_start_power_threshold = _storage_charge_start_power_threshold

    @property
    def storage_charge_stop_power_threshold(self) -> float:
        return self._storage_charge_stop_power_threshold
    
    @storage_charge_stop_power_threshold.setter
    def storage_charge_stop_power_threshold(self, _storage_charge_stop_power_threshold) -> None:
        self._storage_charge_stop_power_threshold = _storage_charge_stop_power_threshold

    @property
    def log_file(self) -> str:
        return self._log_file
    
    @log_file.setter
    def log_file(self, _log_file) -> None:
        self._log_file = _log_file

    @property
    def debug_file_logger_active(self) -> bool:
        return self._debug_file_logger_active
    
    @debug_file_logger_active.setter
    def debug_file_logger_active(self, _debug_file_logger_active: bool) -> None:
        self._debug_file_logger_active = _debug_file_logger_active


class CustomLogger(logging.Logger):
    '''
    _summary_ Custom logger for debugging, currently used in start_threshold_logger below
    Only logs to file and not console
    Logging level control is independent of the default logger

    Args:
        logging (_type_): _description_
    '''
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self.addHandler(logging.NullHandler())

class DebugLogger(CustomLogger):
    def __init__(self, name, level=logging.NOTSET, active: bool=False) -> None:
        super().__init__(name, level)
        self._active = active
        self._debug_logger = CustomLogger('start_threshold_logger')
        self._debug_logger_formatter = logging.Formatter('THRESHOLD: %(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self._debug_logger_file_handler = logging.FileHandler(INVESTIGATE_START_CURRENT_FILE)
        self._debug_logger_file_handler.setFormatter(self._debug_logger_formatter)
        self._debug_logger_file_handler.setLevel(level)
        self._debug_logger.addHandler(self._debug_logger_file_handler)
        self._debug_logger.setLevel(level)


    def info(self, msg: str) -> None:
        if self._active:
            self._debug_logger.info(msg)

    def error(self, msg: str) -> None:
        if self._active:
            self._debug_logger.error(msg)

# logging setup for special debug logger and normal logger
start_threshold_logger = None
logger = None

class ActivePlug():
    plug: "BatteryPlug"
    start_time: datetime
    stop_time: datetime = None

    def __init__(self, plug: "BatteryPlug", start_time: datetime):
        self.plug = plug
        self.start_time = start_time


class AnalyzeException(Exception):
    def __init__(self, msg: str):
        self.msg = msg


class BatteryPlugException(Exception):
    def __init__(self, msg:str) -> None:
        super().__init__(msg)
        self.msg = msg


class BatteryChargeMode(Enum):
    NOMINAL = 1
    FULL    = 2
    STORAGE = 3


class LoggingMode(Enum):
    SUPER_QUIET = 1
    QUIET       = 2
    VERBOSE     = 3
    NOISY       = 4


@dataclass
class DeviceConfig():
    '''
    Device/Manufacturer specific threshold values
    If the battery is linked to a manufacturer in the *.config file, it will
    charge based on the manufacturer specific values.
    If the battery has no associated manufacture profile, it will use the default profile
    Note: manufacturer specific values are determined experimentally and are NOT furnished by the manufacturer 
    '''
    manufacturer_name: str
    nominal_charge_start_power_threshold: float
    nominal_charge_stop_power_threshold: float
    full_charge_power_threshold: float
    storage_charge_start_power_threshold: float
    storage_charge_stop_power_threshold: float
    storage_charge_cycle_limit: int
    coarse_probe_threshold_margin: float
    charger_amp_hour_rate: float
    battery_amp_hour_capacity: float
    charger_max_hours_to_run: int
    battery_voltage: Optional[float] = DEFAULT_BATTERY_VOLTAGE
    charger_efficiency: Optional[float] = CHARGER_EFFICIENCY

    def __post_init__(self):
        if self.battery_voltage is None:
            self.battery_voltage = DEFAULT_BATTERY_VOLTAGE

def kw_h_to_amp_hours(kw_h: float, battery_voltage: float) -> float:
        watt_hours: float = kw_h * 1000
        amp_hours = watt_hours / battery_voltage
        return amp_hours


class BatteryPlug():
    '''
    This class supports the TP-Link KP115 Smart Plug
    '''
    name: str
    device: SmartDevice
    battery_found: bool
    charge_threshold_passed: bool
    charge_threshold_close_misses: int
    full_charge_repeat_count: int
    full_charge_repeat_limit: int
    max_cycles_in_fine_mode: int
    fine_mode_active: bool
    storage_charge_cycle_limit: int
    config: DeviceConfig
    battery_charge_mode: BatteryChargeMode
    battery_charge_start_time: datetime
    battery_charge_stop_time: datetime
    initial_amp_hours: float
    total_amp_hours: float

    def __init__(self, name: str, device: SmartDevice, max_cycles_in_fine_mode: int, config: DeviceConfig):
        self.name = name
        self.device = device
        self.battery_found = False
        self.charge_threshold_passed = False
        self.charge_threshold_close_misses = 0
        self.full_charge_repeat_count = 0
        self.full_charge_repeat_limit = FULL_CHARGE_REPEAT_LIMIT
        self.fine_mode_active = False
        self.storage_charge_cycle_limit = config.storage_charge_cycle_limit
        self.max_cycles_in_fine_mode = max_cycles_in_fine_mode
        self.config = config
        self.battery_charge_mode = BatteryChargeMode.NOMINAL
        self.battery_charge_start_time = datetime.now()
        self.battery_charge_stop_time = self.battery_charge_start_time + timedelta(hours=config.charger_max_hours_to_run)
        self.total_amp_hours = 0.0

    async def update(self) -> None:
        await self.device.update()

    async def reset_emeter_state(self) -> None:
        logger.info(f'{fn_name()}: {self.name}: today: {str(self.device.emeter_today)} kwH')
        self.initial_amp_hours = kw_h_to_amp_hours(self.device.emeter_today, self.config.battery_voltage)
        logger.info(f"BatteryPlug.{fn_name()}: {self.name}: initial_amp_hours: {str(self.initial_amp_hours)}")
        self.total_amp_hours = 0.0

    def get_power_total(self) -> float:
        amp_hours = kw_h_to_amp_hours(self.device.emeter_today, self.config.battery_voltage)
        # logger.error(f'{fn_name()}: kw_h: {str(self.device.emeter_today)}, amp_hours: {str(amp_hours)}')
        if self.initial_amp_hours < 0 or self.initial_amp_hours > amp_hours:
            self.initial_amp_hours = 0
        self.total_amp_hours = amp_hours - self.initial_amp_hours
        # logger.error(f"plug: {self.name}, actual amp hours: {self.total_amp_hours}, CHARGER_EFFICIENCY: {self.config.charger_efficiency}, estimated battery amp hours: {self.total_amp_hours * CHARGER_EFFICIENCY}")
        return self.total_amp_hours * self.config.charger_efficiency

    def get_power(self) -> float:
        '''
        Convert kw to watts

        Returns:
            float: power in watts
        '''
        power: float = self.device.emeter_realtime.power
        logger.info(f'{fn_name()}: {str(power)}')
        return power

    def is_on(self) -> bool:
        return self.device.is_on
    
    def is_time_expired(self, current_time: datetime) -> bool:
        return current_time > self.battery_charge_stop_time


    def get_full_charge_battery_power_threshold(self) -> float:
        return self.config.full_charge_power_threshold

    def get_nominal_charge_battery_power_threshold(self) -> float:
        return self.config.nominal_charge_stop_power_threshold

    def get_active_charge_battery_power_threshold(self) -> float:
        '''
        Returns:
            float: Appropriate power threshold the charger must drop below as a stopping condition
        '''
        match self.battery_charge_mode:
            case BatteryChargeMode.NOMINAL:
                return self.config.nominal_charge_stop_power_threshold
            case BatteryChargeMode.FULL:
                return self.config.full_charge_power_threshold
            case BatteryChargeMode.STORAGE:
                return self.config.storage_charge_stop_power_threshold

    def get_start_power_threshold(self) -> float:
        '''
        Returns the appropriate power threshold that the charger must draw in order
        to enter the repsective charge mode
        '''
        match self.battery_charge_mode:
            case BatteryChargeMode.NOMINAL:
                return self.config.nominal_charge_start_power_threshold
            case BatteryChargeMode.STORAGE:
                return self.config.storage_charge_start_power_threshold
            case BatteryChargeMode.FULL:
                return self.config.full_charge_power_threshold
                        
    def check_full_charge(self) -> bool:
        '''
        Checks and determines if we have reached a stopping point
        Handles both nominal and full charge cases
        In the nominal case, simply the class variable charge_threshold_passed is returned.
        In the full charge case, after charge_threshold_passed is True, we must then satisfy the 
        full_charge_repeat_limit constraint.

        Returns:
            bool: True if full charge is complete
        '''
        # logger.info(f'{self.name} - check_full_charge: battery_charge_mode: {str(self.battery_charge_mode)}, charge_threshold_passed: {str(self.charge_threshold_passed)}')
        if self.battery_charge_mode == BatteryChargeMode.FULL:
            if self.charge_threshold_passed:
                self.full_charge_repeat_count = self.full_charge_repeat_count + 1
                return self.full_charge_repeat_count == self.full_charge_repeat_limit
            else:
                if self.fine_mode_active:
                    self.max_cycles_in_fine_mode = self.max_cycles_in_fine_mode - 1
                    # logger.info(f'{self.name} - check_full_charge: plug.max_cycles_in_fine_mode: {str(self.max_cycles_in_fine_mode)}')
                    return self.max_cycles_in_fine_mode <= 0
        return self.charge_threshold_passed

    def check_storage_mode(self) -> bool:
        '''
        returns True if a plug's battery is in storage mode AND it's cycle limit has counted down to 0
        '''
        # logger.info(f'check_storage_mode: ENTRY: battery_charge_mode: {str(self.battery_charge_mode)}, cycle_limit: {str(self.get_storage_charge_cycle_limit())}')
        if self.battery_charge_mode == BatteryChargeMode.STORAGE:
            logger.info(
                f'check_storage_mode: plug.get_storage_charge_cycle_limit(): {str(self.get_storage_charge_cycle_limit())}')
            if self.get_and_decrement_storage_charge_cycle_limit() == 0:
                self.charge_threshold_passed = True
                # logger.info(f'check_storage_mode: return True')
                return True
            else:
                # logger.info(f'check_storage_mode: return False')
                pass

        return False
    
    def start_threshold_check(self, device_power_consumption: float) -> bool:
        '''
        Logic that should be satisfied to allow a battery/charger pair to start charging

        Args:
            device_power_consumption (float): _description_

        Returns:
            bool: _description_
        '''
        if self.battery_charge_mode == BatteryChargeMode.FULL:
            return True
        return device_power_consumption > self.get_start_power_threshold()

    def stop_threshold_check(self, device_power_consumption: float) -> bool:
        '''
        Checks internal battery thresholds based on BatteryChargeMode and returns True if the stop threshold criteria is passed

        Args:
            device_power_consumption (float): _description_

        Returns:
            bool: _description_
        '''
        # Once we pass, we always pass
        if self.charge_threshold_passed:
            return True
        if self.battery_charge_mode == BatteryChargeMode.FULL:
            approximate_threshold = self.get_active_charge_battery_power_threshold(
            ) + (self.get_active_charge_battery_power_threshold() * CLOSE_MISS_PCT)
            if device_power_consumption < approximate_threshold:
                self.charge_threshold_close_misses = self.charge_threshold_close_misses + 1
            self.charge_threshold_passed = self.charge_threshold_close_misses > CLOSE_MISS_MAX
            return self.charge_threshold_passed
        if device_power_consumption < self.get_active_charge_battery_power_threshold():
            self.charge_threshold_passed = True
            return True
        return False

    def get_coarse_probe_threshold(self) -> float:
        '''
        Returns the computed coarse_probe_threshold based on the battery_charge_mode

        Returns:
            float: computed coarse_probe_threshold
        '''
        match self.battery_charge_mode:
            case BatteryChargeMode.NOMINAL:
                return self.config.nominal_charge_stop_power_threshold + self.config.coarse_probe_threshold_margin
            case BatteryChargeMode.FULL:
                return self.config.full_charge_power_threshold + self.config.coarse_probe_threshold_margin
            case BatteryChargeMode.STORAGE:
                return self.config.storage_charge_stop_power_threshold + self.config.coarse_probe_threshold_margin

    def set_battery_charge_mode(self, mode: BatteryChargeMode):
        self.battery_charge_mode = mode

    def get_storage_charge_cycle_limit(self) -> int:
        return self.storage_charge_cycle_limit

    def get_and_decrement_storage_charge_cycle_limit(self) -> Union[int, BatteryPlugException]:
        '''
        Returns the current_storage_charge_cycle_limit count and
        side-effects the storage_charge_cycle_limit by decrementing on each call
        This effects a countdown function to encapsulate the two actions of accessing
        the count and then decrementing it if > 0.

        Returns:
            int: current countdown as it approaches 0
        '''
        current_storage_charge_cycle_limit = self.storage_charge_cycle_limit
        if self.storage_charge_cycle_limit > 0:
            self.storage_charge_cycle_limit = self.storage_charge_cycle_limit - 1
        return current_storage_charge_cycle_limit

    async def turn_on(self) -> Union[None, BatteryPlugException]:
        await self.device.turn_on()
        await self.device.update()
        if not self.device.is_on:
            logger.error(f"FATAL ERROR, unable to turn on plug: {self.name}")
            raise BatteryPlugException(
                f'FATAL ERROR, unable to turn on plug: {self.name}')

    async def turn_off(self) -> Union[None, BatteryPlugException]:
        await self.device.turn_off()
        await self.device.update()
        if not self.device.is_off:
            logger.error(f"FATAL ERROR, unable to turn off plug: {self.name}")
            raise BatteryPlugException(
                f'FATAL ERROR, unable to turn off plug: {self.name}')

    def get_device(self) -> SmartDevice:
        return self.device
    

class BatteryStripPlug(BatteryPlug):
    '''
    This class subclasses BatteryPlug and supports the TP-Link HS300 SmartStrip plugs
    '''
    plug_index: int

    def __init__(self, name: str, device: SmartDevice, plug_index: int, max_cycles_in_fine_mode: int, thresholds: DeviceConfig):
        super().__init__(name, device, max_cycles_in_fine_mode, thresholds)
        self.plug_index = plug_index

    async def reset_emeter_state(self) -> None:
        logger.info(f'BatteryStripPlug.{fn_name()}: {self.name}: ENTRY')
        child_plug = self.device.children[self.plug_index]
        # await child_plug.erase_emeter_stats()
        logger.info(f'BatteryStripPlug.{fn_name()}: {self.name}: today: {str(child_plug.emeter_today)} kwH')
        self.initial_amp_hours = kw_h_to_amp_hours(child_plug.emeter_today, self.config.battery_voltage)
        logger.info(f"BatteryStripPlug.{fn_name()}: {self.name}: initial_amp_hours: {str(self.initial_amp_hours)}")
        self.total_amp_hours = 0.0
        logger.info(f'BatteryStripPlug.{fn_name()}: {self.name}: EXIT')

    def get_power_total(self) -> float:
        child_plug = self.device.children[self.plug_index]
        amp_hours = kw_h_to_amp_hours(child_plug.emeter_today, self.config.battery_voltage)
        # logger.error(f'{fn_name()}: kw_h: {str(child_plug.emeter_today)}, amp_hours: {str(amp_hours)}')
        if self.initial_amp_hours < 0 or self.initial_amp_hours > amp_hours:
            self.initial_amp_hours = 0
        self.total_amp_hours = amp_hours - self.initial_amp_hours
        # logger.error(f"plug: {self.name}, actual amp hours: {self.total_amp_hours}, CHARGER_EFFICIENCY: {self.config.charger_efficiency}, estimated battery amp hours: {self.total_amp_hours * CHARGER_EFFICIENCY}")
        return self.total_amp_hours * self.config.charger_efficiency

    def get_power(self) -> float:
        '''
        Retrieve power usage from device

        Returns:
            float: power in watts
        '''
        child_plug = self.device.children[self.plug_index]
        power: float = child_plug.emeter_realtime.power
        logger.info(f'BatteryStripPlug.get_power: {str(power)}')
        return power

    def is_on(self) -> bool:
        child_plug = self.device.children[self.plug_index]
        return child_plug.is_on

    async def turn_on(self) -> Union[None, BatteryPlugException]:
        child_plug = self.device.children[self.plug_index]
        await child_plug.turn_on()
        await self.update()
        if not child_plug.is_on:
            logger.error(
                f"FATAL ERROR, unable to turn on plug: {child_plug.name}")
            raise BatteryPlugException(
                f'FATAL ERROR, unable to turn on plug: {child_plug.name}')

    async def turn_off(self) -> Union[None, BatteryPlugException]:
        child_plug = self.device.children[self.plug_index]
        await child_plug.turn_off()
        await self.update()
        if not child_plug.is_off:
            logger.error(
                f"FATAL ERROR, unable to turn off plug: {child_plug.name}")
            raise BatteryPlugException(
                f'FATAL ERROR, unable to turn off plug: {child_plug.name}')


def init_argparse() -> argparse.ArgumentParser:
    '''
    Initializes ArgumentParser for command line args when the script
    is used in that manner.

    Returns:
        argparse.ArgumentParser: initialized argparse
    '''
    parser = argparse.ArgumentParser(
        usage='%(prog)s [OPTIONS]',
        description='Manage EBike battery charging with TP-Link smart socket(s)'
    )
    parser.add_argument(
        '-v', '--version', action='version',
        version=f'{parser.prog} version 1.0.0'
    )
    parser.add_argument(
        "-e", "--email", metavar='',
        help='email address to send reports to'
    )
    parser.add_argument(
        '-a', '--app_key', metavar='',
        help='Google app key needed to allow sending mail reports [gmail only]'
    )
    parser.add_argument(
        '-f', '--force_full_charge',
        action='store_true',
        help='forces all batteries into full charge mode'
    )
    parser.add_argument(
        '-t', '--test_mode',
        action='store_true',
        help='test mode only, verify early stages, no real plug activity'
    )
    parser.add_argument(
        '-l', '--log_file_name', metavar='',
        help='overrides logfile name, default is battery_plug_controller.log'
    )
    parser.add_argument(
        '-c', '--config_file', metavar='',
        help='optional config file, useful to support multiple manufacturers, overrides default values'
    )
    parser.add_argument(
        '-q', '--quiet_mode',
        action='store_true',
        help='reduces logging'
    )
    parser.add_argument(
        '--nominal_start_charge_threshold', metavar='',
        help='set the default start threshold power override for nominal charge start'
    )
    parser.add_argument(
        '--nominal_charge_cutoff', metavar='',
        help='set the default cutoff power override for nominal charge complete'
    )
    parser.add_argument(
        '--full_charge_repeat_limit', metavar='',
        help='number of cycles to repeat after attaining full charge'
    )
    parser.add_argument(
        '--max_cycles_in_fine_mode', metavar='',
        help='max limit of cycles to prevent forever charge'
    )
    parser.add_argument(
        '--full_charge_cutoff', metavar='',
        help='set the full power override for full charge complete'
    )
    parser.add_argument(
        '--storage_start_charge_threshold', metavar='',
        help='set the storage threshold power override for storage charge start'
    )
    parser.add_argument(
        '--storage_charge_cutoff', metavar='',
        help='set the storage power override for storage charge complete'
    )
    parser.add_argument(
        '--storage_charge_cycle_limit', metavar='',
        help='max cycles to charge in storage charge mode, default is 1'
    )
    parser.add_argument(
        '--max_hours_to_run', metavar='',
        help='maximum time to run the script in hours'
    )
    parser.add_argument(
        '--scan_for_battery_prefix',
        action='store_true',
        help='enables auto scan for any plugs with a battery_ prefix'
    )
    return parser


def create_battery_plug(plug_name: str, smart_device: SmartDevice) -> BatteryPlug:
    '''
    Create an instance of a BatteryPlug

    Args:
        plug_name (str): 
        smart_device (SmartDevice): Base class of TP-Link kasa device, in this case SmartPlug superclass

    Returns:
        BatteryPlug: The BatteryPlug instance will have the appropriate BatteryChargeMode set
    '''
    plug_full_charge_list = BatteryManagerState().plug_full_charge_list
    plug_storage_list = BatteryManagerState().plug_storage_list
    plug: BatteryPlug = BatteryPlug(
        plug_name, smart_device, BatteryManagerState().max_cycles_in_fine_mode, get_device_config(plug_name))
    if plug_name in plug_storage_list:
        plug.set_battery_charge_mode(BatteryChargeMode.STORAGE)
    elif plug_name in plug_full_charge_list:
        plug.set_battery_charge_mode(BatteryChargeMode.FULL)
    else:
        plug.set_battery_charge_mode(
            BatteryChargeMode.FULL if BatteryManagerState().force_full_charge else BatteryChargeMode.NOMINAL)
    return plug


def create_battery_strip_plug(plug_name: str, smart_device: SmartDevice, index: int) -> BatteryStripPlug:
    '''
    Create an instance of a BatteryStripPlug

    Args:
        plug_name (str): 
        smart_device (SmartDevice): Base class of TP-Link kasa device, in this case SmartPlug superclass
        index (int): index of the child plug in the strip

    Returns:
        BatteryStripPlug: The BatteryStripPlug instance will have the appropriate BatteryChargeMode set
    '''
    plug_full_charge_list = BatteryManagerState().plug_full_charge_list
    plug_storage_list = BatteryManagerState().plug_storage_list
    plug: BatteryStripPlug = BatteryStripPlug(
        plug_name, smart_device, index, BatteryManagerState().max_cycles_in_fine_mode, get_device_config(plug_name))
    if plug_name in plug_storage_list:
        plug.set_battery_charge_mode(BatteryChargeMode.STORAGE)
    elif plug_name in plug_full_charge_list:
        plug.set_battery_charge_mode(BatteryChargeMode.FULL)
    else:
        plug.set_battery_charge_mode(
            BatteryChargeMode.FULL if BatteryManagerState().force_full_charge else BatteryChargeMode.NOMINAL)
    return plug


async def update_strip_plug(plug, smart_device, index) -> BatteryStripPlug:
    strip_plug = create_battery_strip_plug(plug.alias, smart_device, index)
    logger.info(
        f'SmartStrip: plug: {plug.alias}, battery_charge_mode: {str(strip_plug.battery_charge_mode)}')
    await strip_plug.update()
    logger.info(f'SmartStrip: plug: {plug.alias}, update() ok')
    return strip_plug


async def update_battery_plug_list(smart_device: SmartDevice, manufacturer_plug_names: dict) -> None:
    '''
    Finds plug depending on if the plug is singular or part of a battery strip.
    Create the appropriate BatteryPlug or BatteryStripPlug and append to the global battery_plug_list
    Compute indexes in battery strip mode

    Args:
        smart_device (SmartDevice): Can be either a plug or a strip of plugs
        manufacturer_plug_names (dict): _description_
    '''
    battery_plug_list = BatteryManagerState().battery_plug_list
    if smart_device.is_plug:
        logger.info(f'init: found a SmartPlug: {smart_device.alias}')
        if (
            BatteryManagerState().scan_for_battery_prefix and BATTERY_PREFIX in smart_device.alias
        ) or (
            smart_device.alias in manufacturer_plug_names
        ):
            plug = create_battery_plug(smart_device.alias, smart_device)
            logger.info(
                f'SmartPlug: {smart_device.alias}, battery_charge_mode: {str(plug.battery_charge_mode)}')
            battery_plug_list.append(plug)
            return
    if smart_device.is_strip:
        logger.info(
            f'init: found a SmartStrip: {smart_device.alias}, children: {str(len(smart_device.children))}')
        tasks = []
        for index, plug in enumerate(smart_device.children):
            if (
                BatteryManagerState().scan_for_battery_prefix and BATTERY_PREFIX in plug.alias
            ) or (
                plug.alias in manufacturer_plug_names
            ):
                tasks.append(update_strip_plug(plug, smart_device, index))
        updated_plugs = await asyncio.gather(*tasks)
        battery_plug_list.extend(updated_plugs)


async def init() -> int:
    '''
    async function.  Uses kasa library to discover all devices.
    Then we call update_battery_plug_list to extract all valid ebike battery plugs

    Returns:
        int: number of ebike battery plugs discovered
    '''
    battery_plug_list = BatteryManagerState().battery_plug_list
    found = await Discover.discover()
    force_log(f'>>>>> init <<<<<')
    # Handle all plug names in config file CONFIG_PLUGS_SECTION.  These do not have to have a BATTERY_PREFIX
    manufacturer_plug_names = BatteryManagerState().plug_manufacturer_map.keys()
    for smart_device in found.values():
        await smart_device.update()
        await update_battery_plug_list(smart_device, manufacturer_plug_names)
    battery_count = len(battery_plug_list)
    if battery_count == 0:
        logger.warning(
            f'>>>>> init <<<<< -- EMPTY battery_plug_list + DEBUG -- devices found: {str(found)}')
        logger.warning(
            f'>>>>> init <<<<< -- If this error persists, please restart the TP-Link power strip or plugs to reset them')
    return battery_count


async def setup() -> None:
    '''
    async function.  Updates devices with kasa library to get valid data into each SmartDevice instance
    Scan plugs and make sure all are on at exit

    '''
    battery_plug_list = BatteryManagerState().battery_plug_list
    force_log('>>>>> setup ENTRY')
    for plug in battery_plug_list:
        await plug.update()
        await asyncio.sleep(PLUG_SETTLE_TIME_SECS)
        await plug.reset_emeter_state()
        logger.info('>>>>> setup after reset_emeter_state()')
        plug_retry_setup_ct: int = 0
        while plug_retry_setup_ct < PLUG_RETRY_SETUP_LIMIT:
            logger.info(f'>>>>> setup plug: {plug.name}')
            if not plug.is_on():
                await plug.turn_on()
                await asyncio.sleep(5)
                await plug.update()
                device_power_consumption = plug.get_power()
                if device_power_consumption > 0:
                    logger.info(
                        f'>>>>> setup plug: {plug.name} is using power: {device_power_consumption}')
                    break
                else:
                    # might not have started correctly, retry
                    # It might be ok if no charger
                    plug_retry_setup_ct += 1
                    await plug.turn_off()
                    await asyncio.sleep(2)
                    await plug.update()
            else:
                await plug.update()
                device_power_consumption = plug.get_power()
                if device_power_consumption > 0:
                    logger.info(
                        f'>>>>> setup plug: {plug.name} is using power: {device_power_consumption}')
                    break
                else:
                    logger.info(
                        f'>>>>> setup plug: {plug.name} is NOT using power: {device_power_consumption}')
                    plug_retry_setup_ct += 1
                    await plug.turn_off()
                    await asyncio.sleep(2)
                    await plug.update()

        if plug_retry_setup_ct == PLUG_RETRY_SETUP_LIMIT:
            logger.warning(
                f'!!!!! WARNING !!!!!, no power usage on plug: {plug.name}')
        else:
            logger.info(
                f'>>>>> setup -- plug: {plug.name} appears active, retries: {plug_retry_setup_ct}')

    logger.info('>>>>> setup EXIT')


def delete_plugs(battery_plug_list: list, plugs_to_delete: list) -> None:
    '''
    Helper function to delete a list of plugs from global battery_plug_list

    Args:
        plugs_to_delete (list): plugs that need to be removed from global battery_plug_list
    '''
    # logger.info(f"delete_plugs number to delete: {len(battery_plug_list)}")
    for plug in plugs_to_delete:
        try:
            battery_plug_list.remove(plug)
            stop_active_plug(plug.name)
        except ValueError as e:
            logger.warning(
                f'WARNING: plug: {plug.name} is not in battery_plug_list, exception: {str(e)}')
        except Exception as e:
            logger.warning(
                f'ERROR: plug: {plug.name} had an unexpected exception: {str(e)}')


def set_active_plug(battery_plug: BatteryPlug) -> None:
    active_plugs: Set[ActivePlug] = BatteryManagerState().active_plugs
    if not any(battery_plug.name == plug.plug.name for plug in active_plugs):
        active_plugs.add(ActivePlug(
            plug=battery_plug, start_time=datetime.now()))


def stop_active_plug(plug_name: str) -> None:
    active_plugs: Set[ActivePlug] = BatteryManagerState().active_plugs
    active_plug: ActivePlug = next(
        (x for x in active_plugs if x.plug.name == plug_name), None)
    if active_plug:
        active_plug.stop_time = datetime.now()


async def analyze() -> bool:
    '''
    async function
    Performs a single pass analysis of power levels
    Called periodically from analyze_loop

    Returns:
        bool: True if we are actively charging at the exit of this function
    '''
    global start_threshold_logger
    active_plugs: Set[ActivePlug] = BatteryManagerState().active_plugs
    battery_plug_list = BatteryManagerState().battery_plug_list

    probe_interval_secs = BatteryManagerState().probe_interval_secs

    logger.info(
        f'>>>>> analyze --> probe_interval_secs: {str(probe_interval_secs)}, analyze_first_entry: {str(BatteryManagerState().analyze_first_entry)} <<<<<')
    actively_charging = False

    def set_actively_charging(plug: BatteryPlug) -> None:
        # logger.error(
        #     f'!!!! DEBUG: set_actively_charging(): plug: {str(plug.name)}')
        nonlocal actively_charging
        actively_charging = True
        logger.info(f'{plug.name} is actively_charging')
        set_active_plug(plug)

    # track next_probe_interval_secs starting at COARSE_PROBE_INTERVAL_SECS to handle the case
    # where we dropped into a fine_probe_interval_secs for one battery and that battery finished
    # but the remaining battery is still in the range for COARSE_PROBE_INTERVAL_SECS
    # At the end of the loop, check next_probe_interval_secs against probe_interval_secs
    fine_probe_interval_secs: int = BatteryManagerState().fine_probe_interval_secs
    next_probe_interval_secs = COARSE_PROBE_INTERVAL_SECS
    plugs_to_delete = []

    async def turn_off_and_delete_plug(plug) -> None:
        plug.get_power_total()
        await plug.turn_off()
        plugs_to_delete.append(plug)


    for plug in battery_plug_list:
        plug_name = plug.name
        await plug.update()

        if not plug.is_on():
            logger.info(plug_name + ' is OFF')
            plugs_to_delete.append(plug)
            continue

        # check if plug's time is expired
        if plug.is_time_expired(datetime.now()):
            logger.info(plug_name + ' time expired')
            plugs_to_delete.append(plug)
            continue

        device_power_consumption = plug.get_power()
        logger.info(plug_name + ': ' + str(device_power_consumption))
        if BatteryManagerState().analyze_first_entry:
            start_threshold_logger.info(
                plug_name + ': ' + str(device_power_consumption))
            if not plug.start_threshold_check(device_power_consumption):
                start_threshold_logger.info(
                    f'!!!! DEBUG: analyze(): LOOP - start_threshold_check() is False, plug: {str(plug_name)}, power: {str(device_power_consumption)}')
                await turn_off_and_delete_plug(plug)
                continue
            else:
                start_threshold_logger.info(
                    f'!!!! DEBUG: analyze(): LOOP - start_threshold_check() is True, plug: {str(plug_name)}, power: {str(device_power_consumption)}')

        if plug.stop_threshold_check(device_power_consumption):
            turn_off_plug = plug.check_full_charge() or plug.check_storage_mode()
            if turn_off_plug:
                logger.info(
                    f'{plug_name}: (stop_threshold_check) has no battery present or it may be fully charged: {str(device_power_consumption)}')
                await turn_off_and_delete_plug(plug)
                continue
            plug.fine_mode_active = True
            next_probe_interval_secs = fine_probe_interval_secs
            set_actively_charging(plug)
            continue

        # By here check if we should switch to fine_probe_interval to detect charged state sooner
        if not plug.fine_mode_active and next_probe_interval_secs > BatteryManagerState().fine_probe_interval_secs and device_power_consumption < plug.get_coarse_probe_threshold():
            plug.fine_mode_active = True
            logger.info(
                f'{plug_name}: fine probe interval ({str(fine_probe_interval_secs)}) secs is now ON')

        if plug.fine_mode_active:
            next_probe_interval_secs = fine_probe_interval_secs
            # Must handle additional case of trying for full charge cycle, we may NEVER reach the active_charge_power_threshold
            if plug.check_full_charge():
                logger.info(
                    f'{plug_name}: is done with a full charge cycle at: {str(device_power_consumption)}')
                await turn_off_and_delete_plug(plug)
                continue

        set_actively_charging(plug)

    BatteryManagerState().analyze_first_entry = False
    delete_plugs(battery_plug_list, plugs_to_delete)

    if actively_charging and (probe_interval_secs != next_probe_interval_secs):
        logger.info(
            f'Switch to probe_interval_secs: {str(next_probe_interval_secs)} from: {str(probe_interval_secs)}')
        BatteryManagerState().probe_interval_secs = next_probe_interval_secs
    return actively_charging


async def analyze_loop(final_stop_time: datetime) -> Union[bool, AnalyzeException]:
    '''
    async function.  Encapsulates all downstream async functions.
    This is the main loop control, also does the initialization and setup prior to looping
    calls analyze to probe battery states each time activated in loop, then sleeps 
    for a number of seconds between activations


    Args:
        final_stop_time (datetime): Final watchdog to stop in case we are out of control due to unforeseen conditions

    Raises:
        AnalyzeException: Error condition.  This is caught internally.

    Returns:
        bool: Normal exit indicating success or an AnalyzeException
    '''
    probe_interval_secs: int = BatteryManagerState().probe_interval_secs
    battery_plug_list = BatteryManagerState().battery_plug_list

    retry_limit = RETRY_LIMIT
    init_complete = False
    success = False
    logger.info(f'analyze_loop: START')
    while not success and retry_limit > 0:
        exception_occurred = False
        logger.info(f'analyze_loop: LOOP TOP: success: {success}, retry_limit: {retry_limit}')
        # check absolute stop limit
        if datetime.now() > final_stop_time:
            logger.error(
                f"max runtime {BatteryManagerState().max_hours_to_run} hours exceeded, exit analyze_loop")
            break
        try:
            if not init_complete:
                battery_plug_ct = await init()
                if battery_plug_ct == 0:
                    logger.error("unexpectedly empty battery_plug_list")
                    raise AnalyzeException('ERROR, unexpectedly empty battery_plug_list')
                else:
                    init_complete = True
                    logger.info(
                        f'SUCCESSFULLY found: {str(battery_plug_ct)} smart battery plugs')

            await asyncio.sleep(SETTLE_TIME_SECS)
            await setup()
            await asyncio.sleep(SETTLE_TIME_SECS)
            charging = True
            while charging:
                charging = await analyze()
                if charging:
                    await asyncio.sleep(probe_interval_secs)
            success = True
        except AnalyzeException as e:
            exception_occurred = True
            logger.error(
                f'!!!!!>>>>> ERROR in Execution e: {str(e)}<<<<<!!!!!')
            if len(battery_plug_list) > 0:
                logger.error(
                    '!!!!!>>>>> ERROR Attempting shutdown_plugs <<<<<!!!!!')
                await shutdown_plugs()
        except BatteryPlugException as e:
            exception_occurred = True
            logger.error(
                f'!!!!!>>>>> ERROR ERROR ERROR ERROR BatteryPlugException: {e} <<<<<!!!!!')
        except Exception as e:
            exception_occurred = True
            logger.error(
                f'!!!!!>>>>> ERROR ERROR ERROR ERROR Unexpected Exception: {e} <<<<<!!!!!')
        finally:
            if exception_occurred:
                retry_limit = retry_limit - 1
                traceback_str = traceback.format_exc()
                logger.error(
                    f'!!!!!>>>>> ERROR finally: retry_limit: {retry_limit}, traceback: {traceback_str} <<<<<!!!!!')
                if retry_limit > 0:
                    await asyncio.sleep(RETRY_DELAY_SECS)

    return success


async def shutdown_plugs() -> None:
    '''
    Cleans up plugs when an error state is reached.
    Not part of the normal shutdown
    '''
    battery_plug_list = BatteryManagerState().battery_plug_list
    logger.info(f'>>>>> {fn_name()} ENTRY: battery_plug_list: {len(battery_plug_list)} <<<<<')
    try:
        plugs_to_delete = []
        for plug in battery_plug_list:
            await plug.update()
            await plug.turn_off()
            plugs_to_delete.append(plug)
    except BatteryPlugException as e:
        logger.error(f'FATAL ERROR: {fn_name()}: {str(e)}')
        logger.error(
            'FATAL ERROR: Unable to shutdown plugs, check plug status manually')
        return
    except Exception as e:
        logger.error(f'FATAL ERROR: {fn_name()}:Unexpected Exception in shutdown_plugs: {str(e)}')
        logger.error(
            f'FATAL ERROR: {fn_name()}:Unable to shutdown plugs, check plug status manually')
        return
    finally:      
        delete_plugs(battery_plug_list, plugs_to_delete)
        # We expect battery_plug_list to be empty at this point
        if len(battery_plug_list) > 0:
            logger.error(f'UNEXPECTED, {fn_name()}:battery_plug_list not empty: {len(battery_plug_list)}')
            battery_plug_list.clear()
        logger.info(f'>>>>> {fn_name()}: EXIT <<<<<')


def get_device_config(plug_name: str) -> DeviceConfig:
    '''
    Retrieves a DeviceConfig class from device_config with the following priority
    1. if the plug_name is found in device_config => use the appropriate manufacturer value
    2. if the plug_name is NOT found => use DEFAULT
    3. if the plug_name manufacturer is missing => DEFAULT
    Note, device_config must always have a DEFAULT_CONFIG_TAG tag
    '''
    plug_manufacturer_map = BatteryManagerState().plug_manufacturer_map
    device_config = BatteryManagerState().device_config
    if plug_name in plug_manufacturer_map:
        manufacturer = plug_manufacturer_map[plug_name]
        return device_config[manufacturer]
    return device_config[DEFAULT_CONFIG_TAG]


def check_required_config_strings(config, required_tags: list, one_of_option_tag: list) -> bool:
    for string in required_tags:
        if string not in config:
            return False
    if one_of_option_tag is None or len(one_of_option_tag) == 0:
        return True
    found_one_of_tag = False
    for string in one_of_option_tag:
        if string in config:
            found_one_of_tag = True
            break
    return found_one_of_tag


def verify_config_file(config_file_name: str) -> bool:
    '''
    fails if there is a config file and the [PLUGS] section has a manufacturer that is not in the file
    plug fails will use the DEFAULT thresholds
    On completion, the device_config dict will be filled in as much as possible except for the DEFAULT entry

    Args:
        config_file_name (str): name of full path to a config file

    Returns:
        bool: Normal exit indicating success in parsing the config file
    '''
    plug_full_charge_list = BatteryManagerState().plug_full_charge_list
    plug_manufacturer_map = BatteryManagerState().plug_manufacturer_map
    device_config = BatteryManagerState().device_config
    plug_storage_list = BatteryManagerState().plug_storage_list
    try:
        verified = True
        if isfile(config_file_name):
            logger.info(f'>>>>> FOUND config_file: {config_file_name}')
            config_parser = configparser.ConfigParser(allow_no_value=True)
            config_parser.read(config_file_name)
            manufacturers = list(config_parser.keys())
            if CONFIG_PLUGS_SECTION in manufacturers:
                manufacturers.remove(CONFIG_PLUGS_SECTION)
            if CONFIG_STORAGE_SECTION in manufacturers:
                manufacturers.remove(CONFIG_STORAGE_SECTION)
            if CONFIG_FULL_CHARGE_SECTION in manufacturers:
                manufacturers.remove(CONFIG_FULL_CHARGE_SECTION)
            # Extract manufacture specific DeviceConfig here
            for manufacturer in manufacturers:
                #  valid manufacturer, validate the mandatory_config_manufacturer_tags
                if check_required_config_strings(config_parser[manufacturer], MANDATORY_CONFIG_MANUFACTURER_TAGS, ONE_OF_CONFIG_MANUFACTURER_TAGS):
                    if NOMINAL_START_THRESHOLD_TAG in config_parser[manufacturer]:
                        nominal_charge_start_power_threshold = float(
                            config_parser[manufacturer][NOMINAL_START_THRESHOLD_TAG])
                        if NOMINAL_STOP_THRESHOLD_TAG in config_parser[manufacturer]:
                            nominal_charge_stop_power_threshold = float(
                                config_parser[manufacturer][NOMINAL_STOP_THRESHOLD_TAG])
                        else:
                            nominal_charge_stop_power_threshold = nominal_charge_start_power_threshold
                    elif NOMINAL_STOP_THRESHOLD_TAG in config_parser[manufacturer]:
                        nominal_charge_stop_power_threshold = float(
                            config_parser[manufacturer][NOMINAL_STOP_THRESHOLD_TAG])
                        nominal_charge_start_power_threshold = nominal_charge_stop_power_threshold
                    else:
                        nominal_charge_start_power_threshold = NOMINAL_CHARGE_START_THRESHOLD_DEFAULT
                        nominal_charge_stop_power_threshold = NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT
                    if STORAGE_CHARGE_STOP_THRESHOLD_TAG in config_parser[manufacturer]:
                        storage_charge_stop_power_threshold = float(
                            config_parser[manufacturer][STORAGE_CHARGE_STOP_THRESHOLD_TAG])
                    else:
                        storage_charge_stop_power_threshold = STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT
                    if STORAGE_CHARGE_START_THRESHOLD_TAG in config_parser[manufacturer]:
                        storage_charge_start_power_threshold = float(
                            config_parser[manufacturer][STORAGE_CHARGE_START_THRESHOLD_TAG])
                    else:
                        storage_charge_start_power_threshold = storage_charge_stop_power_threshold
                    if STORAGE_CHARGE_CYCLE_LIMIT_TAG in config_parser[manufacturer]:
                        storage_charge_cycle_limit = int(
                            config_parser[manufacturer][STORAGE_CHARGE_CYCLE_LIMIT_TAG])
                    else:
                        storage_charge_cycle_limit = STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT
                    charger_amp_hour_rate = float(
                        config_parser[manufacturer][CHARGER_AMP_HOUR_RATE_TAG]) if CHARGER_AMP_HOUR_RATE_TAG in config_parser[manufacturer] else 0.0
                    battery_amp_hour_capacity = float(
                        config_parser[manufacturer][BATTERY_AMP_HOUR_CAPACITY_TAG]) if BATTERY_AMP_HOUR_CAPACITY_TAG in config_parser[manufacturer] else 0.0
                    charger_max_hours_to_run = ceil(
                        battery_amp_hour_capacity / charger_amp_hour_rate) if charger_amp_hour_rate > 0.0 and battery_amp_hour_capacity > 0.0 else BatteryManagerState().max_hours_to_run
                    battery_voltage = float(
                        config_parser[manufacturer][BATTERY_VOLTAGE_TAG]) if BATTERY_VOLTAGE_TAG in config_parser[manufacturer] else None
                    charger_efficiency = float(
                        config_parser[manufacturer][CHARGER_EFFICIENCY_TAG]) if CHARGER_EFFICIENCY_TAG in config_parser[manufacturer] else CHARGER_EFFICIENCY
                    device_config[manufacturer] = DeviceConfig(manufacturer,
                                                                       nominal_charge_start_power_threshold,
                                                                       nominal_charge_stop_power_threshold,
                                                                       float(
                                                                           config_parser[manufacturer][FULL_CHARGE_THRESHOLD_TAG]),
                                                                       storage_charge_start_power_threshold,
                                                                       storage_charge_stop_power_threshold,
                                                                       storage_charge_cycle_limit,
                                                                       float(config_parser[manufacturer][COARSE_PROBE_THRESHOLD_MARGIN_TAG]),
                                                                       charger_amp_hour_rate,
                                                                       battery_amp_hour_capacity,
                                                                       charger_max_hours_to_run,
                                                                       battery_voltage,
                                                                       charger_efficiency=charger_efficiency)

            sections = list(config_parser.keys())
            if CONFIG_PLUGS_SECTION in sections:
                for plug_name, manufacturer in config_parser[CONFIG_PLUGS_SECTION].items():
                    if not manufacturer in manufacturers:
                        logger.error(
                            f'>>>>> ERROR in verify_config_file, {manufacturer} not specified')
                        verified = False
                        plug_manufacturer_map[plug_name] = DEFAULT_CONFIG_TAG
                        continue
                    if manufacturer in device_config:
                        plug_manufacturer_map[plug_name] = manufacturer
                    else:
                        plug_manufacturer_map[plug_name] = DEFAULT_CONFIG_TAG
            # any plugs in storage mode?
            if CONFIG_STORAGE_SECTION in sections:
                plug_storage_list = list(config_parser[CONFIG_STORAGE_SECTION])
                BatteryManagerState().plug_storage_list = plug_storage_list
            if CONFIG_FULL_CHARGE_SECTION in sections:
                full_charge_list = list(
                    config_parser[CONFIG_FULL_CHARGE_SECTION])
                plug_full_charge_list = list(
                    set(full_charge_list) - set(plug_storage_list))
                BatteryManagerState().plug_full_charge_list = plug_full_charge_list
        else:
            logger.error(
                f'>>>>> ERROR: specified config_file: {config_file_name} does not exist')
            return False
    # Bad form but we want to absolutely return True or False from this function and any exception => False
    except Exception as e:
        logger.error(
            f'FATAL ERROR: Exception in verify_config_file({config_file_name}): {str(e)}')
        config_parser = None

    return verified


async def test_stuff() -> None:
    '''
    Internal test with real devices
    Used in lieu of an actual async test layer
    '''
    max_cycles_in_fine_mode: int = BatteryManagerState().max_cycles_in_fine_mode
    logger.info('test_stuff: ENTRY')
    battery_plug_list = []
    test_remove = []
    found = await Discover.discover()
    for dev in found.values():
        await dev.update()
        if dev.is_plug:
            if BATTERY_PREFIX in dev.alias:
                battery_plug = BatteryPlug(
                    dev.alias, dev, max_cycles_in_fine_mode)
                # logger.info(f'dir: {str(dir(battery_plug))}')
                logger.info(
                    f'plug: {battery_plug.name}, power: {str(battery_plug.get_power())}')
                battery_plug_list.append(battery_plug)
        if dev.is_strip:
            logger.info(f'test_stuff: dev.children: {len(dev.children)}')
            index = 0
            for child_plug in dev.children:
                if BATTERY_PREFIX in child_plug.alias:
                    battery_plug = BatteryStripPlug(
                        child_plug.alias, dev, index, max_cycles_in_fine_mode)
                    # logger.info(f'child_plug:dir: {str(dir(battery_plug))}')
                    # logger.info(f'child_plug: {battery_plug.get_name()}, power: {str(battery_plug.get_power())}')
                    logger.info(
                        f'child_plug: {battery_plug.name}, power: {str(battery_plug.get_power())}')
                    battery_plug_list.append(battery_plug)
                    if len(test_remove) < 3:
                        test_remove.append(battery_plug)
                index = index + 1
    logger.info(
        f'test_stuff: battery_plug_list: len: {len(battery_plug_list), {str(battery_plug_list)}}')
    # for item in test_remove:
    #     battery_plug_list.remove(item)
    # logger.info(f'test_stuff: after remove: battery_plug_list: len: {len(battery_plug_list), {str(battery_plug_list)}}')
    for item in battery_plug_list:
        await item.turn_off()
        logger.info(
            f'iterate: name: {item.name} on: {str(item.is_on())}, power: {str(item.get_power())}')
        logger.info(
            f'iterate: name: {item.name} on: {str(item.is_on())}, power: {str(item.get_power())}')


def start_quiet_mode() -> None:
    if BatteryManagerState().quiet_mode:
        logging.getLogger("").setLevel(logging.WARNING)


def stop_quiet_mode() -> None:
    logging.getLogger("").setLevel(logging.INFO)


def force_log(log: str) -> None:
    logger.custom(log)
    # log_level = logging.getLogger("").getEffectiveLevel()
    # logging.getLogger("").setLevel(logging.INFO)
    # logging.info(log)
    # logging.getLogger("").setLevel(log_level)


def log_start_state(max_hours_to_run: int,
                           log_file: str,
                           config_file: str,
                           test_mode: bool,
                           config_file_is_valid: bool
                           ) -> None:
    if BatteryManagerState().logging_mode == LoggingMode.SUPER_QUIET:
        # Even in SUPER_QUIET, forcing a full charge is important to know
        if BatteryManagerState().force_full_charge:
            logger.info(f'  ---- force_full_charge: True')
        return
    device_config = BatteryManagerState().device_config
    default_config: DeviceConfig = BatteryManagerState().default_config

    if test_mode:
        logger.info(f'  ---- test_mode: {str(test_mode)}')
    logger.info(f'  ---- quiet_mode: {str(BatteryManagerState().quiet_mode)}')
    if BatteryManagerState().force_full_charge:
        logger.info(f'  ---- force_full_charge: {str(BatteryManagerState().force_full_charge)}')
        logger.info(
            f'  ---- full_charge_repeat_limit: {str(BatteryManagerState().full_charge_repeat_limit)}')
    logger.info(
        f'  ---- max_cycles_in_fine_mode: {str(BatteryManagerState().max_cycles_in_fine_mode)}')
    logger.info(f'  ---- max_hours_to_run: {str(max_hours_to_run)}')
    logger.info(f'  ---- logfile: {str(log_file)}')
    logger.info(f'  ---- config_file: {str(config_file)}')
    logger.info(f'  ---- DEFAULT config')
    logger.info(
        f'  -------- nominal_charge_start_power_threshold: {str(default_config.nominal_charge_start_power_threshold)}')
    logger.info(
        f'  -------- nominal_charge_stop_power_threshold: {str(default_config.nominal_charge_stop_power_threshold)}')
    logger.info(
        f'  -------- full_charge_power_threshold: {str(default_config.full_charge_power_threshold)}')
    logger.info(
        f'  -------- storage_charge_start_power_threshold: {str(default_config.storage_charge_start_power_threshold)}')
    logger.info(
        f'  -------- storage_charge_stop_power_threshold: {str(default_config.storage_charge_stop_power_threshold)}')
    logger.info(
        f'  -------- storage_charge_cycle_limit: {str(BatteryManagerState().storage_charge_cycle_limit)}')
    logger.info(
        f'  -------- scan_for_battery_prefix: {BatteryManagerState().scan_for_battery_prefix}')
    logger.info(
        f'  -------- charger_efficiency: {str(default_config.charger_efficiency)}')
    if config_file_is_valid:
        logger.info(f'  ---- MANUFACTURER specific thresholds')
        for manufacturer in device_config:
            if manufacturer == "DEFAULT":
                continue
            logger.info(f'  ---- manufacturer: {str(manufacturer)}')
            logger.info(
                f'  -------- nominal_charge_start_power_threshold: {str(device_config[manufacturer].nominal_charge_start_power_threshold)}')
            logger.info(
                f'  -------- nominal_charge_stop_power_threshold: {str(device_config[manufacturer].nominal_charge_stop_power_threshold)}')
            logger.info(
                f'  -------- full_charge_power_threshold: {str(device_config[manufacturer].full_charge_power_threshold)}')
            logger.info(
                f'  -------- storage_charge_start_power_threshold: {str(device_config[manufacturer].storage_charge_start_power_threshold)}')
            logger.info(
                f'  -------- storage_charge_stop_power_threshold: {str(device_config[manufacturer].storage_charge_stop_power_threshold)}')
            logger.info(
                f'  -------- storage_charge_cycle_limit: {str(device_config[manufacturer].storage_charge_cycle_limit)}')
            logger.info(
                f'  -------- charger_amp_hour_rate: {str(device_config[manufacturer].charger_amp_hour_rate) if device_config[manufacturer].charger_amp_hour_rate > 0.0 else "N/A"}')
            logger.info(
                f'  -------- battery_amp_hour_capacity: {str(device_config[manufacturer].battery_amp_hour_capacity) if device_config[manufacturer].battery_amp_hour_capacity > 0.0 else "N/A"}')
            logger.info(
                f'  -------- charger_max_hours_to_run: {str(device_config[manufacturer].charger_max_hours_to_run)}')
            logger.info(
                f'  -------- battery_voltage: {str(device_config[manufacturer].battery_voltage)}')
            logger.info(
                f'  -------- charger_efficiency: {str(device_config[manufacturer].charger_efficiency)}')


def log_actively_charging_plugs(active_plugs: Set[ActivePlug]) -> None:
    if len(active_plugs) > 0:
        def get_total_amp_hours(plug: ActivePlug) -> float:
            return plug.plug.get_power_total()
        
        def insert_sorted(sorted_list, item, key) -> None:
            key_value = -key(item)
            bisect.insort(sorted_list, (key_value, item))

        sorted_active_plugs = []
        for plug in active_plugs:
            if plug.plug.total_amp_hours > MINIMUM_AMP_THRESHOLD_FOR_ACTIVE_CHARGE:
                insert_sorted(sorted_active_plugs, plug, get_total_amp_hours)

        if len(sorted_active_plugs) == 0:
            logger.info(f'No plugs were actively charging this run')
            return
        try:
            logger.info(f'The following plugs were actively charging this run:')
            start_threshold_logger.info(
                f'The following plugs were actively charging this run:')
            
            for _, plug in sorted_active_plugs:
                if plug.start_time and plug.stop_time:
                    plug_elapsed_charge_time = plug.stop_time - plug.start_time
                    total_seconds = int(plug_elapsed_charge_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    plug_name = plug.plug.name
                    total_amp_hours = get_total_amp_hours(plug)
                    logger.info(
                        f'    {plug_name}, charged for {hours:02}:{minutes:02}:{seconds:02} added ~{total_amp_hours:.2f} Ah')
                    start_threshold_logger.info(
                        f'    {plug_name}, charged for {hours:02}:{minutes:02}:{seconds:02} added ~{total_amp_hours:.2f} Ah')
                else:
                    logger.info(
                        f'    {plug.plug_name}, charged for unknown duration')
                    start_threshold_logger.info(
                        f'    {plug.plug_name}, charged for unknown duration')
        except Exception as e:
            logger.error(f'Exception in{fn_name()} for plug: {plug_name}: {str(e)}')
    else:
        logger.info(f'No plugs were actively charging this run')


def run_battery_controller(max_hours_to_run: int,
                           log_file: str,
                           config_file: str,
                           email: str,
                           app_key: str,
                           test_mode: bool) -> None:
    '''
    main entry point, expects any global defaults to be settled by this time.
    Currently in script mode, main() will do that work.  When not in script mode,
    users of this entry point must do any setup work if the global defaults are not
    acceptable.


    Args:
        max_hours_to_run (int): 
        log_file (str): 
        config_file (str): 
        email (str): 
        app_key (str): 
        test_mode (bool): 
    '''
    global start_threshold_logger

    start_threshold_logger.info(f"test test test")
    start_threshold_logger.error(f"test test test")

    plug_full_charge_list = BatteryManagerState().plug_full_charge_list
    device_config = BatteryManagerState().device_config
    plug_storage_list = BatteryManagerState().plug_storage_list
    active_plugs: Set[ActivePlug] = BatteryManagerState().active_plugs

    logger.info(f'Script logs are in {log_file}')
    start = datetime.now()

    config_file_is_valid = False
    if config_file != None:
        config_file_is_valid = verify_config_file(config_file)
    default_config: DeviceConfig = BatteryManagerState().default_config
    device_config[DEFAULT_CONFIG_TAG] = default_config

    log_start_state(max_hours_to_run=max_hours_to_run, 
                    log_file=log_file, 
                    config_file=config_file, 
                    test_mode=test_mode, 
                    config_file_is_valid=config_file_is_valid)
    start_quiet_mode()
    if len(plug_storage_list) > 0:
        logger.info(f'  ---- plugs in storage mode: ')
        for plug_name in plug_storage_list:
            logger.info(f'      ---- plug name: {plug_name}')
    if len(plug_full_charge_list) > 0:
        logger.info(f'  ---- plugs in full charge mode: ')
        for plug_name in plug_full_charge_list:
            logger.info(f'      ---- plug name: {plug_name}')

    if test_mode:
        # asyncio.run(test_stuff())
        return

    success = asyncio.run(analyze_loop(
        start + timedelta(hours=max_hours_to_run)))
    stop = datetime.now()
    elapsed_time = stop - start
    stop_quiet_mode()
    logger.custom(f'>>>>> !!!! FINI: success: {str(success)} !!!! <<<<<')
    log_actively_charging_plugs(active_plugs=active_plugs)
    logger.info(f'==> Elapsed time: {str(elapsed_time).split(".", 2)[0]}')

    send_file_email(email=email, app_key=app_key, subject=f'battery_plug_controller status', file_path=log_file)


def exit_handler():
    """
    This function is registered with atexit to handle graceful shutdown of async tasks.
    It attempts to get the current event loop, and if successful, it runs the shutdown_plugs
    coroutine within that loop. If the loop is not running, it creates a new event loop
    to run the shutdown_plugs coroutine.
    """
    logger.info("Executing exit_handler")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            logger.info("Running shutdown_plugs within the current event loop")
            loop.create_task(shutdown_plugs())
        else:
            logger.info("Running shutdown_plugs in the existing event loop")
            loop.run_until_complete(shutdown_plugs())
    except RuntimeError as e:
        logger.info(f"Failed to get event loop: {e}")
        # Create a new event loop if the current one is not available
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("Running shutdown_plugs in a new event loop")
        loop.run_until_complete(shutdown_plugs())
        loop.close()

    logger.info("Event loop closed")

def process_overrides(args) -> None:
    if args.scan_for_battery_prefix != None and args.scan_for_battery_prefix == True:
        try:
            scan_for_battery_prefix = bool(
                args.scan_for_battery_prefix)
            logger.info(
                f'>>>>> OVERRIDE scan_for_battery_prefix: {str(scan_for_battery_prefix)}')
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f'ERROR, Invalid scan_for_battery_prefix: {str(e)}')
    if args.nominal_start_charge_threshold != None:
        try:
            nominal_charge_start_power_threshold = float(
                args.nominal_start_charge_threshold)
            logger.info(
                f'>>>>> OVERRIDE nominal_charge_start_power_threshold: {str(nominal_charge_start_power_threshold)}')
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f'ERROR, Invalid nominal_charge_start_charge_threshold: {str(e)}')
    if args.nominal_charge_cutoff != None:
        try:
            nominal_charge_stop_power_threshold = float(
                args.nominal_charge_cutoff)
            logger.info(
                f'>>>>> OVERRIDE nominal_charge_stop_power_threshold: {str(nominal_charge_stop_power_threshold)}')
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f'ERROR, Invalid nominal_charge_stop_power_threshold: {str(e)}')
    if args.full_charge_cutoff != None:
        try:
            full_charge_power_threshold = float(
                args.full_charge_cutoff)
            logger.info(
                f'>>>>> OVERRIDE full_charge_power_threshold: {str(full_charge_power_threshold)}')
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f'ERROR, Invalid full_charge_power_threshold: {str(e)}')
    if args.storage_start_charge_threshold != None:
        try:
            storage_charge_start_power_threshold = float(
                args.storage_start_charge_threshold)
            logger.info(
                f'>>>>> OVERRIDE storage_charge_start_power_threshold: {str(storage_charge_start_power_threshold)}')
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f'ERROR, Invalid storage_charge_start_power_threshold: {str(e)}')
    if args.storage_charge_cutoff != None:
        try:
            storage_charge_stop_power_threshold = float(
                args.storage_charge_cutoff)
            logger.info(
                f'>>>>> OVERRIDE storage_charge_stop_power_threshold: {str(storage_charge_stop_power_threshold)}')
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f'ERROR, Invalid storage_charge_stop_power_threshold: {str(e)}')
    if args.full_charge_repeat_limit != None:
        try:
            BatteryManagerState().full_charge_repeat_limit = args.full_charge_repeat_limit
            logger.info(
                f'>>>>> OVERRIDE full_charge_repeat_limit: {str(BatteryManagerState().full_charge_repeat_limit)}')
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f'ERROR, Invalid full_charge_repeat_limit: {str(e)}')
    if args.max_cycles_in_fine_mode != None:
        try:
            BatteryManagerState().max_cycles_in_fine_mode = args.max_cycles_in_fine_mode
            logger.info(
                f'>>>>> OVERRIDE max_cycles_in_fine_mode: {str(BatteryManagerState().max_cycles_in_fine_mode)}')
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f'ERROR, Invalid max_cycles_in_fine_mode: {str(e)}')
    if args.storage_charge_cycle_limit != None:
        try:
            BatteryManagerState().storage_charge_cycle_limit = args.storage_charge_cycle_limit
            logger.info(
                f'>>>>> OVERRIDE storage_charge_cycle_limit: {str(BatteryManagerState().storage_charge_cycle_limit)}')
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f'ERROR, Invalid storage_charge_cycle_limit: {str(e)}')
    if args.max_hours_to_run != None:
        try:
            BatteryManagerState().max_hours_to_run = args.max_hours_to_run
            logger.info(
                f'>>>>> OVERRIDE max_hours_to_run: {str(BatteryManagerState().max_hours_to_run)}')
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(f'ERROR, Invalid max_hours_to_run {str(BatteryManagerState().max_hours_to_run)}, exception: {str(e)}')
    BatteryManagerState().quiet_mode = args.quiet_mode
    if args.quiet_mode:
        BatteryManagerState().logging_mode = LoggingMode.SUPER_QUIET
    else:
        BatteryManagerState().logging_mode = LoggingMode.VERBOSE

    
def main() -> None:
    global start_threshold_logger, logger

    # nominal_charge_start_power_threshold = NOMINAL_CHARGE_START_THRESHOLD_DEFAULT
    # nominal_charge_stop_power_threshold = NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT
    # full_charge_power_threshold = FULL_CHARGE_THRESHOLD_DEFAULT
    # storage_charge_start_power_threshold = STORAGE_CHARGE_START_THRESHOLD_DEFAULT
    # storage_charge_stop_power_threshold = STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT
    # log_file = DEFAULT_LOG_FILE

    atexit.register(exit_handler)
    signal.signal(signal.SIGINT, sigint_handler)

    parser = init_argparse()
    args = parser.parse_args()

    # set up default logging
    if args.log_file_name != None:
        BatteryManagerState().log_file = args.log_file_name

    logger = init_logging(log_file=BatteryManagerState().log_file)

    logger.custom('>>>>> START <<<<<')
    BatteryManagerState().force_full_charge = args.force_full_charge

    process_overrides(args)

    start_threshold_logger = DebugLogger('start_threshold_logger', level=logging.INFO, active=BatteryManagerState().debug_file_logger_active)

    # By here global default values for thresholds are valid so create the DEFAULT one
    BatteryManagerState().default_config = DeviceConfig(DEFAULT_CONFIG_TAG,
                                          BatteryManagerState().nominal_charge_start_power_threshold,
                                          BatteryManagerState().nominal_charge_stop_power_threshold,
                                          BatteryManagerState().full_charge_power_threshold,
                                          BatteryManagerState().storage_charge_start_power_threshold,
                                          BatteryManagerState().storage_charge_stop_power_threshold,
                                          BatteryManagerState().storage_charge_cycle_limit,
                                          COARSE_PROBE_THRESHOLD_MARGIN,
                                          0.0,
                                          0.0,
                                          MAX_RUNTIME_HOURS_DEFAULT
                                          )
    run_battery_controller(BatteryManagerState().max_hours_to_run,
                           BatteryManagerState().log_file,
                           args.config_file,
                           args.email,
                           args.app_key,
                           args.test_mode)


if __name__ == '__main__':
    main()
