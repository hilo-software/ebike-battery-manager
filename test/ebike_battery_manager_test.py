#!/usr/bin/python3
import pytest
import logging
import asyncio
from argparse import Namespace
from kasa import SmartDevice
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from math import ceil
import time
import configparser

CONFIG_PATH = './config/'
LECTRIC_NOMINAL_START_THRESHOLD = 90.0
LECTRIC_NOMINAL_STOP_THRESHOLD = 80.0
LECTRIC_STORAGE_START_THRESHOLD = 90.0
LECTRIC_STORAGE_STOP_THRESHOLD = 80.0
LECTRIC_FULL_CHARGE_THRESHOLD = 4.0
LECTRIC_COARSE_MARGIN = 15.0
RAD_CHARGER_AMP_HOUR_RATE = 2.0
RAD_BATTERY_AMP_HOUR_CAPACITY = 14.0
LECTRIC_CHARGER_AMP_HOUR_RATE = 2.0
LECTRIC_BATTERY_AMP_HOUR_CAPACITY = 14.4
RAD_BATTERY_1 = 'rad_battery_1'
RAD_MANUFACTURER_NAME = 'Rad'

target = __import__("scripts.ebike_battery_manager")
target = target.ebike_battery_manager
battery_plug_list = target.BatteryManagerState().battery_plug_list
DeviceConfig = target.DeviceConfig
BatteryPlug = target.BatteryPlug
BatteryStripPlug = target.BatteryStripPlug
max_cycles_in_fine_mode = target.BatteryManagerState().max_cycles_in_fine_mode
default_config = target.BatteryManagerState().default_config
rad_config: DeviceConfig = DeviceConfig('Rad',
                                        target.NOMINAL_CHARGE_START_THRESHOLD_DEFAULT,
                                        target.NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT,
                                        target.FULL_CHARGE_THRESHOLD_DEFAULT,
                                        target.STORAGE_CHARGE_START_THRESHOLD_DEFAULT,
                                        target.STORAGE_CHARGE_STOP_THRESHOLD_TAG,
                                        target.STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT,
                                        target.COARSE_PROBE_THRESHOLD_MARGIN,
                                        RAD_CHARGER_AMP_HOUR_RATE,
                                        RAD_BATTERY_AMP_HOUR_CAPACITY,
                                        ceil(RAD_BATTERY_AMP_HOUR_CAPACITY /
                                             RAD_CHARGER_AMP_HOUR_RATE),
                                        target.DEFAULT_BATTERY_VOLTAGE
                                        )

lectric_config: DeviceConfig = DeviceConfig('Lectric',
                                            LECTRIC_NOMINAL_START_THRESHOLD,
                                            LECTRIC_NOMINAL_STOP_THRESHOLD,
                                            LECTRIC_FULL_CHARGE_THRESHOLD,
                                            LECTRIC_STORAGE_START_THRESHOLD,
                                            LECTRIC_STORAGE_STOP_THRESHOLD,
                                            target.STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT,
                                            LECTRIC_COARSE_MARGIN,
                                            LECTRIC_CHARGER_AMP_HOUR_RATE,
                                            LECTRIC_BATTERY_AMP_HOUR_CAPACITY,
                                            ceil(LECTRIC_BATTERY_AMP_HOUR_CAPACITY /
                                                 LECTRIC_CHARGER_AMP_HOUR_RATE),
                                            target.DEFAULT_BATTERY_VOLTAGE
                                            )

@pytest.fixture(scope="session", autouse=True)
def execute_before_any_test():
    
    global rad_config, battery_plug_list
    assert len(target.BatteryManagerState().device_config) == 0
    assert len(target.BatteryManagerState().battery_plug_list) == 0
    target.BatteryManagerState().device_config['Rad'] = rad_config
    target.BatteryManagerState().device_config['Lectric'] = lectric_config
    create_default_device_config()

    battery_plug_list.append(BatteryPlug('battery_1', target.SmartDevice('127.0.0.1'), max_cycles_in_fine_mode, rad_config))
    battery_plug_list.append(BatteryPlug('battery_2', target.SmartDevice('127.0.0.1'), max_cycles_in_fine_mode, rad_config))


def create_default_device_config() -> None:
    target.BatteryManagerState().device_config[target.DEFAULT_CONFIG_TAG] = DeviceConfig(
        target.DEFAULT_CONFIG_TAG,
        target.NOMINAL_CHARGE_START_THRESHOLD_DEFAULT,
        target.NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT,
        target.FULL_CHARGE_THRESHOLD_DEFAULT,
        target.STORAGE_CHARGE_START_THRESHOLD_DEFAULT,
        target.STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT,
        target.STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT,
        target.COARSE_PROBE_THRESHOLD_MARGIN,
        0.0,
        0.0,
        target.MAX_RUNTIME_HOURS_DEFAULT
    )

def test_fixture_init():
    print(f'fake, battery_plug_list')
    assert len(battery_plug_list) > 0
    assert len(target.BatteryManagerState().device_config) == 3

def reset_device_config():
    target.BatteryManagerState().device_config.clear()
    target.BatteryManagerState().plug_manufacturer_map.clear()
    create_default_device_config()
    # target.BatteryManagerState().device_config[target.DEFAULT_CONFIG_TAG] = target.default_config

def set_sample_thresholds():
    reset_device_config()
    result = target.verify_config_file(CONFIG_PATH + 'sample_ebike_battery_manager.config')
    assert result == True
    assert len(target.BatteryManagerState().device_config) == 3
    assert len(target.BatteryManagerState().plug_manufacturer_map) == 5
    assert len(target.BatteryManagerState().plug_storage_list) == 1

def test_battery_manager_simple_state():
    # test default state getters
    assert target.BatteryManagerState().full_charge_repeat_limit == target.FULL_CHARGE_REPEAT_LIMIT
    assert target.BatteryManagerState().fine_probe_interval_secs == target.FINE_PROBE_INTERVAL_SECS
    assert target.BatteryManagerState().probe_interval_secs == target.COARSE_PROBE_INTERVAL_SECS
    assert target.BatteryManagerState().max_cycles_in_fine_mode == target.MAX_CYCLES_IN_FINE_MODE
    assert target.BatteryManagerState().force_full_charge == False
    assert target.BatteryManagerState().max_hours_to_run == target.MAX_RUNTIME_HOURS_DEFAULT
    assert target.BatteryManagerState().storage_charge_cycle_limit == target.STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT
    assert target.BatteryManagerState().analyze_first_entry == True
    assert target.BatteryManagerState().quiet_mode == False
    assert target.BatteryManagerState().scan_for_battery_prefix == False
    assert target.BatteryManagerState().nominal_charge_start_power_threshold == target.NOMINAL_CHARGE_START_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().nominal_charge_stop_power_threshold == target.NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().full_charge_power_threshold == target.FULL_CHARGE_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().storage_charge_start_power_threshold == target.STORAGE_CHARGE_START_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().storage_charge_stop_power_threshold == target.STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().log_file == target.DEFAULT_LOG_FILE
    assert target.BatteryManagerState().debug_file_logger_active == False

    # test state setters
    target.BatteryManagerState().full_charge_repeat_limit = target.FULL_CHARGE_REPEAT_LIMIT - 1
    assert target.BatteryManagerState().full_charge_repeat_limit == target.FULL_CHARGE_REPEAT_LIMIT - 1
    target.BatteryManagerState().full_charge_repeat_limit = target.FULL_CHARGE_REPEAT_LIMIT
    assert target.BatteryManagerState().full_charge_repeat_limit == target.FULL_CHARGE_REPEAT_LIMIT

    target.BatteryManagerState().fine_probe_interval_secs = target.FINE_PROBE_INTERVAL_SECS - 1
    assert target.BatteryManagerState().fine_probe_interval_secs == target.FINE_PROBE_INTERVAL_SECS - 1
    target.BatteryManagerState().fine_probe_interval_secs = target.FINE_PROBE_INTERVAL_SECS
    assert target.BatteryManagerState().fine_probe_interval_secs == target.FINE_PROBE_INTERVAL_SECS

    target.BatteryManagerState().probe_interval_secs = target.COARSE_PROBE_INTERVAL_SECS - 1
    assert target.BatteryManagerState().probe_interval_secs == target.COARSE_PROBE_INTERVAL_SECS - 1
    target.BatteryManagerState().probe_interval_secs = target.COARSE_PROBE_INTERVAL_SECS
    assert target.BatteryManagerState().probe_interval_secs == target.COARSE_PROBE_INTERVAL_SECS

    target.BatteryManagerState().max_cycles_in_fine_mode = target.MAX_CYCLES_IN_FINE_MODE - 1
    assert target.BatteryManagerState().max_cycles_in_fine_mode == target.MAX_CYCLES_IN_FINE_MODE - 1
    target.BatteryManagerState().max_cycles_in_fine_mode = target.MAX_CYCLES_IN_FINE_MODE
    assert target.BatteryManagerState().max_cycles_in_fine_mode == target.MAX_CYCLES_IN_FINE_MODE

    target.BatteryManagerState().force_full_charge = True
    assert target.BatteryManagerState().force_full_charge == True
    target.BatteryManagerState().force_full_charge = False
    assert target.BatteryManagerState().force_full_charge == False

    target.BatteryManagerState().max_hours_to_run = target.MAX_RUNTIME_HOURS_DEFAULT - 1
    assert target.BatteryManagerState().max_hours_to_run == target.MAX_RUNTIME_HOURS_DEFAULT - 1
    target.BatteryManagerState().max_hours_to_run = target.MAX_RUNTIME_HOURS_DEFAULT
    assert target.BatteryManagerState().max_hours_to_run == target.MAX_RUNTIME_HOURS_DEFAULT

    target.BatteryManagerState().storage_charge_cycle_limit = target.STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT - 1
    assert target.BatteryManagerState().storage_charge_cycle_limit == target.STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT - 1
    target.BatteryManagerState().storage_charge_cycle_limit = target.STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT
    assert target.BatteryManagerState().storage_charge_cycle_limit == target.STORAGE_CHARGE_CYCLE_LIMIT_DEFAULT

    target.BatteryManagerState().analyze_first_entry = False
    assert target.BatteryManagerState().analyze_first_entry == False
    target.BatteryManagerState().analyze_first_entry = True
    assert target.BatteryManagerState().analyze_first_entry == True

    target.BatteryManagerState().quiet_mode = True
    assert target.BatteryManagerState().quiet_mode == True
    target.BatteryManagerState().quiet_mode = False
    assert target.BatteryManagerState().quiet_mode == False

    target.BatteryManagerState().scan_for_battery_prefix = True
    assert target.BatteryManagerState().scan_for_battery_prefix == True
    target.BatteryManagerState().scan_for_battery_prefix = False
    assert target.BatteryManagerState().scan_for_battery_prefix == False

    target.BatteryManagerState().nominal_charge_start_power_threshold = target.NOMINAL_CHARGE_START_THRESHOLD_DEFAULT - 1
    assert target.BatteryManagerState().nominal_charge_start_power_threshold == target.NOMINAL_CHARGE_START_THRESHOLD_DEFAULT - 1
    target.BatteryManagerState().nominal_charge_start_power_threshold = target.NOMINAL_CHARGE_START_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().nominal_charge_start_power_threshold == target.NOMINAL_CHARGE_START_THRESHOLD_DEFAULT

    target.BatteryManagerState().nominal_charge_stop_power_threshold = target.NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT - 1
    assert target.BatteryManagerState().nominal_charge_stop_power_threshold == target.NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT - 1
    target.BatteryManagerState().nominal_charge_stop_power_threshold = target.NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().nominal_charge_stop_power_threshold == target.NOMINAL_CHARGE_STOP_THRESHOLD_DEFAULT

    target.BatteryManagerState().full_charge_power_threshold = target.FULL_CHARGE_THRESHOLD_DEFAULT - 1
    assert target.BatteryManagerState().full_charge_power_threshold == target.FULL_CHARGE_THRESHOLD_DEFAULT - 1
    target.BatteryManagerState().full_charge_power_threshold = target.FULL_CHARGE_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().full_charge_power_threshold == target.FULL_CHARGE_THRESHOLD_DEFAULT

    target.BatteryManagerState().storage_charge_start_power_threshold = target.STORAGE_CHARGE_START_THRESHOLD_DEFAULT - 1
    assert target.BatteryManagerState().storage_charge_start_power_threshold == target.STORAGE_CHARGE_START_THRESHOLD_DEFAULT - 1
    target.BatteryManagerState().storage_charge_start_power_threshold = target.STORAGE_CHARGE_START_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().storage_charge_start_power_threshold == target.STORAGE_CHARGE_START_THRESHOLD_DEFAULT

    target.BatteryManagerState().storage_charge_stop_power_threshold = target.STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT - 1
    assert target.BatteryManagerState().storage_charge_stop_power_threshold == target.STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT - 1
    target.BatteryManagerState().storage_charge_stop_power_threshold = target.STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().storage_charge_stop_power_threshold == target.STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT

    target.BatteryManagerState().log_file = 'FUBAR.LOG'
    assert target.BatteryManagerState().log_file == 'FUBAR.LOG'
    target.BatteryManagerState().log_file = target.DEFAULT_LOG_FILE
    assert target.BatteryManagerState().log_file == target.DEFAULT_LOG_FILE

    target.BatteryManagerState().debug_file_logger_active = True
    assert target.BatteryManagerState().debug_file_logger_active == True
    target.BatteryManagerState().debug_file_logger_active = False
    assert target.BatteryManagerState().debug_file_logger_active == False


def test_battery_manager_container_default_state():
    # test state
    # We always append two plugs in execute_before_any_test() above so we expect to have 2 in this list
    assert len(target.BatteryManagerState().battery_plug_list) == 2
    # Similarly for device_config except there should be 3 items since there is a default one too
    assert len(target.BatteryManagerState().device_config) == 3
    # The rest of the containers should be at defaults
    assert len(target.BatteryManagerState().plug_manufacturer_map) == 0
    assert len(target.BatteryManagerState().plug_storage_list) == 0
    assert len(target.BatteryManagerState().plug_full_charge_list) == 0
    assert len(target.BatteryManagerState().active_plugs) == 0


@pytest.mark.parametrize("args, expected_logs", [
    # Test cases for different overrides
    (Namespace(nominal_start_charge_threshold="5.0", nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["INFO:root:>>>>> OVERRIDE nominal_charge_start_power_threshold: 5.0"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff="10.0", full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["INFO:root:>>>>> OVERRIDE nominal_charge_stop_power_threshold: 10.0"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff="15.0", storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["INFO:root:>>>>> OVERRIDE full_charge_power_threshold: 15.0"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold="20.0", storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["INFO:root:>>>>> OVERRIDE storage_charge_start_power_threshold: 20.0"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff="25.0", full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["INFO:root:>>>>> OVERRIDE storage_charge_stop_power_threshold: 25.0"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=2, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["INFO:root:>>>>> OVERRIDE full_charge_repeat_limit: 2"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=5, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["INFO:root:>>>>> OVERRIDE max_cycles_in_fine_mode: 5"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=3, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["INFO:root:>>>>> OVERRIDE storage_charge_cycle_limit: 3"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=10, scan_for_battery_prefix=None, quiet_mode=None),
     ["INFO:root:>>>>> OVERRIDE max_hours_to_run: 10"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=True, quiet_mode=None),
     ["INFO:root:>>>>> OVERRIDE scan_for_battery_prefix: True"]),
    
    # Test cases for invalid values
    (Namespace(nominal_start_charge_threshold="invalid", nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["ERROR:root:ERROR, Invalid nominal_charge_start_charge_threshold: could not convert string to float: 'invalid'"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff="invalid", full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["ERROR:root:ERROR, Invalid nominal_charge_stop_power_threshold: could not convert string to float: 'invalid'"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff="invalid", storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["ERROR:root:ERROR, Invalid full_charge_power_threshold: could not convert string to float: 'invalid'"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold="invalid", storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["ERROR:root:ERROR, Invalid storage_charge_start_power_threshold: could not convert string to float: 'invalid'"]),
    
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff="invalid", full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=None),
     ["ERROR:root:ERROR, Invalid storage_charge_stop_power_threshold: could not convert string to float: 'invalid'"]),
    
    # Test case for quiet mode
    (Namespace(nominal_start_charge_threshold=None, nominal_charge_cutoff=None, full_charge_cutoff=None, storage_start_charge_threshold=None, storage_charge_cutoff=None, full_charge_repeat_limit=None, max_cycles_in_fine_mode=None, storage_charge_cycle_limit=None, max_hours_to_run=None, scan_for_battery_prefix=None, quiet_mode=True),
     [])
])

def test_process_overrides(args, expected_logs, caplog):
    '''
    Written by ChatGPT 4

    Args:
        args (_type_): _description_
        expected_logs (_type_): _description_
        caplog (_type_): _description_
    '''
    with caplog.at_level(logging.INFO):
        target.process_overrides(args)
    log_messages = [f"{record.levelname}:{record.name}:{record.message}" for record in caplog.records]
    assert log_messages == expected_logs


def test_setup_logging_handlers():
    # Passing a null filename will cause an exception and the 
    # logging_handlers list should only have one item.
    logging_handlers = target.setup_logging_handlers('')
    assert len(logging_handlers) == 1
    # Passing a valid filename will create the log file and the 
    # logging_handlers list should have two items.
    logging_handlers = target.setup_logging_handlers('foo.txt')
    assert len(logging_handlers) == 2

def test_verify_config_file():
    reset_device_config()
    result = target.verify_config_file('not_a_real_file.config')
    assert result == False
    assert len(target.BatteryManagerState().plug_manufacturer_map) == 0
    reset_device_config()
    result = target.verify_config_file(CONFIG_PATH + 'sample_ebike_battery_manager.config')
    assert result == True
    assert len(target.BatteryManagerState().device_config) == 3
    assert len(target.BatteryManagerState().plug_manufacturer_map) == 5
    assert len(target.BatteryManagerState().plug_storage_list) == 1
    reset_device_config()
    result = target.verify_config_file(CONFIG_PATH + 'error_battery_plug_file.config')
    assert result == False
    assert len(target.BatteryManagerState().device_config) == 3
    assert len(target.BatteryManagerState().plug_manufacturer_map) == 5
    assert target.BatteryManagerState().plug_manufacturer_map['rad_battery_3'] == target.DEFAULT_CONFIG_TAG

@pytest.mark.asyncio
async def test_battery_plug_exception():
    with patch('kasa.SmartDevice', new_callable=AsyncMock) as mock:
        mock_smart_device_plug = mock.return_value
        mock_smart_device_plug.is_plug = True
        mock_smart_device_plug.is_strip = False
        mock_smart_device_plug.is_on = False
        battery_plug = target.create_battery_plug('TestExceptionPlug', mock_smart_device_plug)
        exception_occurred = False
        try:
            await battery_plug.turn_on()
        except target.BatteryPlugException as e:
            exception_occurred = True
        finally:
            assert exception_occurred


@pytest.mark.asyncio
async def test_battery_strip_plug_exception():
    with patch('kasa.SmartDevice', new_callable=AsyncMock) as mock:
        with patch('kasa.SmartDevice', new_callable=AsyncMock) as child_mock_1:
            with patch('kasa.SmartDevice', new_callable=AsyncMock) as child_mock_2:
                mock_smart_device_strip = mock.return_value
                mock_smart_device_strip.is_plug = False
                mock_smart_device_strip.is_strip = True
                mock_smart_device_strip.alias = 'lectric_strip_1'
                mock_strip_children = []
                mock_strip_children.append(child_mock_1.return_value)
                mock_strip_children[0].alias = 'lectric_battery_1'
                mock_strip_children[0].is_on = True
                mock_strip_children.append(child_mock_2.return_value)
                mock_strip_children[1].alias = 'lectric_battery_2'
                mock_strip_children[1].is_on = False
                mock_smart_device_strip.children = mock_strip_children
                battery_strip_plug = target.create_battery_strip_plug('TestExceptionStripPlug', mock_smart_device_strip, 0)
                exception_occurred = False
                try:
                    await battery_strip_plug.turn_on()
                except target.BatteryPlugException as e:
                    exception_occurred = True
                finally:
                    assert not exception_occurred
                battery_strip_plug = target.create_battery_strip_plug('TestExceptionStripPlug', mock_smart_device_strip, 1)
                exception_occurred = False
                try:
                    await battery_strip_plug.turn_on()
                except target.BatteryPlugException as e:
                    exception_occurred = True
                finally:
                    assert exception_occurred


@pytest.mark.asyncio
async def test_scan_for_battery_prefix():
    with patch('kasa.SmartDevice', new_callable=AsyncMock) as mock:
        reset_device_config()
    pass

@pytest.mark.asyncio
async def test_update_battery_plug_list():
    with patch('kasa.SmartDevice', new_callable=AsyncMock) as mock:
        reset_device_config()
        save_battery_plug_list = target.BatteryManagerState().battery_plug_list
        target.BatteryManagerState().battery_plug_list = []
        target.BatteryManagerState().scan_for_battery_prefix = False
        mock_smart_device_plug = mock.return_value
        mock_smart_device_plug.is_plug = True
        mock_smart_device_plug.is_strip = False
        mock_smart_device_plug.alias = 'rad_battery_1'
        assert mock_smart_device_plug.is_plug == True
        assert mock_smart_device_plug.alias == 'rad_battery_1'
        assert len(target.BatteryManagerState().battery_plug_list) == 0
        assert target.BatteryManagerState().scan_for_battery_prefix == False
        manufacturer_plug_names = []
        await target.update_battery_plug_list(mock_smart_device_plug, manufacturer_plug_names)
        assert len(target.BatteryManagerState().battery_plug_list) == 0
        target.BatteryManagerState().scan_for_battery_prefix = True
        await target.update_battery_plug_list(mock_smart_device_plug, manufacturer_plug_names)
        assert len(target.BatteryManagerState().battery_plug_list) == 1
        target.BatteryManagerState().battery_plug_list = []
        result = target.verify_config_file(CONFIG_PATH + 'sample_ebike_battery_manager.config')
        assert result == True
        manufacturer_plug_names = target.BatteryManagerState().plug_manufacturer_map.keys()
        assert mock_smart_device_plug.alias in manufacturer_plug_names
        assert len(target.BatteryManagerState().battery_plug_list) == 0
        await target.update_battery_plug_list(mock_smart_device_plug, manufacturer_plug_names)
        assert len(target.BatteryManagerState().battery_plug_list) == 1
        mock_smart_device_strip = mock.return_value
        mock_smart_device_strip.is_plug = False
        mock_smart_device_strip.is_strip = True
        mock_smart_device_strip.alias = 'lectric_strip_1'
        mock_strip_children = []
        mock_strip_children.append(mock.return_value)
        mock_strip_children[0].alias = 'lectric_battery_1'
        mock_strip_children.append(mock.return_value)
        mock_strip_children[1].alias = 'lectric_battery_2'
        mock_smart_device_strip.children = mock_strip_children
        await target.update_battery_plug_list(mock_smart_device_strip, manufacturer_plug_names)
        assert len(target.BatteryManagerState().battery_plug_list) == 3
        target.BatteryManagerState().battery_plug_list = []
        manufacturer_plug_names = []
        target.BatteryManagerState().scan_for_battery_prefix = False
        await target.update_battery_plug_list(mock_smart_device_strip, manufacturer_plug_names)
        assert len(target.BatteryManagerState().battery_plug_list) == 0
        target.BatteryManagerState().scan_for_battery_prefix = True
        await target.update_battery_plug_list(mock_smart_device_strip, manufacturer_plug_names)
        assert len(target.BatteryManagerState().battery_plug_list) == 2
        target.BatteryManagerState().scan_for_battery_prefix = False
        # Restore original battery_plug_list
        target.BatteryManagerState().battery_plug_list = save_battery_plug_list

@pytest.mark.asyncio
async def test_update_battery_plug_list_config_name_not_battery():
    with patch('kasa.SmartDevice', new_callable=AsyncMock) as mock:
        reset_device_config()
        plug_manufacturer_map = {}
        plug_manufacturer_map['rad_power_1'] = 100
        plug_manufacturer_map['lectric_1'] = 101
        plug_manufacturer_map['lectric_2'] = 102
        save_battery_plug_list = target.BatteryManagerState().battery_plug_list
        target.BatteryManagerState().battery_plug_list = []
        mock_smart_device_plug = mock.return_value
        mock_smart_device_plug.is_plug = True
        mock_smart_device_plug.is_strip = False
        mock_smart_device_plug.alias = 'rad_power_1'
        assert mock_smart_device_plug.is_plug == True
        assert mock_smart_device_plug.alias == 'rad_power_1'
        assert len(target.BatteryManagerState().battery_plug_list) == 0
        result = target.verify_config_file(CONFIG_PATH + 'test.config')
        assert result == True
        manufacturer_plug_names = plug_manufacturer_map.keys()
        assert mock_smart_device_plug.alias in manufacturer_plug_names
        assert len(target.BatteryManagerState().battery_plug_list) == 0
        assert len(manufacturer_plug_names) == 3
        await target.update_battery_plug_list(mock_smart_device_plug, manufacturer_plug_names)
        assert len(target.BatteryManagerState().battery_plug_list) == 1
        mock_smart_device_strip = mock.return_value
        mock_smart_device_strip.is_plug = False
        mock_smart_device_strip.is_strip = True
        mock_smart_device_strip.alias = 'rad_strip_1'
        mock_strip_children = []
        mock_strip_children.append(mock.return_value)
        mock_strip_children[0].alias = 'lectric_1'
        mock_strip_children.append(mock.return_value)
        mock_strip_children[1].alias = 'lectric_2'
        mock_smart_device_strip.children = mock_strip_children
        await target.update_battery_plug_list(mock_smart_device_strip, manufacturer_plug_names)
        assert len(target.BatteryManagerState().battery_plug_list) == 3
        target.BatteryManagerState().battery_plug_list = save_battery_plug_list

def setup_sample_config():
    reset_device_config()
    result = target.verify_config_file(CONFIG_PATH + 'sample_ebike_battery_manager.config')
    assert result == True
    assert len(target.BatteryManagerState().device_config) == 3
    assert len(target.BatteryManagerState().plug_manufacturer_map) == 5
    assert len(target.BatteryManagerState().plug_storage_list) == 1

def verify_plug(plug: BatteryPlug, start_nominal: float, stop_nominal: float, storage: float, full: float) -> None:
    plug_name = plug.name
    time_difference = plug.battery_charge_stop_time - plug.battery_charge_start_time
    hours_difference = ceil(time_difference.total_seconds() / 3600)
    assert(hours_difference == plug.config.charger_max_hours_to_run)    
    if plug_name in target.BatteryManagerState().plug_storage_list:
        assert plug.battery_charge_mode == target.BatteryChargeMode.STORAGE
        assert plug.config.storage_charge_stop_power_threshold == storage
        assert plug.get_active_charge_battery_power_threshold() == storage
        assert plug.check_storage_mode() == False
        assert plug.charge_threshold_passed == False
        assert plug.check_storage_mode() == True
        assert plug.charge_threshold_passed == True
    elif plug_name in target.BatteryManagerState().plug_full_charge_list:
        assert plug.battery_charge_mode == target.BatteryChargeMode.FULL
        assert plug.get_start_power_threshold() == full
        assert plug.get_active_charge_battery_power_threshold() == full
    else:
        assert plug.battery_charge_mode == target.BatteryChargeMode.NOMINAL
        assert plug.get_start_power_threshold() == start_nominal
        assert plug.get_active_charge_battery_power_threshold() == stop_nominal

def test_plug_is_time_expired():
    plug = target.create_battery_plug('TestTimeExpired', any)
    assert not plug.is_time_expired(datetime.now())
    assert not plug.is_time_expired(datetime.now() + timedelta(hours=(plug.config.charger_max_hours_to_run/2)))
    assert plug.is_time_expired(datetime.now() + timedelta(hours=plug.config.charger_max_hours_to_run))

def test_storage_mode():
    reset_device_config()
    result = target.verify_config_file(CONFIG_PATH + 'sample_ebike_battery_manager.config')
    assert result == True
    assert len(target.BatteryManagerState().device_config) == 3
    assert len(target.BatteryManagerState().plug_manufacturer_map) == 5
    assert len(target.BatteryManagerState().plug_storage_list) == 1
    assert target.BatteryManagerState().device_config['Rad'].nominal_charge_start_power_threshold == 90.0
    assert target.BatteryManagerState().device_config['Rad'].nominal_charge_stop_power_threshold == 45.0
    assert target.BatteryManagerState().device_config['Rad'].full_charge_power_threshold == 5.0
    assert target.BatteryManagerState().device_config['Rad'].storage_charge_start_power_threshold == 115.0
    assert target.BatteryManagerState().device_config['Rad'].storage_charge_stop_power_threshold == 115.0
    assert target.BatteryManagerState().device_config['Lectric'].nominal_charge_start_power_threshold == 40.0
    assert target.BatteryManagerState().device_config['Lectric'].nominal_charge_stop_power_threshold == 40.0
    assert target.BatteryManagerState().device_config['Lectric'].full_charge_power_threshold == 10.0
    assert target.BatteryManagerState().device_config['Lectric'].storage_charge_start_power_threshold == target.STORAGE_CHARGE_START_THRESHOLD_DEFAULT
    assert target.BatteryManagerState().device_config['Lectric'].storage_charge_stop_power_threshold == target.STORAGE_CHARGE_STOP_THRESHOLD_DEFAULT
    for plug_name in list(target.BatteryManagerState().plug_manufacturer_map.keys()):
        print(f'test_storage_mode:plug_name: {plug_name}')
        if 'rad' in plug_name:
            plug: target.BatteryPlug = target.create_battery_plug(plug_name, any)
            verify_plug(plug, 90.0, 45.0, 115.0, 5.0)
        print(f'test_storage_mode:plug_name: {plug_name}')
        if 'rad' in plug_name:
            strip_plug: target.BatteryStripPlug = target.create_battery_strip_plug(plug_name, any, 0)
            verify_plug(strip_plug, 90.0, 45.0, 115.0, 5.0)
        if 'lectric' in plug_name:
            plug: target.BatteryPlug = target.create_battery_plug(plug_name, any)
            verify_plug(plug, 40.0, 40.0, 90.0, 10.0)
        if 'lectric' in plug_name:
            strip_plug: target.BatteryStripPlug = target.create_battery_strip_plug(plug_name, any, 0)
            verify_plug(strip_plug, 40.0, 40.0, 90.0, 10.0)

def test_full_charge_mode():
    reset_device_config()
    result = target.verify_config_file(CONFIG_PATH + 'test.config')
    assert result == True
    assert len(target.BatteryManagerState().plug_storage_list) == 2
    assert len(target.BatteryManagerState().plug_full_charge_list) == 1
    assert 'rad_battery_1' in target.BatteryManagerState().plug_full_charge_list

def test_get_device_config():
    set_sample_thresholds()
    rad_device_threshold = target.get_device_config(RAD_BATTERY_1)
    assert rad_device_threshold.manufacturer_name == 'Rad'
    assert rad_device_threshold.full_charge_power_threshold == target.FULL_CHARGE_THRESHOLD_DEFAULT
    assert rad_device_threshold.nominal_charge_start_power_threshold == 90.0
    assert rad_device_threshold.nominal_charge_stop_power_threshold == 45.0
    assert rad_device_threshold.storage_charge_stop_power_threshold == 115.0
    assert rad_device_threshold.charger_amp_hour_rate == 2.0
    assert rad_device_threshold.battery_amp_hour_capacity == 14.0
    assert rad_device_threshold.charger_max_hours_to_run == 7.0
    default_device_threshold = target.get_device_config('rad_battery_7')
    assert default_device_threshold.manufacturer_name == target.DEFAULT_CONFIG_TAG

def test_create_battery_plug():
    set_sample_thresholds()
    plug = target.create_battery_plug(RAD_BATTERY_1, any)
    assert plug.name == RAD_BATTERY_1
    assert plug.config.manufacturer_name == RAD_MANUFACTURER_NAME

def test_create_battery_strip_plug():
    set_sample_thresholds()
    plug = target.create_battery_strip_plug(RAD_BATTERY_1, any, 1)
    assert plug.name == RAD_BATTERY_1
    assert plug.plug_index == 1
    assert plug.config.manufacturer_name == RAD_MANUFACTURER_NAME

def test_check_full_charge():
    test_max_cycles_in_fine_mode = 3
    plug = BatteryPlug('test_check_full_charge_battery_name', any, test_max_cycles_in_fine_mode, rad_config)
    result = plug.check_full_charge()
    assert result == False
    plug.charge_threshold_passed = True
    result = plug.check_full_charge()
    assert result == True
    plug.charge_threshold_passed = False
    # test fine mode countdown in force_full_charge mode
    plug.set_battery_charge_mode(target.BatteryChargeMode.FULL)
    result = plug.check_full_charge()
    assert result == False
    assert plug.max_cycles_in_fine_mode == test_max_cycles_in_fine_mode
    plug.fine_mode_active = True
    result_true_ct = 0
    test_cycle_ct = test_max_cycles_in_fine_mode
    for i in range(test_max_cycles_in_fine_mode):
        print(f'LOOP: i: {str(i)}')
        result = plug.check_full_charge()
        if result == False:
            assert plug.max_cycles_in_fine_mode < test_max_cycles_in_fine_mode
            test_cycle_ct = test_cycle_ct - 1
            assert plug.max_cycles_in_fine_mode == test_cycle_ct
        else:
            result_true_ct = result_true_ct + 1
            assert plug.max_cycles_in_fine_mode <= 0
    assert result_true_ct == 1
    # reset the plug state
    plug = BatteryPlug('test_check_full_charge_battery_name_fine_mode', any, test_max_cycles_in_fine_mode, rad_config)
    plug.fine_mode_active = True
    plug.charge_threshold_passed = True
    plug.set_battery_charge_mode(target.BatteryChargeMode.FULL)
    assert plug.full_charge_repeat_limit == 3
    result_true_ct = 0
    for i in range(plug.full_charge_repeat_limit):
        result = plug.check_full_charge()
        if result == False:
            assert plug.full_charge_repeat_count < plug.full_charge_repeat_limit
        else:
            assert plug.full_charge_repeat_count == plug.full_charge_repeat_limit
            result_true_ct = result_true_ct + 1
    assert result_true_ct == 1
    target.force_full_charge = False

def test_delete_plugs():
    plug = BatteryPlug('test_delete_plugs_battery_name', any, max_cycles_in_fine_mode, rad_config)
    strip_plug = BatteryStripPlug('test_delete_plugs_battery_name', any, 0, max_cycles_in_fine_mode, rad_config)
    battery_plug_list = []
    battery_plug_list.append(plug)
    battery_plug_list.append(strip_plug)
    assert len(battery_plug_list) == 2
    plugs_to_delete = []
    plugs_to_delete.append(strip_plug)
    plugs_to_delete.append(plug)
    target.delete_plugs(battery_plug_list, plugs_to_delete)
    assert len(battery_plug_list) == 0

def test_start_threshold_check():
    reset_device_config()
    result = target.verify_config_file(CONFIG_PATH + 'sample_ebike_battery_manager.config')
    assert result == True
    plugs = []
    for plug_name in list(target.BatteryManagerState().plug_manufacturer_map.keys()):
        if 'rad' in plug_name:
            plug: target.BatteryPlug = target.create_battery_plug(plug_name, any)
            verify_plug(plug, 90.0, 45.0, 115.0, 5.0)
            plugs.append(plug)
    plug = plugs[0]
    result = plug.start_threshold_check(50.0)
    assert result == False
    result = plug.start_threshold_check(91.0)
    assert result == True
    plug.set_battery_charge_mode(target.BatteryChargeMode.FULL)
    result = plug.start_threshold_check(50.0)
    assert result == True
    result = plug.start_threshold_check(91.0)
    assert result == True
    plug.set_battery_charge_mode(target.BatteryChargeMode.STORAGE)
    result = plug.start_threshold_check(50.0)
    assert result == False
    result = plug.start_threshold_check(91.0)
    assert result == False
    result = plug.start_threshold_check(116.0)
    assert result == True

def test_threshold_check():
    nominal_thresholds = DeviceConfig(rad_config.manufacturer_name,
                                          rad_config.nominal_charge_start_power_threshold,
                                          rad_config.nominal_charge_stop_power_threshold,
                                          rad_config.full_charge_power_threshold,
                                          rad_config.storage_charge_start_power_threshold,
                                          rad_config.storage_charge_stop_power_threshold,
                                          rad_config.storage_charge_cycle_limit,
                                          20,
                                          rad_config.charger_amp_hour_rate,
                                          rad_config.battery_amp_hour_capacity,
                                          rad_config.charger_max_hours_to_run)
    plug = BatteryPlug('test_battery_name', any, max_cycles_in_fine_mode, nominal_thresholds)
    assert plug.charge_threshold_passed == False
    result = plug.stop_threshold_check(91.0)
    assert result == False
    result = plug.stop_threshold_check(89.0)
    assert result == True
    assert plug.charge_threshold_passed == True
    result = plug.stop_threshold_check(91.0)
    assert result == True
    plug.charge_threshold_passed = False
    plug.set_battery_charge_mode(target.BatteryChargeMode.FULL)
    full_charge_thresholds = DeviceConfig(rad_config.manufacturer_name,
                                          rad_config.nominal_charge_start_power_threshold,
                                          rad_config.nominal_charge_stop_power_threshold,
                                          rad_config.full_charge_power_threshold,
                                          rad_config.storage_charge_start_power_threshold,
                                          rad_config.storage_charge_stop_power_threshold,
                                          rad_config.storage_charge_cycle_limit,
                                          20,
                                          rad_config.charger_amp_hour_rate,
                                          rad_config.battery_amp_hour_capacity,
                                          rad_config.charger_max_hours_to_run)
    plug.config = full_charge_thresholds
    result = plug.stop_threshold_check(89.0)
    assert result == False
    result = plug.stop_threshold_check(89.0)
    assert result == False
    result = plug.stop_threshold_check(5.5)
    assert result == False
    assert plug.charge_threshold_close_misses == 0
    result = plug.stop_threshold_check(5.1)
    assert result == False
    assert plug.charge_threshold_close_misses == 1
    result = plug.stop_threshold_check(4.9)
    assert result == False
    assert plug.charge_threshold_close_misses == 2
    result = plug.stop_threshold_check(5.5)
    assert result == False
    assert plug.charge_threshold_close_misses == 2
    result = plug.stop_threshold_check(4.9)
    assert result == False
    assert plug.charge_threshold_close_misses == 3
    result = plug.stop_threshold_check(4.9)
    assert result == True
    assert plug.charge_threshold_close_misses == 4
    target.force_full_charge = False

def test_mock_BatteryPlug():
    with patch('scripts.ebike_battery_manager.BatteryPlug') as mock:
        instance = mock.return_value
        instance.get_power.return_value = 4.5
        result = instance.get_power()
        assert result == 4.5

def test_mock_BatteryStripPlug():
    with patch('scripts.ebike_battery_manager.BatteryStripPlug') as mock:
        instance = mock.return_value
        instance.get_power.return_value = 4.5
        result = instance.get_power()
        assert result == 4.5

def test_device_config_battery_voltage() -> None:
    test_config = DeviceConfig(rad_config.manufacturer_name,
                                          rad_config.nominal_charge_start_power_threshold,
                                          rad_config.nominal_charge_stop_power_threshold,
                                          rad_config.full_charge_power_threshold,
                                          rad_config.storage_charge_start_power_threshold,
                                          rad_config.storage_charge_stop_power_threshold,
                                          rad_config.storage_charge_cycle_limit,
                                          20,
                                          rad_config.charger_amp_hour_rate,
                                          rad_config.battery_amp_hour_capacity,
                                          rad_config.charger_max_hours_to_run)
    assert test_config.battery_voltage == target.DEFAULT_BATTERY_VOLTAGE
    test_config = DeviceConfig(rad_config.manufacturer_name,
                                          rad_config.nominal_charge_start_power_threshold,
                                          rad_config.nominal_charge_stop_power_threshold,
                                          rad_config.full_charge_power_threshold,
                                          rad_config.storage_charge_start_power_threshold,
                                          rad_config.storage_charge_stop_power_threshold,
                                          rad_config.storage_charge_cycle_limit,
                                          20,
                                          rad_config.charger_amp_hour_rate,
                                          rad_config.battery_amp_hour_capacity,
                                          rad_config.charger_max_hours_to_run,
                                          battery_voltage=None)
    assert test_config.battery_voltage == target.DEFAULT_BATTERY_VOLTAGE
    test_config = DeviceConfig(rad_config.manufacturer_name,
                                          rad_config.nominal_charge_start_power_threshold,
                                          rad_config.nominal_charge_stop_power_threshold,
                                          rad_config.full_charge_power_threshold,
                                          rad_config.storage_charge_start_power_threshold,
                                          rad_config.storage_charge_stop_power_threshold,
                                          rad_config.storage_charge_cycle_limit,
                                          20,
                                          rad_config.charger_amp_hour_rate,
                                          rad_config.battery_amp_hour_capacity,
                                          rad_config.charger_max_hours_to_run,
                                          battery_voltage=target.DEFAULT_BATTERY_VOLTAGE)
    assert test_config.battery_voltage == target.DEFAULT_BATTERY_VOLTAGE
    test_battery_override_voltage: float = 24.0
    test_config = DeviceConfig(rad_config.manufacturer_name,
                                          rad_config.nominal_charge_start_power_threshold,
                                          rad_config.nominal_charge_stop_power_threshold,
                                          rad_config.full_charge_power_threshold,
                                          rad_config.storage_charge_start_power_threshold,
                                          rad_config.storage_charge_stop_power_threshold,
                                          rad_config.storage_charge_cycle_limit,
                                          20,
                                          rad_config.charger_amp_hour_rate,
                                          rad_config.battery_amp_hour_capacity,
                                          rad_config.charger_max_hours_to_run,
                                          test_battery_override_voltage)
    assert test_config.battery_voltage == test_battery_override_voltage

def test_default_battery_voltage() -> None:
    nominal_thresholds = DeviceConfig(rad_config.manufacturer_name,
                                          rad_config.nominal_charge_start_power_threshold,
                                          rad_config.nominal_charge_stop_power_threshold,
                                          rad_config.full_charge_power_threshold,
                                          rad_config.storage_charge_start_power_threshold,
                                          rad_config.storage_charge_stop_power_threshold,
                                          rad_config.storage_charge_cycle_limit,
                                          20,
                                          rad_config.charger_amp_hour_rate,
                                          rad_config.battery_amp_hour_capacity,
                                          rad_config.charger_max_hours_to_run)
    plug = BatteryPlug('test_battery_name', any, max_cycles_in_fine_mode, nominal_thresholds)
    assert plug.config.battery_voltage == target.DEFAULT_BATTERY_VOLTAGE

def test_override_battery_voltage() -> None:
    test_battery_override_voltage: float = 24.0
    nominal_thresholds = DeviceConfig(rad_config.manufacturer_name,
                                          rad_config.nominal_charge_start_power_threshold,
                                          rad_config.nominal_charge_stop_power_threshold,
                                          rad_config.full_charge_power_threshold,
                                          rad_config.storage_charge_start_power_threshold,
                                          rad_config.storage_charge_stop_power_threshold,
                                          rad_config.storage_charge_cycle_limit,
                                          20,
                                          rad_config.charger_amp_hour_rate,
                                          rad_config.battery_amp_hour_capacity,
                                          rad_config.charger_max_hours_to_run,
                                          test_battery_override_voltage)
    plug = BatteryPlug('test_battery_name', any, max_cycles_in_fine_mode, nominal_thresholds)
    assert plug.config.battery_voltage == test_battery_override_voltage

def compute_amp_hours(watts: float, seconds: int, battery_voltage: float) -> float:
        watt_hours: float = watts * (float(seconds) / 60.0)
        return (watt_hours / battery_voltage)


def test_active_plugs():
    nominal_thresholds = DeviceConfig(rad_config.manufacturer_name,
                                          rad_config.nominal_charge_start_power_threshold,
                                          rad_config.nominal_charge_stop_power_threshold,
                                          rad_config.full_charge_power_threshold,
                                          rad_config.storage_charge_start_power_threshold,
                                          rad_config.storage_charge_stop_power_threshold,
                                          rad_config.storage_charge_cycle_limit,
                                          20,
                                          rad_config.charger_amp_hour_rate,
                                          rad_config.battery_amp_hour_capacity,
                                          rad_config.charger_max_hours_to_run)
    target.set_active_plug(BatteryPlug('plug_1', any, max_cycles_in_fine_mode, nominal_thresholds))
    target.set_active_plug(BatteryPlug('plug_2', any, max_cycles_in_fine_mode, nominal_thresholds))
    assert len(target.BatteryManagerState().active_plugs) == 2
    time.sleep(1)
    for active_plug in target.BatteryManagerState().active_plugs:
        target.stop_active_plug(active_plug.plug.name)
        elapsed_time: datetime = active_plug.stop_time - active_plug.start_time
        assert elapsed_time.seconds > 0

def test_setup_logging_handlers_with_valid_file():
    logging_handlers = target.setup_logging_handlers('foo')
    assert len(logging_handlers) == 2

def test_setup_logging_handlers_with_invalid_file():
    logging_handlers = target.setup_logging_handlers('/usr/foo')
    assert len(logging_handlers) == 1

def test_setup_logging_handlers_with_blank_file_name():
    logging_handlers = target.setup_logging_handlers('')
    assert len(logging_handlers) == 1

def test_email_send_not_called_with_invalid_file():
    with patch('scripts.ebike_battery_manager.send') as mock:
        target.send_my_mail('any@gmail.com', 'any_app_key', None)
    assert not mock.called

if __name__ == "__main__":
    # test_foo()
    print('Everything passed')