from machine import ADC, Pin
import time


# Schutz-Spannungsteiler:
# Messpunkt -> R_TOP -> GP26/ADC0 -> R_BOTTOM -> GND
R_TOP = 220_000
R_BOTTOM = 100_000
ADC_MAX_V = 3.3

adc = ADC(Pin(26))
factor = (R_TOP + R_BOTTOM) / R_BOTTOM

print("PICO_VOLTMETER_READY")
print("Wiring: test point -> 220k -> GP26 -> 100k -> GND")
print("Ctrl+C zum Beenden")

while True:
    raw = adc.read_u16()
    adc_v = raw * ADC_MAX_V / 65535
    input_v = adc_v * factor
    print("raw={} adc_v={:.3f} input_v={:.3f}".format(raw, adc_v, input_v))
    time.sleep(0.25)
