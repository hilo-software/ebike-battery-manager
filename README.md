# EBike Battery Plug Manager

## **Important - Read this first**
*This script requires additional hardware to work:*  

Required hardware:

- One or more TP-Link Smart Plug socket or Smart Strip with energy metering capability (emeter)
    - The KP115 Smart Plug and the HS300 Smart Strip models are compatible.
    - The KP303 is NOT compatible as it does not have the energy metering capability.
- The associated Kasa phone app to add the TP-Link devices to the network
- A WiFi network for the TP-Link Smart Plug(s) and the computer hosting the script.
- A linux or MacOS host capable of running **Python 3.10** to host the script.  (Raspberry Pi's work fine)


**If purchasing the hardware is not acceptable, GO NO FURTHER!**

## Summary
### Benefits

- The script monitors charging of batteries and turns off the plug that the charger is connected to when a suitable level of charge has been attained.
- This should be equivalent to unplugging the charger from the  wall and avoids any safety issues associated with leaving chargers and batteries plugged into power after they are charged.
- Charging can be scheduled for off peak periods since when not charging, the plug is turned off.
- Three modes are supported, **nominal**, **full charge** and **storage**:
    - The **nominal** charge mode turns off the charger slightly before full charge is attained to reduce wear on the battery and extend battery life.
    - The **full charge** mode allows the battery to charge fully to balance the cells, something that periodically needs to be done.
    - The **storage** charge mode allows keeping the battery at a lower level of charge when the battery will not be used for an extended period of time, preventing unnecessary wear on the battery.

## How it works

 The script looks at the power draw of the TP-Link plug that the charger is plugged into and based on the measured power draw, shuts off the plug once the chargers power draw drops below either nominal or full charge cutoff limits, depending on the mode the script is used in.

### How Lithium Ion battery chargers work
See references 4, 5 below and the ExperimentalData.md file. 
- Lithium Ion chargers work in two stages:
    - Stage 1 is the Constant Current charge and uses a constant current until an expected voltage is observed.
    - Stage 2 is the Saturation charge which occurs when the constant voltage peak is observed.  During this stage the current will steadily fall until it reaches a minimum, ~10% of the rated current.

With most chargers we cannot observe the actual current usage inside charger or the battery but we can observe how much current is being pulled through the SmartPlug.  We depend on their being a correlation between that observed current draw at the Smart Plug and the current drop in Stage 2 of the charger.

Three cutoff thresholds are supported.  
- A nominal cutoff threshold cuts off power to the plug/charger slightly before the battery is fully charged to hopefully extend battery life.
- A full charge cutoff threshold allows the charger to fully charge the battery enabling balancing of the individual cells.
- A storage cutoff threshold behaves identically to the nominal cutoff but allows a lower cutoff to hold the battery at a lower charge percentage which is desirable in Li Ion batteries that will be stored unused for an extended period of time.

A nominal start threshold is also supported.
- The start threshold can be higher than the cutoff threshold to reduce the occurrence of very small recharges due to a battery's normal slow discharge rate.  This can reduce wear on both the charger and the battery.
## Disclaimer
- The author of the script is not an electrical power engineer but is a software engineer who has worked with embedded systems. 
- The script observes the power draw that the chargers are pulling at the smart plug.
- The script assumes that power draw is related to the amount of amperage the charger is adding to the battery.
- The script assumes that as the battery approaches full charge, the charger draws correspondingly less power establishing a known power drawdown curve that is correlated with the actual charger as it charges the battery, allowing the script to manage the charger(s) by controlling the TP-Link smart plug(s) on/off state. 
- This behavior was observed to be true with Rad Power and Lectric EBike batteries and chargers.
- This is a correlational approach and results will be approximate since we do not see the actual battery charge voltage while the charger is actively charging the battery.
## Compatibility
- The script is developed using Rad Power EBike battery packs and chargers for both Rad Mini and RadRunner Plus models.
- Lectric XPedition packs and chargers are also profiled.
- Currently only 48V systems have been profiled.
- The script provides command line control to allow customization of certain default parameters.
    - You can always directly modify the Python script as well.
- A configuration file is also allowed which provides more extensive customization.  See sample_ebike_battery_manager.config
    - Multiple configurations based on a separate manufacturers as well as different models within a given manufacturer are supported.
## Setup
### TP Link Plugs
- Any TP-Link plug/strip that supports plug level power metering should work.  The KP115 and HS300 were used in development so modifications to the script may be needed for other models that support energy metering.
### Python3
- Python 3.10.6 or more recent
### Python Kasa Library
- This is mandatory, the script imports this third party library which furnishes the API to access the TP-Link SmartDevices.
- https://github.com/python-kasa/python-kasa

#### Naming the plugs
- The script looks for all TP-Link devices prefixed with "battery_" and treats those as plugs with battery chargers attached.
- Custom battery names can be specified via a config file.
- After you have installed the python-kasa library should create a command line interface "kasa"
- Use the kasa command without arguments to get all devices and their ip addresses
    - $ kasa
- Naming a plug can be done using the kasa alias command at the command line in either a Mac OS Terminal or a linux Terminal.
    - $ kasa --host <ip> alias <new_name>
    - For example: ```$ kasa --host 192.168.1.555 alias battery_1``` assigns a plug the name of battery_1
### Raspberry Pi
- A Raspberry Pi is not mandatory but it is what I use to drive the script.
- https://medium.com/geekculture/use-raspberry-pi-and-tp-link-kasa-to-automate-your-devices-9f936a6243c1
## Features
## Nominal, Full Charge and Storage
- Nominal charge mode is intended for daily use to keep batteryies charge to a point slightly less than full charge to maximize battery life.
- Full charge mode brings batteries to full charge and is intended for periodic use to allow battery cell balancing.
- Storage mode is intended for use when the battery will not be used for an extended period of time.
## Reports go to a logfile in the same directory the script is run in
- As the script runs, it posts information to a logfile as well as to the console and optionally to email.
    - The default logfile name is **ebike_battery_manager.log** and a custom logfile name be specified by the -l, --log_file_name command line argument
    - The logfile is overwritten with each run to prevent creating a large logfile.
### Gmail report support
- The script supports using gmail's app support to generate an email report which contains the log info.
    - This particular approach expects a Google app password: https://support.google.com/mail/answer/185833?hl=en-GB
- smtp.sendmail is the underlying mechanism so different smtp servers can be used.  Modify as needed.
## Usage
- The script handles a daily charge scenario and depends on outside support such as linux's crontab for scheduling runs over time.
- Users should keep the same charger/battery pair in each plug if possible for consistency in looking at the logs.
### Command line arguments

```
 ./ebike_battery_manager.py -h
usage: ebike_battery_manager.py [OPTIONS]

Manage EBike battery charging with TP-Link smart socket(s)

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -e , --email          email address to send reports to
  -a , --app_key        Google app key needed to allow sending mail reports [gmail only]
  -f, --force_full_charge
                        forces all batteries into full charge mode
  -t, --test_mode       test mode only, verify early stages, no real plug activity
  -l , --log_file_name 
                        overrides logfile name, default is battery_plug_controller.log
  -c , --config_file    optional config file, useful to support multiple manufacturers, overrides default values
  -q, --quiet_mode      reduces logging
  --nominal_start_charge_threshold 
                        set the default start threshold power override for nominal charge start
  --nominal_charge_cutoff 
                        set the default cutoff power override for nominal charge complete
  --full_charge_repeat_limit 
                        number of cycles to repeat after attaining full charge
  --max_cycles_in_fine_mode 
                        max limit of cycles to prevent forever charge
  --full_charge_cutoff 
                        set the full power override for full charge complete
  --storage_start_charge_threshold 
                        set the storage threshold power override for storage charge start
  --storage_charge_cutoff 
                        set the storage power override for storage charge complete
  --storage_charge_cycle_limit 
                        max cycles to charge in storage charge mode, default is 1
  --max_hours_to_run    maximum time to run the script in hours (Default is 12 hours)
```

### Configuration file
- A configuration file can be used to furnish the cutoff thresholds and also to support multiple manufacturers and custom plug/battery names.
    - This file can reside in the directory the script is run from or be be specified with a full path.
    - This is the preferred method of setting options, especially in the case where multiple manufacturers or multiple model profiles must be separately specified.
- The sample config file: sample_ebike_battery_manager.config can be used as a template. -- See the ./config directory
- For multiple profiles the plugs must be dedicated to a specific profile and matching charger/battery pairs assigned to the plug.
    - Multiple batteries matching a charger can be interchanged as needed to charge them.
#### Configuration Sections
- The configuration files will have a section named for each manufacturer with the appropriate threshold power cutoffs.
    - There can be multiple sections for a manufacturer since they may have different batteries and chargers for different ebike models.  In this case, you can just add sections like Rad-1, Rad-2 or whatever way you want to distinguish them.
    - Mandatory fields
        - nominal_charge_stop_power_threshold
            - In nominal charge mode when the current draw of a plug falls below this value, the plug will be powered off and the charger will stop charging the battery.
        - full_charge_power_threshold
            - In full charge mode when the current draw of a plug falls below this value, the plug will be powered off and the charger will stop charging the battery.
        - coarse_probe_threshold_margin
            - Initially the script will check the current draw of a plug in fairly coarse time intervals.
            - Once the current draw of a plug falls below this threshold the script will begin checking more often in shorter time intervals.
    - Optional field(s)
        - nominal_charge_start_power_threshold
            - This allows fine tuning the decision to start charging in nominal mode and can be used to reduce repeated small charges and reduce charger and battery wear and tear.
            - If omitted, the nominal_charge_stop_power_threshold will be used
        - storage_charge_stop_power_threshold
            - If omitted, then the nominal_charge_stop_power_threshold will be used in its place
        - charger_amp_hour_rate
            - The amps per hour the charger can send to the battery.
            - In conjunction with the battery_amp_hour_capacity field this is used to determine the maximum cutoff time for a battery to be charged.
        - battery_amp_hour_capacity
            - Battery capacity in amp hours.
        - If both charger_amp_hour_rate and battery_amp_hour_capacity are set, the script can more accurately set an overall maximum runtime for the charger and battery pair.  If the fields are not set the script will use the overall max_hours_to_run.

- The [Plugs] section matches plug_names with manufacturer section profiles.
- The [Storage] section is optional and when present lists plug_names that are to be in Storage mode
    - The Storage section has the highest precedence for plug charging modes.  If a plug_name is present in both this Storage section and the FullCharge section below, the plug_name will charge in Storage mode.
- The [FullCharge] section is optional and when present lists plug_names that are to be fully charged all the time, overriding any time the script is running in nominal mode.
    - This section has a lower precedence that Storage.

### Profiling a Battery and Charger pair
- Run a full charge sequence and examine the log.
    - Do NOT use quiet mode (-q) or you will not see the detailed data you will need.
- Ideally you will see distinct changes in power consumption levels
    - These large changes are a clue as to where the nominal/full charge occurs.
    - If you have a multimeter, this is a good place to begin setting various nominal cutoff points and then measuring the battery voltage after the cutoff occurs and the plug shuts down.
- If you determine values for a new manufacturer, please post in ExperimentalData.md for others to use.

### Linux cron Job Example for scheduling daily running of the script
The Linux cron function allows scheduling actions based on time and date.

#### Possible scenarios

##### Example Use Cases
- Use CRON to schedule daily nominal charge cycles and a full charge cycle at 12AM Saturday in anticipation of longer rides on weekends.
```
0 0  * * SUN /home/kelvin/sandbox/ebike_battery_manager.py -c /home/kelvin/sample_ebike_battery_manager.config -e <your_gmail> -a <your_gmail_app_id>
0 0  * * 1-5 /home/kelvin/sandbox/ebike_battery_manager.py -c /home/kelvin/sample_ebike_battery_manager.config -e <your_gmail> -a <your_gmail_app_id>
0 0  * * SAT /home/kelvin/sandbox/ebike_battery_manager.py -f -c /home/kelvin/sample_ebike_battery_manager.config -e <your_gmail> -a <your_gmail_app_id>
```

### Host Computer

#### Linux, including Raspberry PI
- These work as the python-kasa library that supports the script appears to be developed in linux.
- The script is set to look for bash as the command shell.  If the command shell is different, run explicitly under python by prefixing python3 to the script run line.
#### Windows
- The short answer is to run the script from a WSL linux shell where cron is available.
- I have not tried this.  Also, it appears WSL supports cron but does not start the service by default.  
    - https://www.howtogeek.com/746532/how-to-launch-cron-automatically-in-wsl-on-windows-10-and-11/
- Whether or not cron runs while windows sleeps is also a matter for the interested reader to determine.
#### Mac OS
- It appears that MacOS will also work.  The default kasa install does not place the kasa script on the path so you will have to locate it.  In my MacOS install, it is at ~/Library/Python/3.9/bin/kasa and needs to be explicitly run with python.  I successfully ran it in the bin directory.
```
% cd ~/Library/Python/3.9/bin/
% python3 kasa
```
- ebike_battery_manager.py is a command line app so you have to run it in a terminal.
- Also the ebike_battery_manager.py script is set to look for bash so on the mac, which uses zsh instead, you have to explcitly run it under python by prefixing python3 to the script run lines.
- Mac OS supports cron but cron jobs will not wake a sleeping Mac OS so there will be some hoops to jump through if you want the job to run late at night.

## References
1. https://ebikesforum.com/threads/48-volt-13s-battery-voltage-chart-li-ion-batteries.699/#:~:text=80%25%20DOD%20is%20around%2043v%20depending%20on%20cell%20chemistry
2. https://www.cnet.com/roadshow/news/how-to-keep-your-e-bike-battery-in-top-shape/
3. https://www.electrifybike.com/blogs/news/charging-and-caring-for-your-lithium-ion-ebike-battery
4. https://www.batteriesplus.com/blog/power/lithium-battery-chargers
5. https://www.electronics-notes.com/articles/electronic_components/battery-technology/li-ion-lithium-ion-charging.php

## Unit Tests
- Unit testing is furnished in ebike_battery_manager_test.py
- Run pytest in the same directory as the repository.
- There is only limited coverage of async functions.
```
$ cd scripts
$ python3 -m pytest ../test/
===================================================================================================== test session starts ======================================================================================================
platform linux -- Python 3.10.6, pytest-7.3.1, pluggy-1.0.0
rootdir: /home/kelvin/sandbox/projects/ebike-battery-manager
plugins: anyio-3.6.2
collected 14 items                                                                                                                                                                                                             

../test/ebike_battery_manager_test.py ..............                                                                                                                                                                     [100%]

====================================================================================================== 14 passed in 0.09s ======================================================================================================
```
## TBD
- Investigate integration of script into Home Assistant ecosystem.
- Add more async unit test coverage.
