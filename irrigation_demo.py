"""
irrigation_demo.py
"""

from water_control import WaterControl
from machine import Pin
import time

# ──────────────────────────────────────────────
#  Supervision parameters (adjustable)
# ──────────────────────────────────────────────
TARGET_CONSUMPTION_ML = 500.0   # mL/day – target daily consumption
INTERVAL_H             = 0.15    # h – interval between distributions
DEVIATION_PCT          = 20.0    # % – allowed deviation (FT4.4)

# ──────────────────────────────────────────────
#  Initialization
# ──────────────────────────────────────────────
wc   = WaterControl(pin_moisture=35, pin_water_lvl=33, pin_relay=2)
stop = Pin(25, Pin.IN)   # emergency stop button

print("=" * 45)
print(" Water Supply Demonstration")
print("=" * 45)

# ──────────────────────────────────────────────
#  Sensor acquisition
# ──────────────────────────────────────────────
print("\nReading sensors (10 s)…")
for _ in range(10):
    if stop.value():
        break

    moisture        = wc.capacitive_get_moist()
    water_level_low = wc.get_water_alert()

    print("  Soil moisture : " + str(round(moisture, 1)) +
          "%  |  Low level alert : " + str(water_level_low))
    time.sleep(1.0)

# ──────────────────────────────────────────────
#  Pump control test
# ──────────────────────────────────────────────
print("\nPump test – 3 s ON then OFF")
wc.pump(True)
print("  Pump: ON")
time.sleep(3.0)
wc.pump(False)
print("  Pump: OFF")

# ──────────────────────────────────────────────
#  Ration calculation & execution
# ──────────────────────────────────────────────
print("\ndistribute_water | target=" + str(TARGET_CONSUMPTION_ML) +
      " mL/day  interval=" + str(INTERVAL_H) + " h")

pump_flag, pump_duration = wc.distribute_water(TARGET_CONSUMPTION_ML, INTERVAL_H)
volume_per_cycle         = TARGET_CONSUMPTION_ML / (24.0 / INTERVAL_H)

print("  Volume per ration : " + str(round(volume_per_cycle, 1)) + " mL")
print("  Pumping duration  : " + str(round(pump_duration, 2)) + " s")
print("  Pump flag         : " + str(pump_flag))

if pump_flag and not wc.get_water_alert():
    print("  → Starting pump…")
    wc.pump(True)
    time.sleep(pump_duration)
    wc.pump(False)
    print("  → Pump stopped.")
elif wc.get_water_alert():
    print("  ⚠  Empty tank – pumping canceled !")

# ──────────────────────────────────────────────
#  Moisture-optimized distribution
# ──────────────────────────────────────────────
moisture = wc.capacitive_get_moist()
print("\ndistribute_water_moist | target=" + str(TARGET_CONSUMPTION_ML) +
      " mL/day  interval=" + str(INTERVAL_H) + " h  moisture="
      + str(round(moisture, 1)) + "%  dev=" + str(DEVIATION_PCT) + "%")

pump_flag_opt, pump_duration_opt = wc.distribute_water_moist(
    TARGET_CONSUMPTION_ML, INTERVAL_H, moisture, DEVIATION_PCT)

adjusted_volume = pump_duration * 2500.0 / 3600.0   # mL recalculated

print("  Measured moisture : " + str(round(moisture, 1)) + "%")
print("  Adjusted volume   : " + str(round(adjusted_volume, 1)) + " mL")
print("  Pumping duration  : " + str(round(pump_duration, 2)) + " s")
print("  Pump flag         : " + str(pump_flag_opt))

if pump_flag_opt and not wc.get_water_alert():
    print("  → Starting pump (optimized)…")
    wc.pump(True)
    time.sleep(pump_duration_opt)
    wc.pump(False)
    print("  → Pump stopped.")
elif wc.get_water_alert():
    print("  ⚠  Empty tank – pumping canceled !")

print("\n[END] Demonstration finished.")
