# Experimental Data
- The sample set is three Rad Power 48V batteries, two older and one newer and two new Lectric batteries from the Lectric XPedition.
    - The battery voltage is checked via multimeter in the morning after a charge cycle.
    - *If you do this, make sure the battery is switched on so the multimeter sees the voltage at the output plugs.*
- The granularity of the script to probe for power usage and cutoff detection is every 5 minutes.
- See References section for tables correlating battery voltage to percent of charge.
    - There are various charts but the one I am using is from reference (1) and correlates the full charge voltage (52.9) of the battery to 99% while other ones showed that voltage as only 87% but since 52.9 is as high as the Rad batteries go when the chargers indicate a full charge, that particular chart seems better correlated.
- Depending on which chart used, you get different cutoffs.
- This is not a scientific test, only low/single point measurements and a specific configuration only.
- It is an example of how a user can vary the nominal cutoff and figure out appropriate values for their specific battery and riding needs.
## Rad Chargers
### Nominal Power Cutoff Data
Nominal Power Cutoff == 90W

| Cutoff Power Draw| Battery | Battery Voltage | Capacity |
| :------- | ---- | ---------------: | ---------: |
| 20W | Rad_Newest   | 52.8                |        98%
| 20W | Rad_Older_2   | 52.7                |        97%
| 25W | Rad_Newest   | 52.6                |        96%
| 25W | Rad_Older_2   | 52.6                |        96%
| 30W | Rad_Newest   | 52.6                |        96%
| 30W | Rad_Older_2   | 52.6                |        96%
| 40W | Rad_Newest   | 52.5                |        95%
| 40W | Rad_Older_2   | 52.6                |        96%
| 70W | Rad_Older_2   | 52.3                |        94%
| 90W | Rad_Newest   | 52.3                |        94%
| 90W | Rad_Newest   | 52.0                |        91%
| 90W | Rad_Older_1   | 52.1                |        92%
| 90W | Rad_Older_2   | 52.0                |        91%
| 90W | Rad_Newest   | 52.0                |        91%
| 90W | Rad_Older_1   | 52.1               |        93%
| 90W | Rad_Older_1   | 51.9               |        90%
| 90W | Rad_Newest   | 52.0                |        91%
| 90W | Rad_Older_1   | 52.1                |        92%

### Full Power Cutoff Data

Full Power Cutoff == 5W, 
- Measured 6-8 hours after completion so the voltage reflects the charger shut down point plus the drop between charger shutoff and measurement.
    - Verified that the charger shows completion after the cutoff point so we are not stopping early.

| Cutoff Power Draw| Battery | Battery Voltage | Capacity |
| :------- | ---- | ---------------: | ---------: |
| 5W | Rad_Newest   | 52.9                |        99%
| 5W | Rad_Older_2   | 52.9                |        99%
| 5W | Rad_Newest   | 52.8                |        98%
| 5W | Rad_Older_2   | 52.8                |        98%

### Storage Power Cutoff Data
Starting Voltage = 49.3 ~ 66%
| Starting Voltage | Start Capacity | Cutoff Power Draw| Plug | Battery Voltage | Capacity |
:------- | ---- | :------- | ---- | ---------------: | ---------: |
| 49.3 | 66% | 115W | rad_battery_3   | xx.x                |        xx%

## Lectric Chargers
### No Battery Power Draw
### Nominal Power Cutoff Data
Nominal Power Cutoff == 90W

| Cutoff Power Draw| Battery | Battery Voltage | Capacity | Notes | 
| :------- | ---- | ---------------: | ---------: | ----------- |
| 80W | lectric_battery_1   | 52.2                |        93% | Display shows 53.6 but voltmeter used for all measurements shows 52.2 | 
| 80W | lectric_battery_2   | 52.2                |        93% | 

### Full Power Cutoff Data

Full Power Cutoff == 10W, 
- Green light on charger around this point.

| Cutoff Power Draw| Battery | Battery Voltage | Capacity |
| :------- | ---- | ---------------: | ---------: |
| 10W | lectric_battery_1   | 53.2                |        100+%
| 10W | lectric_battery_2   | 53.1                |        100+%

### Storage Power Cutoff Data
Starting Voltage = 49.3 ~ 66%
| Starting Voltage | Start Capacity | Cutoff Power Draw| Plug | Battery Voltage | Capacity |
:------- | ---- | :------- | ---- | ---------------: | ---------: |
| 49.3 | 66% | 115W | No data   | xx.x                |        xx%
## References
1. https://ebikesforum.com/threads/48-volt-13s-battery-voltage-chart-li-ion-batteries.699/#:~:text=80%25%20DOD%20is%20around%2043v%20depending%20on%20cell%20chemistry
2. https://www.cnet.com/roadshow/news/how-to-keep-your-e-bike-battery-in-top-shape/
3. https://www.electrifybike.com/blogs/news/charging-and-caring-for-your-lithium-ion-ebike-battery
