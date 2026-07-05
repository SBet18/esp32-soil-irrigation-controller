"""
water_control.py
Irrigation control Class for a greenhouse system
Sensors: Capacitive moisture sensor, analogique water lvl sensor.
"""

from machine import Pin, ADC
import time

# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────
PUMP_FLOW      = 2500.0   # mL/h  – pump - measured value
DRY_BRUT_MOIST     = 2600     # dry sensor's ADC value - measured value
WET_BRUT_MOIST  = 1000     # saturated sensor's ADC value - measured value
MAX_WATER_BRUT     = 730      # 40mm water lvl's ADC value - measured value
WATER_THR_ALERT = 20.0     # % – low lvl alert threshold
TGT_MOIST        = 50.0     # % – target mositure


class WaterControl:
    """
    Class for automatic irrigation control.

    Constructor parameters
    --------------------------
    pin_moisture      : ADC pin of the humidity sensor (default 35)
    pin_water_lvl     : ADC pin of the water lvl sensor (default 33)
    pin_relay         : GPIO pin of the pump's relay (default 2, inverse logic)
    """

    def __init__(self, pin_moisture: int = 35,
                 pin_water_lvl: int = 33,
                 pin_relay: int = 2):

        # Moisture sensor
        self._adc_moisture = ADC(Pin(pin_moisture))
        self._adc_moisture.atten(ADC.ATTN_11DB)

        # Water lvl sensor
        self._adc_water_lvl = ADC(Pin(pin_water_lvl))
        self._adc_water_lvl.atten(ADC.ATTN_11DB)

        # Pump's relay – Inverse logic(0 = pump ON)
        self._relay = Pin(pin_relay, Pin.OUT)
        self._relay.value(1)   # Pump OFF by default

    # ──────────────────────────────────────────
    #  Soil moisture acquisition
    # ──────────────────────────────────────────
    def capacitive_get_moist(self) -> float:
        """
        Acquires the soil's relative moisture via the
        Capacitive Soil Moisture Sensor.

        Returns
        ------
        float : relative moisture in % [0.0 – 100.0]
        """
        brut = self._adc_moisture.read()
        moisture = (DRY_BRUT_MOIST - brut) / (DRY_BRUT_MOIST - WET_BRUT_MOIST) * 100.0
        # Saturation
        if moisture < 0.0:
            moisture = 0.0
        elif moisture > 100.0:
            moisture = 100.0
        return float(moisture)

    # ──────────────────────────────────────────
    #  Water level alert
    # ──────────────────────────────────────────
    def get_water_alert(self) -> bool:
        """
        Acquires the water reservoir's level.

        Returns
        ------
        bool : True if level is low (≤ WATER_THR_ALERT %), False otherwise
        """
        brut = self._adc_water_lvl.read()
        lvl_pct = brut / MAX_WATER_BRUT * 100.0
        return lvl_pct <= WATER_THR_ALERT

    # ──────────────────────────────────────────
    #  Pump control
    # ──────────────────────────────────────────
    def pump(self, status: bool) -> None:
        """
        Activates / deactivates the pump via the relay.

        Parameter
        ---------
        status : True = pump ON, False = pump OFF
        """
        self._relay.value(not status)   # inverse relay logic

    # ──────────────────────────────────────────
    #  Water distribution calculation
    # ──────────────────────────────────────────
    def distribute_water(self, tgt_cons: float,
                         interval_h: float) -> tuple:
        """
        Calculates the volume and pumping duration for each ration.

        The daily consumption is split into equal rations
        every `interval_h` hours.

        Parameters
        ----------
        tgt_cons   : target daily consumption in mL/day (float)
        interval_h : interval between distributions in h (float)

        Returns
        ------
        (bool, float) : activation flag, pumping duration in s
        """
        if interval_h <= 0 or tgt_cons <= 0:
            return False, 0.0

        times_per_day  = 24.0 / interval_h          # rations/day
        volume_per_cycle  = tgt_cons / times_per_day  # mL per ration
        pump_duration     = volume_per_cycle / PUMP_FLOW * 3600.0  # s

        pump_flag = pump_duration > 0.0
        
        print("  Feeding volume : " + str(round(volume_per_cycle, 1)) + " mL")
        print("  Pumping duration  : " + str(round(pump_duration, 2)) + " s")
        print("  Pump flag   : " + str(pump_flag))

        if pump_flag and not self.get_water_alert():
            print("  → Starting pump…")
            self.pump(True)
            time.sleep(pump_duration)
            self.pump(False)
            print("  → Pump stopped.")
        elif self.get_water_alert():
            print("  ⚠  Empty tank – pumping canceled !")
        return pump_flag, float(pump_duration)

    # ──────────────────────────────────────────
    #  Optimized distribution (hygrometry)
    # ──────────────────────────────────────────
    def distribute_water_moist(self, tgt_cons: float,
                              interval_h: float,
                              moisture: float,
                              deviation: float) -> tuple:
        """
        Water distribution optimized by the soil moisture reading.

        The base volume is modulated according to the gap between
        the measured moisture and the target (TGT_MOIST). The correction
        is bounded to ±deviation %.

        Parameters
        ----------
        tgt_cons     : target daily consumption in mL/day (float)
        interval_h  : interval between distributions in h (float)
        moisture      : soil relative moisture in % (float)
        deviation     : allowed deviation on tgt_cons in % (float)

        Returns
        ------
        (bool, float) : activation flag, pumping duration in s
        """
        if interval_h <= 0 or tgt_cons <= 0:
            return False, 0.0

        # Base volume per ration
        times_per_day  = 24.0 / interval_h
        volume_base = tgt_cons / times_per_day   # mL

        # ── Hygrometric correction factor ──────────────────────
        # Normalized gap between target and measurement  →  [-1 ; +1]
        #   moisture < TGT_MOIST  → dry soil  → +correction (more water)
        #   moisture > TGT_MOIST  → wet soil → -correction (less water)
        
        normalized_deviation = (TGT_MOIST - moisture) / TGT_MOIST
        # +1 : dry soil - maximum water need
        # -1 : 100% wet soil - no water need
        # Clamp to [-1 ; 1] to secure extreme cases
        normalized_deviation = max(-1.0, min(1.0, normalized_deviation))
        correction      = normalized_deviation * (deviation / 100.0)
        volume_tuned   = volume_base * (1.0 + correction)

        # Strict bound ±deviation %
        volume_max      = volume_base * (1.0 + deviation / 100.0)
        volume_min      = volume_base * (1.0 - deviation / 100.0)
        volume_tuned   = max(volume_min, min(volume_max, volume_tuned))

        pump_duration = volume_tuned / PUMP_FLOW * 3600.0  # s
        pump_flag = pump_duration > 0.0
        
        print("  mesured moisture  : " + str(round(moisture, 1)) + "%")
        print("  Tuned volume      : " + str(round(volume_tuned, 1)) + " mL")
        print("  Pumping duration  : " + str(round(pump_duration, 2)) + " s")
        print("  Pumo flag         : " + str(pump_flag))

        if pump_flag and not self.get_water_alert():
            print("  → Starting pump (optimized)…")
            self.pump(True)
            time.sleep(pump_duration)
            self.pump(False)
            print("  → Pump stopped.")
        elif self.get_water_alert():
            print("  ⚠  Empty tank – pumping canceled !")

        return pump_flag, float(pump_duration)
